"""Classify CI/CD task automation independently from its invocation channel."""

from __future__ import annotations

import hashlib
import json
from typing import Any


AUTOMATION_LEVELS = ("routine", "expensive", "critical")
CRITICAL_CATEGORIES = {"push", "merge", "publish", "release", "deploy"}
EXPENSIVE_VALIDATION_LEVELS = {"integration", "full"}


def request_digest(request: dict[str, Any]) -> str:
    payload = json.dumps(request, sort_keys=True, separators=(",", ":")).encode()
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def effective_automation(
    task: dict[str, Any], validation_level: str | None = None
) -> dict[str, Any]:
    """Return the effective level and whether this invocation may be automatic."""

    declared = task.get("automation_level")
    category = task.get("category")
    errors: list[str] = []
    if declared not in AUTOMATION_LEVELS:
        errors.append("automation_level is missing or invalid")
        effective = "confirmation-required"
    else:
        effective = declared
    if category in CRITICAL_CATEGORIES and declared != "critical":
        errors.append(f"{category} tasks must use critical automation")
        effective = "critical"
    if (
        validation_level in EXPENSIVE_VALIDATION_LEVELS
        and effective != "critical"
    ):
        effective = "expensive"
    auto_allowed = (
        effective == "routine"
        and task.get("auto_allowed") is True
        and not errors
    )
    return {
        "declared_level": declared,
        "automation_level": effective,
        "auto_allowed": auto_allowed,
        "confirmation_required": not auto_allowed,
        "configuration_errors": errors,
    }


def resolve_action_policy(
    tool_id: str,
    tools: dict[str, Any],
    tasks: dict[str, Any],
    validation_level: str | None = None,
) -> dict[str, Any]:
    """Resolve an action through task_ref so channel type cannot alter its gate."""

    tool = next(
        (item for item in tools.get("tools", []) if item.get("id") == tool_id),
        None,
    )
    if tool is None:
        return {
            "status": "blocked",
            "blocker_codes": ["TOOL_NOT_REGISTERED"],
        }
    if tool.get("invocation_mode") == "direct":
        return {
            "status": "direct",
            "tool_id": tool_id,
            "channel": tool.get("type"),
            "confirmation_required": False,
            "blocker_codes": [],
        }
    task_ref = tool.get("task_ref")
    task = next(
        (item for item in tasks.get("tasks", []) if item.get("id") == task_ref),
        None,
    )
    if task is None:
        return {
            "status": "blocked",
            "tool_id": tool_id,
            "channel": tool.get("type"),
            "blocker_codes": ["CONFIG_INVALID"],
        }
    automation = effective_automation(task, validation_level)
    return {
        "status": (
            "automatic"
            if automation["auto_allowed"]
            else "confirmation-required"
        ),
        "tool_id": tool_id,
        "channel": tool.get("type"),
        "task_id": task_ref,
        **automation,
        "blocker_codes": (
            ["CONFIG_INVALID", "HANDOFF_REQUIRED"]
            if automation["configuration_errors"]
            else []
            if automation["auto_allowed"]
            else ["HANDOFF_REQUIRED"]
        ),
    }


def create_task_request(
    task: dict[str, Any],
    validation_level: str,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    automation = effective_automation(task, validation_level)
    request = {
        "task_id": task["id"],
        "category": task.get("category"),
        "validation_level": validation_level,
        "automation_level": automation["automation_level"],
        "context": context or {},
    }
    return {
        "request": request,
        "request_digest": request_digest(request),
        "confirmation_required": automation["confirmation_required"],
    }


def authorize_task(
    task: dict[str, Any],
    validation_level: str,
    request: dict[str, Any] | None = None,
    confirmation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fail closed for non-routine, non-auto, or unclassified CI/CD tasks."""

    automation = effective_automation(task, validation_level)
    if automation["configuration_errors"]:
        return {
            "allowed": False,
            **automation,
            "blocker_codes": ["CONFIG_INVALID", "HANDOFF_REQUIRED"],
            "confirmation_status": "invalid-task-configuration",
        }
    if not automation["confirmation_required"]:
        return {
            "allowed": True,
            **automation,
            "blocker_codes": [],
            "confirmation_status": "not-required-by-explicit-policy",
        }
    if request is None or confirmation is None:
        return {
            "allowed": False,
            **automation,
            "blocker_codes": ["HANDOFF_REQUIRED"],
            "confirmation_status": "required",
        }
    expected = create_task_request(
        task, validation_level, request.get("context", {})
    )
    request_matches = request == expected["request"]
    confirmation_matches = (
        confirmation.get("confirmed") is True
        and confirmation.get("request_digest") == expected["request_digest"]
    )
    if not request_matches or not confirmation_matches:
        return {
            "allowed": False,
            **automation,
            "blocker_codes": ["HANDOFF_REQUIRED"],
            "confirmation_status": "stale-or-mismatched",
        }
    return {
        "allowed": True,
        **automation,
        "blocker_codes": [],
        "confirmation_status": "confirmed",
    }
