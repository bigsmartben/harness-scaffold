"""Exact provider adapters for controlled delivery actions."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .artifacts import (
    SCHEMA_VERSION,
    attach_digest,
    canonical_digest,
    digest_matches,
)
from .branching import branch_action_blockers
from .codex_adapter import load_projection_bundle, runtime_state
from .decisions import task_decision_blockers
from .policy import load_project_config
from .workspace import workspace_state


CONTROLLED_DELIVERY_SEMANTICS = (
    "pull-request",
    "merge",
    "publish",
    "release",
    "deploy",
)

_TARGET_FIELDS: dict[str, tuple[set[str], set[str]]] = {
    "pull-request": (
        {
            "provider",
            "repository",
            "base_ref",
            "head_ref",
            "title",
            "body",
            "draft",
            "commit_sha",
        },
        set(),
    ),
    "merge": (
        {
            "provider",
            "repository",
            "pull_request_number",
            "method",
            "expected_head_sha",
        },
        set(),
    ),
    "publish": (
        {
            "provider",
            "repository",
            "package",
            "version",
            "registry",
            "artifact_digest",
        },
        set(),
    ),
    "release": (
        {
            "provider",
            "repository",
            "tag",
            "commit_sha",
            "title",
            "notes",
            "artifact_digests",
        },
        set(),
    ),
    "deploy": (
        {
            "provider",
            "repository",
            "environment",
            "commit_sha",
            "artifact_digest",
        },
        set(),
    ),
}

_REPOSITORY = re.compile(r"^[^/\s]+/[^/\s]+$")
_DIGEST = re.compile(r"^sha256:[a-f0-9]{64}$")


def _target_is_valid(semantics: str, target: dict[str, Any]) -> bool:
    fields = _TARGET_FIELDS.get(semantics)
    if fields is None:
        return False
    required, optional = fields
    if set(target) != required | (set(target) & optional):
        return False
    if not required.issubset(target):
        return False
    if target.get("provider") != "github":
        return False
    if not isinstance(target.get("repository"), str) or not _REPOSITORY.fullmatch(
        target["repository"]
    ):
        return False

    strings = {
        key
        for key in required
        if key
        not in {
            "draft",
            "pull_request_number",
            "artifact_digests",
        }
    }
    if any(
        not isinstance(target.get(key), str) or not target[key].strip()
        for key in strings
    ):
        return False
    if semantics == "pull-request" and not isinstance(target.get("draft"), bool):
        return False
    if semantics == "merge":
        if (
            not isinstance(target.get("pull_request_number"), int)
            or target["pull_request_number"] < 1
            or target.get("method") not in {"merge", "squash", "rebase"}
        ):
            return False
    if semantics in {"publish", "deploy"} and not _DIGEST.fullmatch(
        str(target.get("artifact_digest") or "")
    ):
        return False
    if semantics == "release":
        digests = target.get("artifact_digests")
        if (
            not isinstance(digests, list)
            or len(digests) != len(set(digests))
            or any(
                not isinstance(item, str) or not _DIGEST.fullmatch(item)
                for item in digests
            )
        ):
            return False
    return True


def _action(
    repository: Path,
    action_id: str,
) -> dict[str, Any] | None:
    bundle = load_projection_bundle(repository)
    if bundle is None:
        return None
    matches = [
        item
        for item in bundle["action_graph"].get("actions", [])
        if item.get("action_id") == action_id
    ]
    if len(matches) != 1:
        return None
    action = matches[0]
    if (
        action.get("domain") != "delivery"
        or action.get("boundary") != "controlled"
        or action.get("semantics") not in CONTROLLED_DELIVERY_SEMANTICS
        or action.get("binding_state") != "bound"
    ):
        return None
    return action


def platform_gate_blockers(
    evidence: dict[str, Any] | None,
    *,
    action_id: str,
    provider: str,
    repository: str,
    target_digest: str,
) -> list[str]:
    """Verify independent upstream platform-gate evidence."""

    if (
        not isinstance(evidence, dict)
        or not digest_matches(evidence, "evidence_digest")
        or evidence.get("artifact_type") != "platform-gate-evidence"
        or evidence.get("schema_version") != SCHEMA_VERSION
        or evidence.get("action_id") != action_id
        or evidence.get("provider") != provider
        or evidence.get("repository") != repository
        or evidence.get("target_digest") != target_digest
        or evidence.get("status") != "passed"
    ):
        return ["PLATFORM_GATE_REQUIRED", "HANDOFF_REQUIRED"]
    checks = evidence.get("checks")
    if (
        not isinstance(checks, list)
        or not checks
        or any(
            not isinstance(check, dict)
            or not isinstance(check.get("name"), str)
            or not check["name"]
            or check.get("status") != "passed"
            or not isinstance(check.get("source"), str)
            or not check["source"]
            or not isinstance(check.get("evidence_id"), str)
            or not check["evidence_id"]
            for check in checks
        )
    ):
        return ["PLATFORM_GATE_REQUIRED", "HANDOFF_REQUIRED"]
    return []


def build_platform_gate_evidence(
    *,
    action_id: str,
    target: dict[str, Any],
    checks: list[dict[str, Any]],
) -> dict[str, Any]:
    """Normalize queried platform facts into digest-bound gate evidence."""

    provider = target.get("provider")
    repository = target.get("repository")
    if (
        not isinstance(provider, str)
        or not isinstance(repository, str)
        or not action_id.startswith("delivery:")
    ):
        raise ValueError("PLATFORM_GATE_REQUIRED")
    document = attach_digest(
        {
            "artifact_type": "platform-gate-evidence",
            "schema_version": SCHEMA_VERSION,
            "action_id": action_id,
            "provider": provider,
            "repository": repository,
            "target_digest": canonical_digest(target),
            "status": "passed",
            "checks": checks,
        },
        "evidence_digest",
    )
    if platform_gate_blockers(
        document,
        action_id=action_id,
        provider=provider,
        repository=repository,
        target_digest=document["target_digest"],
    ):
        raise ValueError("PLATFORM_GATE_REQUIRED")
    return document


def delivery_decision_target(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "plan_digest": plan["plan_digest"],
        "action_id": plan["action_id"],
        "semantics": plan["semantics"],
        "provider": plan["target"]["provider"],
        "repository": plan["target"]["repository"],
        "target_digest": plan["target_digest"],
        "platform_evidence_digest": plan["platform_evidence"][
            "evidence_digest"
        ],
    }


def build_controlled_delivery_plan(
    repository: Path,
    *,
    action_id: str,
    target: dict[str, Any],
    platform_evidence: dict[str, Any] | None,
) -> dict[str, Any]:
    """Plan one source-backed remote action without invoking its provider."""

    root = repository.resolve()
    runtime = runtime_state(root)
    state = workspace_state(root)
    action = _action(root, action_id)
    blockers = set(runtime["blocker_codes"])
    semantics = str((action or {}).get("semantics") or "")
    target_digest = canonical_digest(target)
    if action is None:
        blockers.add("TOOL_BINDING_AMBIGUOUS")
    elif not _target_is_valid(semantics, target):
        blockers.add("GOVERNANCE_SCOPE_UNRESOLVED")
    elif semantics == "pull-request" and (
        target["head_ref"] != state["head_ref"]
        or target["commit_sha"] != state["base_commit"]
    ):
        blockers.add("GOVERNANCE_SCOPE_UNRESOLVED")
    elif semantics in {"release", "deploy"} and (
        target["commit_sha"] != state["base_commit"]
    ):
        blockers.add("GOVERNANCE_SCOPE_UNRESOLVED")
    if action is not None and _target_is_valid(semantics, target):
        blockers.update(
            platform_gate_blockers(
                platform_evidence,
                action_id=action_id,
                provider=target["provider"],
                repository=target["repository"],
                target_digest=target_digest,
            )
        )
    config = load_project_config(root)
    if config is not None and semantics:
        blockers.update(
            branch_action_blockers(
                state["head_ref"],
                semantics,
                config["branch_policy"],
            )
        )
    document = {
        "artifact_type": "controlled-delivery-plan",
        "schema_version": SCHEMA_VERSION,
        "projection_id": runtime.get("projection_id"),
        "workspace_digest": state["workspace_digest"],
        "action_id": action_id,
        "semantics": semantics,
        "action_digest": canonical_digest(action) if action is not None else None,
        "source_refs": list((action or {}).get("source_refs") or []),
        "target": target,
        "target_digest": target_digest,
        "platform_evidence": platform_evidence,
        "blocker_codes": sorted(blockers),
    }
    return attach_digest(document, "plan_digest")


def prepare_controlled_delivery_request(
    repository: Path,
    plan: dict[str, Any],
    *,
    decision: dict[str, Any] | None,
) -> dict[str, Any]:
    """Validate one plan and decision before the provider is called."""

    root = repository.resolve()
    if not digest_matches(plan, "plan_digest"):
        return {
            "status": "blocked",
            "blocker_codes": ["CONTROLLED_DELIVERY_PLAN_STALE"],
        }
    if plan.get("blocker_codes"):
        return {"status": "blocked", "blocker_codes": plan["blocker_codes"]}
    runtime = runtime_state(root)
    state = workspace_state(root)
    action = _action(root, str(plan.get("action_id") or ""))
    if (
        runtime["status"] != "active"
        or runtime["projection_id"] != plan.get("projection_id")
        or state["workspace_digest"] != plan.get("workspace_digest")
        or action is None
        or canonical_digest(action) != plan.get("action_digest")
        or action.get("semantics") != plan.get("semantics")
        or not _target_is_valid(
            str(plan.get("semantics") or ""),
            plan.get("target") or {},
        )
        or canonical_digest(plan.get("target")) != plan.get("target_digest")
    ):
        return {
            "status": "blocked",
            "blocker_codes": [
                "CONTROLLED_DELIVERY_PLAN_STALE",
                "HANDOFF_REQUIRED",
            ],
        }
    gate_blockers = platform_gate_blockers(
        plan.get("platform_evidence"),
        action_id=plan["action_id"],
        provider=plan["target"]["provider"],
        repository=plan["target"]["repository"],
        target_digest=plan["target_digest"],
    )
    if gate_blockers:
        return {"status": "blocked", "blocker_codes": gate_blockers}
    target = delivery_decision_target(plan)
    blockers = task_decision_blockers(
        decision,
        task_id=str((decision or {}).get("task_id") or ""),
        projection_id=str(runtime["projection_id"]),
        workspace_digest=state["workspace_digest"],
        exact_action=plan["action_id"],
        target=target,
    )
    if blockers:
        return {"status": "blocked", "blocker_codes": blockers}
    return {
        "status": "provider-required",
        "provider": plan["target"]["provider"],
        "operation": plan["semantics"],
        "request": {
            "action_id": plan["action_id"],
            "plan_digest": plan["plan_digest"],
            "target_digest": plan["target_digest"],
            "platform_evidence_digest": plan["platform_evidence"][
                "evidence_digest"
            ],
            **plan["target"],
        },
        "blocker_codes": [],
    }


def validate_controlled_delivery_receipt(
    plan: dict[str, Any],
    receipt: dict[str, Any],
) -> list[str]:
    """Validate provider evidence against the exact planned target."""

    if not digest_matches(plan, "plan_digest") or plan.get("blocker_codes"):
        return ["CONTROLLED_DELIVERY_PLAN_STALE"]
    target = plan["target"]
    if (
        receipt.get("status") != "succeeded"
        or receipt.get("provider") != target["provider"]
        or receipt.get("repository") != target["repository"]
        or receipt.get("action_id") != plan["action_id"]
        or receipt.get("target_digest") != plan["target_digest"]
    ):
        return ["REMOTE_DELIVERY_FAILED", "HANDOFF_REQUIRED"]

    semantics = plan["semantics"]
    evidence = receipt.get("evidence")
    if not isinstance(evidence, dict):
        return ["GOVERNANCE_EVIDENCE_INCOMPLETE", "HANDOFF_REQUIRED"]
    checks: list[bool]
    if semantics == "pull-request":
        checks = [
            isinstance(evidence.get("pull_request_number"), int)
            and evidence["pull_request_number"] > 0,
            isinstance(evidence.get("url"), str)
            and evidence["url"].startswith("https://"),
            evidence.get("base_ref") == target["base_ref"],
            evidence.get("head_ref") == target["head_ref"],
            evidence.get("head_sha") == target["commit_sha"],
            evidence.get("draft") == target["draft"],
        ]
    elif semantics == "merge":
        checks = [
            evidence.get("pull_request_number") == target["pull_request_number"],
            evidence.get("head_sha") == target["expected_head_sha"],
            isinstance(evidence.get("merge_commit_sha"), str)
            and bool(evidence["merge_commit_sha"]),
            evidence.get("method") == target["method"],
        ]
    elif semantics == "publish":
        checks = [
            evidence.get(key) == target[key]
            for key in ("package", "version", "registry", "artifact_digest")
        ]
    elif semantics == "release":
        checks = [
            evidence.get("tag") == target["tag"],
            evidence.get("commit_sha") == target["commit_sha"],
            sorted(evidence.get("artifact_digests") or [])
            == sorted(target["artifact_digests"]),
            isinstance(evidence.get("url"), str)
            and evidence["url"].startswith("https://"),
        ]
    elif semantics == "deploy":
        checks = [
            evidence.get(key) == target[key]
            for key in ("environment", "commit_sha", "artifact_digest")
        ] + [
            isinstance(evidence.get("deployment_id"), (str, int))
            and bool(str(evidence["deployment_id"]))
        ]
    else:
        checks = [False]
    if not all(checks):
        return ["GOVERNANCE_EVIDENCE_INCOMPLETE", "HANDOFF_REQUIRED"]
    return []


def execute_controlled_delivery_plan(
    repository: Path,
    plan: dict[str, Any],
    *,
    decision: dict[str, Any] | None,
    provider_writer: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    """Call one injected provider adapter exactly once after all local gates pass."""

    prepared = prepare_controlled_delivery_request(
        repository,
        plan,
        decision=decision,
    )
    if prepared["status"] != "provider-required":
        return prepared
    try:
        receipt = provider_writer(prepared["request"])
    except Exception as exc:
        return {
            "status": "failed",
            "blocker_codes": ["REMOTE_DELIVERY_FAILED", "HANDOFF_REQUIRED"],
            "summary": str(exc),
        }
    blockers = validate_controlled_delivery_receipt(plan, receipt)
    if blockers:
        return {"status": "failed", "blocker_codes": blockers}
    return attach_digest(
        {
            "status": "delivered",
            "action_id": plan["action_id"],
            "semantics": plan["semantics"],
            "receipt": receipt,
            "blocker_codes": [],
        },
        "evidence_digest",
    )
