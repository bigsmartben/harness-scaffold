"""Separate delivery readiness, dispatch, and finalization states."""

from __future__ import annotations

from typing import Any

from .artifacts import digest_matches
from .automation import request_digest
from .branching import branch_is_controlled, default_branch_gate
from .contracts import runtime_artifact_is_valid
from .platform import platform_evidence_complete
from .runner import PlatformAdapter


def create_external_request(
    event: dict[str, Any], target_pipeline: str
) -> dict[str, Any]:
    """Record an external event without treating it as execution authority."""

    request = {"event": event, "target_pipeline": target_pipeline}
    return {
        "status": "blocked",
        "request": request,
        "request_digest": request_digest(request),
        "backend_calls": 0,
        "blocker_codes": ["HANDOFF_REQUIRED"],
    }


def _required_evidence_tasks(pipeline: dict[str, Any]) -> set[str]:
    return {
        task
        for stage in pipeline.get("stages", [])
        if stage.get("requires_evidence") is True
        for task in stage.get("tasks", [])
    }


def _confirmation_matches(
    request: dict[str, Any], confirmation: dict[str, Any] | None
) -> bool:
    return (
        isinstance(confirmation, dict)
        and runtime_artifact_is_valid(confirmation)
        and confirmation.get("artifact_type") == "confirmation"
        and confirmation.get("schema_version") == "0.3.0"
        and confirmation.get("confirmation_status") == "confirmed"
        and confirmation.get("request_digest") == request.get("request_digest")
    )


def evaluate_pipeline_readiness(
    pipeline: dict[str, Any],
    evidence: list[dict[str, Any]],
    request: dict[str, Any] | None,
    confirmation: dict[str, Any] | None,
    branch_gate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return blocked, confirmation-required, or ready-for-dispatch."""

    kind = pipeline.get("kind")
    if kind not in {"merge", "publish"}:
        return {
            "status": "blocked",
            "backend_calls": 0,
            "blocker_codes": ["CONFIG_INVALID"],
        }
    if (
        not isinstance(request, dict)
        or not runtime_artifact_is_valid(request)
        or request.get("artifact_type") != "task-request"
        or request.get("schema_version") != "0.3.0"
        or request.get("action_semantics") != kind
        or request.get("automation_level") != "critical"
        or request.get("policy_version") != "0.3.0"
        or not request.get("target")
        or request_digest(request) != request.get("request_digest")
    ):
        return {
            "status": "blocked",
            "backend_calls": 0,
            "blocker_codes": [
                "EVIDENCE_BINDING_MISMATCH",
                "HANDOFF_REQUIRED",
            ],
        }

    required = _required_evidence_tasks(pipeline)
    passed_by_task = {
        item.get("task_id"): item
        for item in evidence
        if isinstance(item, dict) and item.get("status") == "passed"
    }
    missing = sorted(required - passed_by_task.keys())
    if missing:
        return {
            "status": "blocked",
            "missing_tasks": missing,
            "backend_calls": 0,
            "blocker_codes": ["EVIDENCE_INCOMPLETE"],
        }
    mismatched = [
        task_id
        for task_id in sorted(required)
        if (
            not runtime_artifact_is_valid(passed_by_task[task_id])
            or not digest_matches(passed_by_task[task_id], "evidence_digest")
            or passed_by_task[task_id].get("grant_digest")
            != request.get("grant_digest")
            or passed_by_task[task_id].get("manifest_digest")
            != request.get("manifest_digest")
            or passed_by_task[task_id].get("selection_digest")
            != request.get("selection_digest")
            or passed_by_task[task_id].get("commit_sha")
            != request.get("commit_sha")
        )
    ]
    if mismatched:
        return {
            "status": "blocked",
            "missing_tasks": [],
            "backend_calls": 0,
            "blocker_codes": [
                "EVIDENCE_BINDING_MISMATCH",
                "HANDOFF_REQUIRED",
            ],
        }
    if kind == "publish" and (
        request.get("version") is None
        or request.get("artifact_digest") is None
        or request.get("environment") is None
    ):
        return {
            "status": "blocked",
            "missing_tasks": [],
            "backend_calls": 0,
            "blocker_codes": ["EVIDENCE_INCOMPLETE"],
        }
    controlled_target = (
        kind == "merge"
        and branch_is_controlled(
            str(request["target"]), "merge", branch_gate or default_branch_gate()
        )
    )
    if controlled_target and (
        pipeline.get("requires_independent_confirmation") is not True
        or not _confirmation_matches(request, confirmation)
    ):
        return {
            "status": "confirmation-required",
            "missing_tasks": [],
            "backend_calls": 0,
            "blocker_codes": [
                "CONTROLLED_BRANCH_GATE_REQUIRED",
                "HANDOFF_REQUIRED",
            ],
        }
    return {
        "status": "ready-for-dispatch",
        "missing_tasks": [],
        "backend_calls": 0,
        "blocker_codes": [],
    }


def dispatch_pipeline(
    readiness: dict[str, Any],
    task: dict[str, Any],
    request: dict[str, Any],
    adapter: PlatformAdapter,
) -> dict[str, Any]:
    """Call only prepare and dispatch after readiness succeeds."""

    if readiness.get("status") != "ready-for-dispatch":
        return {
            **readiness,
            "backend_calls": 0,
        }
    if (
        task.get("id") != request.get("task_id")
        or task.get("category") != request.get("action_semantics")
        or task.get("backend") != "github-actions"
        or not isinstance(task.get("source"), str)
        or not task.get("source")
    ):
        return {
            "status": "blocked",
            "backend_calls": 0,
            "blocker_codes": [
                "EVIDENCE_BINDING_MISMATCH",
                "HANDOFF_REQUIRED",
            ],
        }
    try:
        prepared = adapter.prepare(task, request)
        locator = adapter.dispatch(prepared)
    except Exception as exc:
        return {
            "status": "blocked",
            "backend_calls": 0,
            "blocker_codes": ["BACKEND_UNAVAILABLE"],
            "primary_error": str(exc),
        }
    return {
        "status": "dispatched",
        "backend_calls": 1,
        "blocker_codes": [],
        "locator": locator,
    }


def finalize_pipeline(
    pipeline: dict[str, Any],
    evidence: list[dict[str, Any]],
    request: dict[str, Any] | None,
    confirmation: dict[str, Any] | None,
    platform: dict[str, Any] | None,
    branch_gate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Finalize only with complete, request-bound Platform Evidence."""

    readiness = evaluate_pipeline_readiness(
        pipeline, evidence, request, confirmation, branch_gate
    )
    if readiness["status"] != "ready-for-dispatch":
        return readiness
    assert request is not None
    if not isinstance(platform, dict):
        return {
            "status": "blocked",
            "backend_calls": 0,
            "blocker_codes": ["EVIDENCE_INCOMPLETE"],
        }
    if not runtime_artifact_is_valid(platform):
        return {
            "status": "blocked",
            "backend_calls": 0,
            "blocker_codes": [
                "EVIDENCE_BINDING_MISMATCH",
                "HANDOFF_REQUIRED",
            ],
        }
    if (
        platform.get("request_digest") != request.get("request_digest")
        or platform.get("commit_sha") != request.get("commit_sha")
        or (
            request.get("artifact_digest") is not None
            and platform.get("artifact_digest") != request.get("artifact_digest")
        )
        or (
            pipeline.get("kind") == "merge"
            and platform.get("protected_ref") != request.get("target")
        )
        or (
            pipeline.get("kind") == "publish"
            and platform.get("protected_environment")
            != request.get("environment")
        )
    ):
        return {
            "status": "blocked",
            "backend_calls": 0,
            "blocker_codes": [
                "EVIDENCE_BINDING_MISMATCH",
                "HANDOFF_REQUIRED",
            ],
        }
    if not platform_evidence_complete(platform, pipeline["kind"], request):
        return {
            "status": "blocked",
            "backend_calls": 0,
            "blocker_codes": ["EVIDENCE_INCOMPLETE"],
        }
    return {
        "status": "passed",
        "backend_calls": 1,
        "blocker_codes": [],
        "platform": platform,
    }


def evaluate_merge_readiness(
    pipeline: dict[str, Any],
    evidence: list[dict[str, Any]],
    request: dict[str, Any] | None = None,
    confirmation: dict[str, Any] | None = None,
    branch_gate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return evaluate_pipeline_readiness(
        pipeline, evidence, request, confirmation, branch_gate
    )


def evaluate_publish_readiness(
    pipeline: dict[str, Any],
    request: dict[str, Any] | None,
    confirmation: dict[str, Any] | None,
    evidence: list[dict[str, Any]] | None = None,
    branch_gate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return evaluate_pipeline_readiness(
        pipeline, evidence or [], request, confirmation, branch_gate
    )
