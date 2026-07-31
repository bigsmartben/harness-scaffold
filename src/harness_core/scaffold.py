"""Authoritative governance state, projection, and enforcement safeguards."""

from __future__ import annotations

import fnmatch
import json
import os
import re
import tempfile
from copy import deepcopy
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .artifacts import canonical_digest
from .lifecycle import (
    apply_operation,
    build_operation_request,
    cancel_operation,
    empty_governance_state,
    register_operation,
)
from .model import (
    CELL_IDS,
    CONTRACT_VERSION,
    DOMAINS,
    consumer_rule_cell_ids,
)


GOVERNANCE_STATE_RELATIVE_PATH = ".harness/governance/state.json"
EVIDENCE_TYPES = {
    "specification": "acceptance_record",
    "implementation": "implementation_result",
    "verification": "verification_result",
    "delivery": "delivery_result",
}
ENFORCEMENT_DECISIONS = (
    "satisfied",
    "blocked",
    "not_applicable",
    "stale",
)
_FORBIDDEN_EVIDENCE_PRODUCERS = {
    "agent_summary",
    "memory",
    "transcript",
    "chat",
}
_SHA256_PATTERN = re.compile(r"^sha256:[a-f0-9]{64}$")


def _projection_payload(state: dict[str, Any]) -> dict[str, Any]:
    enabled = []
    disabled = []
    for rule_id in sorted(state["rules"]):
        rule = state["rules"][rule_id]
        identity = {
            "rule_id": rule_id,
            "revision": rule["revision"],
            "domain": rule["domain"],
            "cell_bindings": list(consumer_rule_cell_ids(rule["domain"])),
        }
        if rule["status"] == "disabled":
            disabled.append({**identity, "status": "disabled"})
            continue
        enabled.append(
            {
                **identity,
                "status": "enabled",
                "directive": rule["directive"],
                "scope": deepcopy(rule["scope"]),
                "sources": deepcopy(rule["sources"]),
            }
        )
    return {
        "artifact_type": "harness-governance-projection",
        "contract_version": CONTRACT_VERSION,
        "state_revision": state["state_revision"],
        "fixed_cells": list(CELL_IDS),
        "rules": enabled,
        "disabled_rules": disabled,
    }


def compile_governance_projection(state: dict[str, Any]) -> dict[str, Any]:
    """Project effective rules and fixed Cell bindings deterministically."""

    projection = _projection_payload(state)
    projection["projection_id"] = canonical_digest(projection)
    return projection


def _scope_matches(patterns: list[str], target: str) -> bool:
    return any(
        pattern == "**" or fnmatch.fnmatchcase(target, pattern)
        for pattern in patterns
    )


def create_enforcement_obligations(
    state: dict[str, Any],
    event: dict[str, Any],
) -> dict[str, Any]:
    """Create typed obligations for rules applicable to one governed event."""

    projection = compile_governance_projection(state)
    required = {"event_id", "domain", "target", "event_type"}
    if not isinstance(event, dict) or set(event) != required:
        return {
            "decision": "blocked",
            "projection_id": projection["projection_id"],
            "obligations": [],
            "diagnostics": [
                {
                    "code": "GOVERNED_EVENT_INVALID",
                    "message": (
                        "event must contain event_id, domain, target, and event_type"
                    ),
                }
            ],
        }
    if event["domain"] not in DOMAINS:
        return {
            "decision": "blocked",
            "projection_id": projection["projection_id"],
            "obligations": [],
            "diagnostics": [
                {
                    "code": "GOVERNANCE_DOMAIN_INVALID",
                    "message": "event domain is outside the fixed model",
                    "actual": event["domain"],
                }
            ],
        }
    applicable = [
        rule
        for rule in projection["rules"]
        if rule["domain"] == event["domain"]
        and _scope_matches(rule["scope"], event["target"])
    ]
    obligations = []
    for rule in applicable:
        base = {
            "projection_id": projection["projection_id"],
            "event_id": event["event_id"],
            "event_type": event["event_type"],
            "domain": event["domain"],
            "target": event["target"],
            "rule_id": rule["rule_id"],
            "revision": rule["revision"],
            "evidence_type": EVIDENCE_TYPES[rule["domain"]],
            "completion_condition": (
                "typed evidence postcondition status is passed"
            ),
        }
        obligations.append(
            {
                "enforcement_id": "enf-"
                + canonical_digest(base).split(":", maxsplit=1)[1][:24],
                **base,
            }
        )
    return {
        "decision": "applicable" if obligations else "not_applicable",
        "projection_id": projection["projection_id"],
        "obligations": obligations,
        "diagnostics": [],
    }


def evaluate_enforcement(
    state: dict[str, Any],
    obligation: dict[str, Any],
    evidence: dict[str, Any] | None,
) -> dict[str, Any]:
    """Recompute applicability and evaluate typed external evidence."""

    projection = compile_governance_projection(state)
    if obligation.get("projection_id") != projection["projection_id"]:
        return {
            "decision": "stale",
            "enforcement_id": obligation.get("enforcement_id"),
            "diagnostics": [
                {
                    "code": "ENFORCEMENT_PROJECTION_STALE",
                    "message": "obligation references a superseded projection",
                    "expected": projection["projection_id"],
                    "actual": obligation.get("projection_id"),
                }
            ],
        }
    current = next(
        (
            rule
            for rule in projection["rules"]
            if rule["rule_id"] == obligation.get("rule_id")
        ),
        None,
    )
    if (
        current is None
        or current["revision"] != obligation.get("revision")
        or current["domain"] != obligation.get("domain")
        or not _scope_matches(
            current["scope"], str(obligation.get("target", ""))
        )
    ):
        return {
            "decision": "stale",
            "enforcement_id": obligation.get("enforcement_id"),
            "diagnostics": [
                {
                    "code": "ENFORCEMENT_RULE_STALE",
                    "message": (
                        "obligation no longer resolves to an active applicable rule"
                    ),
                }
            ],
        }
    if evidence is None:
        return {
            "decision": "blocked",
            "enforcement_id": obligation["enforcement_id"],
            "diagnostics": [
                {
                    "code": "EVIDENCE_MISSING",
                    "message": (
                        "applicable governance obligation requires typed evidence"
                    ),
                }
            ],
        }
    required = {
        "evidence_id",
        "enforcement_id",
        "projection_id",
        "rule_id",
        "revision",
        "evidence_type",
        "producer",
        "artifact_digest",
        "postcondition",
    }
    if not isinstance(evidence, dict) or set(evidence) != required:
        return {
            "decision": "blocked",
            "enforcement_id": obligation["enforcement_id"],
            "diagnostics": [
                {
                    "code": "EVIDENCE_INVALID",
                    "message": (
                        "evidence fields do not match the enforcement contract"
                    ),
                }
            ],
        }
    producer = evidence["producer"]
    if (
        not isinstance(producer, dict)
        or set(producer) != {"type", "identity"}
        or not isinstance(producer.get("type"), str)
        or not producer["type"]
        or not isinstance(producer.get("identity"), str)
        or not producer["identity"]
        or not isinstance(evidence["evidence_id"], str)
        or not evidence["evidence_id"]
        or not isinstance(evidence["artifact_digest"], str)
        or _SHA256_PATTERN.fullmatch(evidence["artifact_digest"]) is None
    ):
        return {
            "decision": "blocked",
            "enforcement_id": obligation["enforcement_id"],
            "diagnostics": [
                {
                    "code": "EVIDENCE_INVALID",
                    "message": (
                        "evidence identity, producer, and artifact digest must "
                        "match the typed contract"
                    ),
                }
            ],
        }
    if producer["type"] in _FORBIDDEN_EVIDENCE_PRODUCERS:
        return {
            "decision": "blocked",
            "enforcement_id": obligation["enforcement_id"],
            "diagnostics": [
                {
                    "code": "EVIDENCE_PRODUCER_FORBIDDEN",
                    "message": (
                        "Agent summaries, Memory, chat, and transcripts are not evidence"
                    ),
                    "actual": producer,
                }
            ],
        }
    bindings = {
        "enforcement_id": obligation["enforcement_id"],
        "projection_id": obligation["projection_id"],
        "rule_id": obligation["rule_id"],
        "revision": obligation["revision"],
        "evidence_type": obligation["evidence_type"],
    }
    mismatches = {
        key: {"expected": expected, "actual": evidence.get(key)}
        for key, expected in bindings.items()
        if evidence.get(key) != expected
    }
    if mismatches:
        return {
            "decision": "blocked",
            "enforcement_id": obligation["enforcement_id"],
            "diagnostics": [
                {
                    "code": "EVIDENCE_BINDING_MISMATCH",
                    "message": "evidence does not bind the current obligation",
                    "actual": mismatches,
                }
            ],
        }
    postcondition = evidence["postcondition"]
    if (
        not isinstance(postcondition, dict)
        or set(postcondition) != {"status", "observed"}
        or postcondition["status"] not in {"passed", "failed"}
    ):
        return {
            "decision": "blocked",
            "enforcement_id": obligation["enforcement_id"],
            "diagnostics": [
                {
                    "code": "EVIDENCE_POSTCONDITION_INVALID",
                    "message": (
                        "postcondition must have passed/failed status and observed data"
                    ),
                }
            ],
        }
    if postcondition["status"] == "failed":
        return {
            "decision": "blocked",
            "enforcement_id": obligation["enforcement_id"],
            "diagnostics": [
                {
                    "code": "GOVERNANCE_POSTCONDITION_FAILED",
                    "message": (
                        "external result did not satisfy the governance rule"
                    ),
                    "actual": postcondition["observed"],
                }
            ],
        }
    return {
        "decision": "satisfied",
        "enforcement_id": obligation["enforcement_id"],
        "evidence_digest": canonical_digest(evidence),
        "diagnostics": [],
    }


def ingest_load_result(
    state: dict[str, Any],
    load_result: dict[str, Any],
) -> dict[str, Any]:
    """Atomically prepare state changes for a ready LoadResult."""

    if load_result.get("status") != "ready" or load_result.get("diagnostics"):
        return {
            "status": "blocked",
            "changed": False,
            "state": state,
            "diagnostics": load_result.get("diagnostics")
            or [
                {
                    "code": "LOAD_RESULT_NOT_READY",
                    "message": "only a conflict-free LoadResult can be ingested",
                }
            ],
        }
    updated = deepcopy(state)
    for candidate in load_result["candidates"]:
        payload = {
            key: deepcopy(candidate[key])
            for key in ("domain", "directive", "scope", "sources")
        }
        current = updated["rules"].get(candidate["rule_id"])
        if current is not None:
            current_payload = {
                key: current[key]
                for key in ("domain", "directive", "scope", "sources")
            }
            if canonical_digest(current_payload) == canonical_digest(payload):
                continue
            operation_type = "update"
            base_revision = current["revision"]
        else:
            operation_type = "add"
            base_revision = 0
        operation_seed = {
            "load_result": load_result["result_digest"],
            "operation_type": operation_type,
            "rule_id": candidate["rule_id"],
            "payload": payload,
        }
        operation_id = "op-load-" + canonical_digest(operation_seed).split(
            ":", maxsplit=1
        )[1][:20]
        request = build_operation_request(
            operation_id,
            operation_type,
            candidate["rule_id"],
            base_revision=base_revision,
            payload=payload,
        )
        registered = register_operation(updated, request)
        if registered["status"] not in {"pending", "applied"}:
            return {
                "status": "blocked",
                "changed": False,
                "state": state,
                "diagnostics": registered["diagnostics"],
            }
        applied = apply_operation(registered["state"], operation_id)
        if applied["status"] != "applied":
            return {
                "status": "blocked",
                "changed": False,
                "state": state,
                "diagnostics": applied["diagnostics"],
            }
        updated = applied["state"]
    return {
        "status": "loaded",
        "changed": updated != state,
        "state": updated,
        "projection": compile_governance_projection(updated),
        "diagnostics": [],
    }


class GovernanceRepository:
    """Persist the authoritative state in one atomically replaced document."""

    def __init__(self, repository: Path) -> None:
        self.repository = repository.resolve()
        self.path = self.repository / GOVERNANCE_STATE_RELATIVE_PATH
        self.lock_path = self.path.with_suffix(".lock")

    @contextmanager
    def _locked(self):
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as stream:
            try:
                import fcntl
            except ImportError:  # pragma: no cover - Windows fallback
                yield
                return
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def _read_unlocked(self) -> dict[str, Any]:
        if not self.path.is_file():
            return empty_governance_state()
        document = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            raise ValueError("governance state must be an object")
        return document

    def read(self) -> dict[str, Any]:
        with self._locked():
            return self._read_unlocked()

    def _write(self, state: dict[str, Any]) -> None:
        payload = (
            json.dumps(
                state,
                allow_nan=False,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            dir=self.path.parent,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    def register(self, request: dict[str, Any]) -> dict[str, Any]:
        with self._locked():
            result = register_operation(self._read_unlocked(), request)
            if result["changed"]:
                self._write(result["state"])
            return result

    def apply(self, operation_id: str) -> dict[str, Any]:
        with self._locked():
            result = apply_operation(
                self._read_unlocked(), operation_id
            )
            if result["changed"]:
                self._write(result["state"])
            result["projection"] = compile_governance_projection(
                result["state"]
            )
            return result

    def cancel(self, operation_id: str | None = None) -> dict[str, Any]:
        with self._locked():
            result = cancel_operation(
                self._read_unlocked(), operation_id
            )
            if result["changed"]:
                self._write(result["state"])
            result["projection"] = compile_governance_projection(
                result["state"]
            )
            return result

    def ingest(self, load_result: dict[str, Any]) -> dict[str, Any]:
        with self._locked():
            result = ingest_load_result(
                self._read_unlocked(), load_result
            )
            if result["changed"]:
                self._write(result["state"])
            return result
