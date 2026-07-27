"""Deterministic G0-G7 governance gate engine."""

from __future__ import annotations

from copy import deepcopy
from pathlib import PurePosixPath
from typing import Any

from .artifacts import (
    GOVERNANCE_SCHEMA_VERSION,
    attach_digest,
    canonical_digest,
    verify_digest,
)


GATE_IDS = ("G0", "G1", "G2", "G3", "G4", "G5", "G6", "G7")
_DELIVERY_ACTIONS = {
    "push",
    "pull-request",
    "merge",
    "publish",
    "release",
    "deploy",
}


def create_work_grant(
    projection_id: str,
    objective: str,
    scope: list[str],
    *,
    audiences: list[str] | None = None,
) -> dict[str, Any]:
    """Create a reusable Work Grant bound to one projection and write scope."""

    document = {
        "artifact_type": "governance-work-grant",
        "schema_version": GOVERNANCE_SCHEMA_VERSION,
        "projection_id": projection_id,
        "objective": objective,
        "scope": sorted(set(path.replace("\\", "/") for path in scope)),
        "audiences": sorted(set(audiences or ["maintainer"])),
        "standing_policy": {
            "routine": "none",
            "scope_expansion": "once_per_change_set",
            "critical_external_action": "once_per_delivery",
        },
    }
    return attach_digest(document, "grant_digest")


def create_action_request(
    projection_id: str,
    grant: dict[str, Any],
    action_id: str,
    *,
    audience: str = "maintainer",
    scope: list[str] | None = None,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a typed request; arbitrary invocation overrides are rejected."""

    if (
        not verify_digest(grant, "grant_digest")
        or grant.get("projection_id") != projection_id
        or audience not in grant.get("audiences", [])
    ):
        raise ValueError("Work Grant is invalid or does not authorize this request")
    supplied = parameters or {}
    forbidden = {"command", "argv", "cwd", "environment", "env"}
    if forbidden.intersection(supplied):
        raise ValueError("Action parameters cannot override invocation bindings")
    document = {
        "artifact_type": "action-request",
        "schema_version": GOVERNANCE_SCHEMA_VERSION,
        "projection_id": projection_id,
        "grant_digest": grant["grant_digest"],
        "action_id": action_id,
        "audience": audience,
        "scope": sorted(set(scope or grant.get("scope", []))),
        "parameters": deepcopy(supplied),
    }
    return attach_digest(document, "request_digest")


def create_confirmation_package(
    projection_id: str,
    request_digests: list[str],
    *,
    kind: str,
    scope: list[str],
    decision: str,
) -> dict[str, Any]:
    """Aggregate one scope-change or delivery confirmation package."""

    if kind not in {"change-set", "delivery"}:
        raise ValueError("confirmation kind must be change-set or delivery")
    if decision not in {"approved", "rejected"}:
        raise ValueError("confirmation decision must be approved or rejected")
    document = {
        "artifact_type": "confirmation-package",
        "schema_version": GOVERNANCE_SCHEMA_VERSION,
        "projection_id": projection_id,
        "kind": kind,
        "request_digests": sorted(set(request_digests)),
        "scope": sorted(set(scope)),
        "decision": decision,
    }
    return attach_digest(document, "confirmation_digest")


def _in_scope(path: str, allowed: list[str]) -> bool:
    normalized = PurePosixPath(path.replace("\\", "/"))
    for candidate in allowed:
        base = candidate.replace("\\", "/").rstrip("/")
        if base in {"", "."}:
            return True
        if normalized == PurePosixPath(base):
            return True
        if str(normalized).startswith(f"{base}/"):
            return True
    return False


def _gate(
    gate_id: str,
    passed: bool,
    blocker_code: str | None = None,
    *,
    pending: bool = False,
) -> dict[str, Any]:
    return {
        "gate_id": gate_id,
        "status": "pending" if pending else "passed" if passed else "blocked",
        "blocker_codes": [] if passed or pending else [str(blocker_code)],
    }


def evaluate_gates(
    *,
    projection_lock: dict[str, Any],
    action_graph: dict[str, Any],
    rules: dict[str, Any],
    grant: dict[str, Any],
    request: dict[str, Any],
    current_snapshot_digest: str,
    confirmation: dict[str, Any] | None = None,
    invocation_channel: str = "harness",
    postcondition_result: dict[str, Any] | None = None,
    final_snapshot_digest: str | None = None,
) -> dict[str, Any]:
    """Evaluate all gates at once and return a complete blocker packet."""

    projection_id = projection_lock.get("projection_id")
    action = next(
        (
            item
            for item in action_graph.get("actions", [])
            if item.get("action_id") == request.get("action_id")
        ),
        None,
    )
    rule = next(
        (
            item
            for item in rules.get("rules", [])
            if item.get("action_id") == request.get("action_id")
            and item.get("audience") == request.get("audience")
        ),
        None,
    )

    same_projection = all(
        value == projection_id
        for value in (
            request.get("projection_id"),
            grant.get("projection_id"),
            rules.get("projection_id"),
        )
    )
    projection_artifacts_valid = (
        verify_digest(projection_lock, "projection_lock_digest")
        and verify_digest(action_graph, "action_graph_digest")
        and verify_digest(rules, "rules_digest")
    )
    g0 = (
        projection_artifacts_valid
        and same_projection
        and current_snapshot_digest == projection_lock.get("snapshot_digest")
        and projection_lock.get("ready") is True
    )
    g1 = bool(rule and rule.get("source_refs"))
    g2 = bool(action and rule and not action_graph.get("blockers"))
    invocation = action.get("invocation", {}) if action else {}
    g3 = bool(
        action
        and (
            (
                isinstance(invocation.get("argv"), list)
                and invocation.get("argv")
                and isinstance(invocation.get("cwd"), str)
            )
            or (
                isinstance(invocation.get("adapter"), str)
                and isinstance(invocation.get("workflow"), str)
            )
        )
    )

    request_scope = request.get("scope", [])
    grant_scope = grant.get("scope", [])
    scope_valid = bool(request_scope) and all(
        _in_scope(path, grant_scope) for path in request_scope
    )
    grant_valid = (
        verify_digest(grant, "grant_digest")
        and verify_digest(request, "request_digest")
        and request.get("grant_digest") == grant.get("grant_digest")
        and request.get("audience") in grant.get("audiences", [])
    )

    semantics = action.get("semantics") if action else None
    policy = rule.get("confirmation_policy") if rule else None
    confirmation_required = not scope_valid or semantics in _DELIVERY_ACTIONS
    confirmation_matches = bool(
        confirmation
        and verify_digest(confirmation, "confirmation_digest")
        and confirmation.get("projection_id") == projection_id
        and request.get("request_digest") in confirmation.get("request_digests", [])
        and confirmation.get("decision") == "approved"
        and (
            (not scope_valid and confirmation.get("kind") == "change-set")
            or (semantics in _DELIVERY_ACTIONS and confirmation.get("kind") == "delivery")
        )
    )
    known_policy = policy in {
        "none",
        "once_per_change_set",
        "once_per_delivery",
    }
    g4 = grant_valid and known_policy and (
        (scope_valid and not confirmation_required) or confirmation_matches
    )
    g5 = invocation_channel == "harness"
    g6_pending = postcondition_result is None
    g6 = bool(
        postcondition_result
        and postcondition_result.get("status") == "passed"
        and not postcondition_result.get("blocker_codes")
    )
    g7_pending = final_snapshot_digest is None
    g7 = bool(
        final_snapshot_digest
        and final_snapshot_digest == current_snapshot_digest
    )

    gates = [
        _gate("G0", g0, "GOVERNANCE_PROJECTION_STALE"),
        _gate("G1", g1, "GOVERNANCE_SOURCE_MISSING"),
        _gate("G2", g2, "GOVERNANCE_COVERAGE_INCOMPLETE"),
        _gate("G3", g3, "TOOL_BINDING_AMBIGUOUS"),
        _gate("G4", g4, "GOVERNANCE_PRECONDITION_FAILED"),
        _gate("G5", g5, "INVOCATION_BYPASS_ATTEMPT"),
        _gate(
            "G6",
            g6,
            "GOVERNANCE_EVIDENCE_INCOMPLETE",
            pending=g6_pending,
        ),
        _gate(
            "G7",
            g7,
            "GOVERNANCE_DRIFT_DETECTED",
            pending=g7_pending,
        ),
    ]
    blocker_codes = sorted(
        {
            code
            for gate in gates
            for code in gate["blocker_codes"]
        }
    )
    if blocker_codes:
        blocker_codes.append("HANDOFF_REQUIRED")
    document = {
        "artifact_type": "gate-decision",
        "schema_version": GOVERNANCE_SCHEMA_VERSION,
        "projection_id": projection_id,
        "request_digest": request.get("request_digest"),
        "gates": gates,
        "status": (
            "blocked"
            if blocker_codes
            else "pending"
            if any(gate["status"] == "pending" for gate in gates)
            else "passed"
        ),
        "confirmation_required": confirmation_required,
        "blocker_codes": blocker_codes,
        "blocker_packet_digest": canonical_digest(blocker_codes),
    }
    return attach_digest(document, "decision_digest")
