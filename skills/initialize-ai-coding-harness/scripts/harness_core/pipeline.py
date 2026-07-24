"""Evaluate Merge and Publish pipeline gates."""

from __future__ import annotations

from typing import Any, Callable

from .automation import request_digest


def create_external_request(
    event: dict[str, Any], target_pipeline: str
) -> dict[str, Any]:
    request = {
        "event": event,
        "target_pipeline": target_pipeline,
    }
    return {
        "status": "blocked",
        "request": request,
        "request_digest": request_digest(request),
        "backend_calls": 0,
        "blocker_codes": ["HANDOFF_REQUIRED"],
    }


def evaluate_merge(
    pipeline: dict[str, Any],
    evidence: list[dict[str, Any]],
    request: dict[str, Any] | None = None,
    confirmation: dict[str, Any] | None = None,
    platform: dict[str, Any] | None = None,
) -> dict[str, Any]:
    passed = {
        item.get("task_id")
        for item in evidence
        if item.get("status") == "passed"
        and item.get("change_manifest")
        and item.get("selection")
    }
    required = {
        task
        for stage in pipeline.get("stages", [])
        if stage.get("requires_evidence", False)
        for task in stage.get("tasks", [])
    }
    missing = sorted(required - passed)
    if missing:
        return {
            "status": "blocked",
            "missing_tasks": missing,
            "backend_calls": 0,
            "blocker_codes": ["EVIDENCE_INCOMPLETE"],
        }
    if (
        request is None
        or confirmation is None
        or confirmation.get("confirmed") is not True
        or confirmation.get("request_digest") != request_digest(request)
    ):
        return {
            "status": "confirmation-required",
            "missing_tasks": [],
            "backend_calls": 0,
            "blocker_codes": ["HANDOFF_REQUIRED"],
        }
    if not platform or platform.get("required_checks") != "passed":
        return {
            "status": "blocked",
            "missing_tasks": [],
            "backend_calls": 0,
            "blocker_codes": ["EVIDENCE_INCOMPLETE"],
        }
    return {
        "status": "passed",
        "missing_tasks": [],
        "backend_calls": 1,
        "blocker_codes": [],
        "platform": platform,
    }


def execute_publish(
    pipeline: dict[str, Any],
    request: dict[str, Any],
    confirmation: dict[str, Any] | None,
    backend: Callable[[], Any],
    platform: dict[str, Any] | None = None,
) -> dict[str, Any]:
    expected = request_digest(request)
    if (
        pipeline.get("requires_independent_confirmation") is not True
        or confirmation is None
        or confirmation.get("request_digest") != expected
        or confirmation.get("confirmed") is not True
    ):
        return {
            "status": "blocked",
            "backend_calls": 0,
            "blocker_codes": ["PUBLISH_CONFIRMATION_REQUIRED"],
        }
    if (
        not platform
        or platform.get("approval_status") != "approved"
        or not platform.get("workflow")
        or not platform.get("commit_sha")
        or not platform.get("protected_environment")
    ):
        return {
            "status": "blocked",
            "backend_calls": 0,
            "blocker_codes": ["EVIDENCE_INCOMPLETE"],
        }
    result = backend()
    return {
        "status": "passed",
        "backend_calls": 1,
        "blocker_codes": [],
        "result": result,
        "platform": platform,
    }
