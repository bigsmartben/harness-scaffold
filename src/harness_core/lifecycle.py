"""Typed governance rule lifecycle and operation contracts."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from .artifacts import canonical_digest
from .model import (
    CONTRACT_VERSION,
    DOMAINS,
    RULE_ID_MAX_LENGTH,
    RULE_ID_PATTERN,
)


RULE_STATUSES = ("enabled", "disabled")
OPERATION_TYPES = ("add", "update", "disable", "enable", "delete")
OPERATION_STATUSES = ("pending", "applied", "cancelled", "rejected")
_SHA256_PATTERN = re.compile(r"^sha256:[a-f0-9]{64}$")


def empty_governance_state() -> dict[str, Any]:
    """Return a new authoritative state document."""

    return {
        "contract_version": CONTRACT_VERSION,
        "state_revision": 0,
        "rules": {},
        "deleted_rules": {},
        "operations": {},
    }


def governance_rule_digest(state: dict[str, Any]) -> str:
    """Digest only current rules, excluding operations and tombstones."""

    return canonical_digest(state["rules"])


def _diagnostic(
    code: str,
    message: str,
    *,
    operation_id: str | None = None,
    rule_id: str | None = None,
    expected: Any | None = None,
    actual: Any | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {"code": code, "message": message}
    for name, value in (
        ("operation_id", operation_id),
        ("rule_id", rule_id),
        ("expected", expected),
        ("actual", actual),
    ):
        if value is not None:
            result[name] = value
    return result


def _result(
    state: dict[str, Any],
    *,
    status: str,
    operation_id: str | None = None,
    changed: bool = False,
    diagnostic: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "operation_id": operation_id,
        "changed": changed,
        "state": state,
        "rule_digest": governance_rule_digest(state),
        "diagnostics": [] if diagnostic is None else [diagnostic],
    }


def _valid_identifier(value: Any, prefix: str) -> bool:
    if not isinstance(value, str) or not value.startswith(prefix):
        return False
    suffix = value[len(prefix) :]
    if not suffix or len(value) > RULE_ID_MAX_LENGTH + len(prefix):
        return False
    return re.fullmatch(RULE_ID_PATTERN, suffix) is not None


def _valid_scope(scope: Any) -> bool:
    return (
        isinstance(scope, list)
        and bool(scope)
        and len(scope) == len(set(scope))
        and all(isinstance(item, str) and item for item in scope)
    )


def _validate_payload(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return _diagnostic(
            "OPERATION_PAYLOAD_INVALID",
            "add and update require an object payload",
            expected=["domain", "directive", "scope", "sources"],
            actual=type(payload).__name__,
        )
    expected_fields = {"domain", "directive", "scope", "sources"}
    if set(payload) != expected_fields:
        return _diagnostic(
            "OPERATION_PAYLOAD_INVALID",
            "payload fields must match the rule content contract",
            expected=sorted(expected_fields),
            actual=sorted(payload),
        )
    if payload["domain"] not in DOMAINS:
        return _diagnostic(
            "RULE_DOMAIN_INVALID",
            "rule domain is not part of the fixed governance model",
            expected=list(DOMAINS),
            actual=payload["domain"],
        )
    if not isinstance(payload["directive"], str) or not payload["directive"].strip():
        return _diagnostic(
            "RULE_DIRECTIVE_INVALID",
            "rule directive must be a non-empty string",
        )
    if not _valid_scope(payload["scope"]):
        return _diagnostic(
            "RULE_SCOPE_INVALID",
            "rule scope must be a non-empty unique string array",
        )
    sources = payload["sources"]
    if not isinstance(sources, list) or not sources:
        return _diagnostic(
            "RULE_SOURCES_INVALID",
            "rule sources must contain at least one traceable source",
        )
    expected_source_fields = {"source_type", "reference", "digest"}
    for source in sources:
        if (
            not isinstance(source, dict)
            or set(source) != expected_source_fields
            or source.get("source_type")
            not in {"repository_fact", "governance_source", "user_intent"}
            or not isinstance(source.get("reference"), str)
            or not source["reference"]
            or not isinstance(source.get("digest"), str)
            or _SHA256_PATTERN.fullmatch(source["digest"]) is None
        ):
            return _diagnostic(
                "RULE_SOURCES_INVALID",
                "each source must have a type, reference, and SHA-256 digest",
            )
    return None


def validate_operation_request(request: Any) -> list[dict[str, Any]]:
    """Validate one typed operation request with stable diagnostics."""

    required = {
        "contract_version",
        "operation_id",
        "operation_type",
        "target_rule_id",
        "base_revision",
        "payload",
        "payload_digest",
    }
    if not isinstance(request, dict):
        return [
            _diagnostic(
                "OPERATION_REQUEST_INVALID",
                "operation request must be an object",
                expected=sorted(required),
                actual=type(request).__name__,
            )
        ]
    if set(request) != required:
        return [
            _diagnostic(
                "OPERATION_REQUEST_INVALID",
                "operation request fields do not match the contract",
                expected=sorted(required),
                actual=sorted(request),
            )
        ]
    operation_id = request["operation_id"]
    rule_id = request["target_rule_id"]
    if request["contract_version"] != CONTRACT_VERSION:
        return [
            _diagnostic(
                "CONTRACT_VERSION_UNSUPPORTED",
                "operation contract version is unsupported",
                operation_id=operation_id,
                expected=CONTRACT_VERSION,
                actual=request["contract_version"],
            )
        ]
    if not _valid_identifier(operation_id, "op-"):
        return [
            _diagnostic(
                "OPERATION_ID_INVALID",
                "operation_id must be unique lowercase kebab-case with an op- prefix",
                actual=operation_id,
            )
        ]
    if request["operation_type"] not in OPERATION_TYPES:
        return [
            _diagnostic(
                "OPERATION_TYPE_INVALID",
                "operation_type is unsupported",
                operation_id=operation_id,
                expected=list(OPERATION_TYPES),
                actual=request["operation_type"],
            )
        ]
    if not _valid_identifier(rule_id, ""):
        return [
            _diagnostic(
                "RULE_ID_INVALID",
                "target_rule_id must be lowercase kebab-case",
                operation_id=operation_id,
                actual=rule_id,
            )
        ]
    if not isinstance(request["base_revision"], int) or request["base_revision"] < 0:
        return [
            _diagnostic(
                "BASE_REVISION_INVALID",
                "base_revision must be a non-negative integer",
                operation_id=operation_id,
                rule_id=rule_id,
            )
        ]
    operation_type = request["operation_type"]
    if operation_type in {"add", "update"}:
        payload_issue = _validate_payload(request["payload"])
        if payload_issue is not None:
            payload_issue["operation_id"] = operation_id
            payload_issue["rule_id"] = rule_id
            return [payload_issue]
    elif request["payload"] is not None:
        return [
            _diagnostic(
                "OPERATION_PAYLOAD_FORBIDDEN",
                f"{operation_type} does not accept a payload",
                operation_id=operation_id,
                rule_id=rule_id,
                expected=None,
                actual=request["payload"],
            )
        ]
    expected_digest = canonical_digest(request["payload"])
    if request["payload_digest"] != expected_digest:
        return [
            _diagnostic(
                "OPERATION_PAYLOAD_DIGEST_MISMATCH",
                "payload_digest does not match the canonical payload",
                operation_id=operation_id,
                rule_id=rule_id,
                expected=expected_digest,
                actual=request["payload_digest"],
            )
        ]
    return []


def build_operation_request(
    operation_id: str,
    operation_type: str,
    target_rule_id: str,
    *,
    base_revision: int,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a canonical request; validation remains the caller's responsibility."""

    normalized_payload = deepcopy(payload)
    return {
        "contract_version": CONTRACT_VERSION,
        "operation_id": operation_id,
        "operation_type": operation_type,
        "target_rule_id": target_rule_id,
        "base_revision": base_revision,
        "payload": normalized_payload,
        "payload_digest": canonical_digest(normalized_payload),
    }


def register_operation(
    state: dict[str, Any],
    request: dict[str, Any],
) -> dict[str, Any]:
    """Register a pending operation without changing any rule."""

    issues = validate_operation_request(request)
    if issues:
        return _result(state, status="rejected", diagnostic=issues[0])
    operation_id = request["operation_id"]
    existing = state["operations"].get(operation_id)
    if existing is not None:
        if existing["request"] == request:
            return _result(
                state,
                status=existing["status"],
                operation_id=operation_id,
            )
        return _result(
            state,
            status="rejected",
            operation_id=operation_id,
            diagnostic=_diagnostic(
                "OPERATION_ID_CONFLICT",
                "operation_id is already bound to a different request",
                operation_id=operation_id,
            ),
        )
    updated = deepcopy(state)
    updated["operations"][operation_id] = {
        "request": deepcopy(request),
        "status": "pending",
        "diagnostic": None,
    }
    return _result(
        updated,
        status="pending",
        operation_id=operation_id,
        changed=True,
    )


def _precondition_diagnostic(
    state: dict[str, Any],
    request: dict[str, Any],
) -> dict[str, Any] | None:
    operation_type = request["operation_type"]
    rule_id = request["target_rule_id"]
    rule = state["rules"].get(rule_id)
    if operation_type == "add":
        if rule is not None:
            return _diagnostic(
                "RULE_ALREADY_EXISTS",
                "add target already exists in the current rule collection",
                rule_id=rule_id,
            )
        if rule_id in state["deleted_rules"]:
            return _diagnostic(
                "RULE_ID_RETIRED",
                "deleted rule identities cannot be silently reused",
                rule_id=rule_id,
            )
        if request["base_revision"] != 0:
            return _diagnostic(
                "BASE_REVISION_CONFLICT",
                "add requires base_revision 0",
                rule_id=rule_id,
                expected=0,
                actual=request["base_revision"],
            )
        return None
    if rule is None:
        return _diagnostic(
            "RULE_NOT_FOUND",
            "target rule is not in the current rule collection",
            rule_id=rule_id,
        )
    if request["base_revision"] != rule["revision"]:
        return _diagnostic(
            "BASE_REVISION_CONFLICT",
            "rule changed after the request base revision",
            rule_id=rule_id,
            expected=rule["revision"],
            actual=request["base_revision"],
        )
    if operation_type == "disable" and rule["status"] == "disabled":
        return _diagnostic(
            "RULE_ALREADY_DISABLED",
            "rule is already disabled",
            rule_id=rule_id,
        )
    if operation_type == "enable" and rule["status"] == "enabled":
        return _diagnostic(
            "RULE_ALREADY_ENABLED",
            "rule is already enabled",
            rule_id=rule_id,
        )
    return None


def _history_entry(
    operation_id: str,
    operation_type: str,
    rule: dict[str, Any],
) -> dict[str, Any]:
    return {
        "operation_id": operation_id,
        "operation_type": operation_type,
        "revision": rule["revision"],
        "status": rule["status"],
        "domain": rule["domain"],
        "directive": rule["directive"],
        "scope": deepcopy(rule["scope"]),
        "sources": deepcopy(rule["sources"]),
    }


def apply_operation(state: dict[str, Any], operation_id: str) -> dict[str, Any]:
    """Atomically apply one pending operation to a copied state."""

    operation = state["operations"].get(operation_id)
    if operation is None:
        return _result(
            state,
            status="rejected",
            operation_id=operation_id,
            diagnostic=_diagnostic(
                "OPERATION_NOT_FOUND",
                "operation_id is not registered",
                operation_id=operation_id,
            ),
        )
    if operation["status"] == "applied":
        return _result(state, status="applied", operation_id=operation_id)
    if operation["status"] == "cancelled":
        return _result(
            state,
            status="rejected",
            operation_id=operation_id,
            diagnostic=_diagnostic(
                "OPERATION_CANCELLED",
                "cancelled operation cannot be applied",
                operation_id=operation_id,
            ),
        )
    if operation["status"] == "rejected":
        return _result(
            state,
            status="rejected",
            operation_id=operation_id,
            diagnostic=operation["diagnostic"],
        )

    request = operation["request"]
    diagnostic = _precondition_diagnostic(state, request)
    if diagnostic is not None:
        updated = deepcopy(state)
        updated_operation = updated["operations"][operation_id]
        updated_operation["status"] = "rejected"
        updated_operation["diagnostic"] = diagnostic
        return _result(
            updated,
            status="rejected",
            operation_id=operation_id,
            changed=True,
            diagnostic=diagnostic,
        )

    updated = deepcopy(state)
    request = updated["operations"][operation_id]["request"]
    operation_type = request["operation_type"]
    rule_id = request["target_rule_id"]
    if operation_type == "add":
        payload = deepcopy(request["payload"])
        rule = {
            "rule_id": rule_id,
            **payload,
            "status": "enabled",
            "revision": 1,
            "history": [],
        }
        rule["history"].append(_history_entry(operation_id, "add", rule))
        updated["rules"][rule_id] = rule
    else:
        rule = updated["rules"][rule_id]
        rule["revision"] += 1
        if operation_type == "update":
            payload = request["payload"]
            rule.update(deepcopy(payload))
        elif operation_type == "disable":
            rule["status"] = "disabled"
        elif operation_type == "enable":
            rule["status"] = "enabled"
        rule["history"].append(
            _history_entry(operation_id, operation_type, rule)
        )
        if operation_type == "delete":
            tombstone = deepcopy(rule)
            tombstone["deleted_by"] = operation_id
            tombstone["deleted_revision"] = rule["revision"]
            updated["deleted_rules"][rule_id] = tombstone
            del updated["rules"][rule_id]
    updated["state_revision"] += 1
    updated["operations"][operation_id]["status"] = "applied"
    return _result(
        updated,
        status="applied",
        operation_id=operation_id,
        changed=True,
    )


def cancel_operation(
    state: dict[str, Any],
    operation_id: str | None = None,
) -> dict[str, Any]:
    """Cancel one pending operation while preserving current rules byte-for-byte."""

    if operation_id is None:
        candidates = sorted(
            identifier
            for identifier, operation in state["operations"].items()
            if operation["status"] == "pending"
        )
        if len(candidates) != 1:
            return _result(
                state,
                status="rejected",
                diagnostic=_diagnostic(
                    "CANCEL_TARGET_AMBIGUOUS",
                    "cancel current requires exactly one pending operation",
                    expected=1,
                    actual=len(candidates),
                ),
            )
        operation_id = candidates[0]
    operation = state["operations"].get(operation_id)
    if operation is None:
        return _result(
            state,
            status="rejected",
            operation_id=operation_id,
            diagnostic=_diagnostic(
                "OPERATION_NOT_FOUND",
                "operation_id is not registered",
                operation_id=operation_id,
            ),
        )
    if operation["status"] == "cancelled":
        return _result(state, status="cancelled", operation_id=operation_id)
    if operation["status"] == "applied":
        return _result(
            state,
            status="rejected",
            operation_id=operation_id,
            diagnostic=_diagnostic(
                "OPERATION_ALREADY_COMMITTED",
                "applied operation cannot be cancelled or implicitly rolled back",
                operation_id=operation_id,
            ),
        )
    if operation["status"] == "rejected":
        return _result(
            state,
            status="rejected",
            operation_id=operation_id,
            diagnostic=operation["diagnostic"],
        )
    updated = deepcopy(state)
    updated["operations"][operation_id]["status"] = "cancelled"
    return _result(
        updated,
        status="cancelled",
        operation_id=operation_id,
        changed=True,
    )
