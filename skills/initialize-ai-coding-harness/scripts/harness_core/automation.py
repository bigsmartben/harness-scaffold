"""Classify actions and authorize digest-bound Task Requests."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .artifacts import SCHEMA_VERSION, artifact_digest, attach_digest, canonical_digest
from .contracts import runtime_artifact_is_valid


AUTOMATION_LEVELS = ("routine", "expensive", "critical")
ACTION_SEMANTICS = {
    "ordinary",
    "lint",
    "validation",
    "test",
    "build",
    "ci",
    "package",
    "push",
    "pull-request",
    "merge",
    "publish",
    "release",
    "deploy",
}
CRITICAL_CATEGORIES = {
    "push",
    "pull-request",
    "merge",
    "publish",
    "release",
    "deploy",
}
EXPENSIVE_VALIDATION_LEVELS = {"integration", "full"}
TOOL_BINDING_FIELDS = {
    "type",
    "entrypoint",
    "server_ref",
    "method",
    "version_source",
    "invocation_mode",
    "action_semantics",
    "task_ref",
}


def tool_entry_blockers(
    registered: dict[str, Any], observed: dict[str, Any]
) -> list[str]:
    """Detect a discovered Tool fact that no longer matches its registry entry."""

    stale = any(
        registered.get(field) != observed.get(field)
        for field in TOOL_BINDING_FIELDS
        if field in registered or field in observed
    )
    return ["TOOL_ENTRY_STALE", "HANDOFF_REQUIRED"] if stale else []


def request_digest(request: dict[str, Any]) -> str:
    """Digest a Task Request without digesting its own digest field."""

    if request.get("artifact_type") == "task-request":
        return artifact_digest(request, "request_digest")
    return canonical_digest(request)


def _missing_request_fields(
    task: dict[str, Any], request: dict[str, Any]
) -> list[str]:
    category = task.get("category")
    missing: list[str] = []
    if category in CRITICAL_CATEGORIES and not request.get("target"):
        missing.append("target")
    if category == "pull-request" and not request.get("source_ref"):
        missing.append("source_ref")
    if category == "merge":
        if not request.get("pull_request_number"):
            missing.append("pull_request_number")
        if not request.get("merge_method"):
            missing.append("merge_method")
    if category in {"publish", "release", "deploy"}:
        for field in ("version", "artifact_digest", "environment"):
            if not request.get(field):
                missing.append(field)
    return missing


def effective_automation(
    task: dict[str, Any], validation_level: str | None = None
) -> dict[str, Any]:
    """Return the effective automation level and fail closed on bad policy."""

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
    if validation_level in EXPENSIVE_VALIDATION_LEVELS and effective != "critical":
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
    """Resolve policy by action semantics, never by invocation channel."""

    tool = next(
        (item for item in tools.get("tools", []) if item.get("id") == tool_id),
        None,
    )
    if tool is None:
        return {
            "status": "blocked",
            "blocker_codes": ["TOOL_NOT_REGISTERED", "HANDOFF_REQUIRED"],
        }
    semantics = tool.get("action_semantics")
    mode = tool.get("invocation_mode")
    base = {
        "tool_id": tool_id,
        "channel": tool.get("type"),
    }
    if semantics not in ACTION_SEMANTICS:
        return {
            **base,
            "status": "blocked",
            "blocker_codes": [
                "ACTION_CLASSIFICATION_UNRESOLVED",
                "HANDOFF_REQUIRED",
            ],
        }
    if semantics == "ordinary":
        if mode == "direct" and "task_ref" not in tool:
            return {
                **base,
                "status": "direct",
                "confirmation_required": False,
                "blocker_codes": [],
            }
        return {
            **base,
            "status": "blocked",
            "blocker_codes": [
                "ACTION_CLASSIFICATION_UNRESOLVED",
                "HANDOFF_REQUIRED",
            ],
        }
    if mode == "direct":
        return {
            **base,
            "status": "blocked",
            "blocker_codes": [
                "TASK_BYPASS_ATTEMPT",
                "HANDOFF_REQUIRED",
            ],
        }
    if mode != "managed":
        return {
            **base,
            "status": "blocked",
            "blocker_codes": [
                "ACTION_CLASSIFICATION_UNRESOLVED",
                "HANDOFF_REQUIRED",
            ],
        }
    task_ref = tool.get("task_ref")
    task = next(
        (item for item in tasks.get("tasks", []) if item.get("id") == task_ref),
        None,
    )
    if task is None:
        return {
            **base,
            "status": "blocked",
            "blocker_codes": ["CONFIG_INVALID", "HANDOFF_REQUIRED"],
        }
    if task.get("category") != semantics:
        return {
            **base,
            "task_id": task_ref,
            "status": "blocked",
            "blocker_codes": [
                "ACTION_CLASSIFICATION_UNRESOLVED",
                "HANDOFF_REQUIRED",
            ],
        }
    automation = effective_automation(task, validation_level)
    return {
        **base,
        "task_id": task_ref,
        **automation,
        "status": (
            "automatic" if automation["auto_allowed"] else "confirmation-required"
        ),
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
    context: dict[str, Any],
) -> dict[str, Any]:
    """Create one 1.0 Task Request bound to the current execution chain."""

    required = {
        "commit_sha",
        "grant_digest",
        "manifest_digest",
        "selection_digest",
    }
    missing = sorted(required - context.keys())
    if missing:
        raise ValueError(
            "EVIDENCE_BINDING_MISMATCH: missing request bindings: "
            + ", ".join(missing)
        )
    automation = effective_automation(task, validation_level)
    if automation["configuration_errors"]:
        raise ValueError("CONFIG_INVALID: " + "; ".join(automation["configuration_errors"]))
    request = {
        "artifact_type": "task-request",
        "schema_version": SCHEMA_VERSION,
        "request_id": context.get("request_id", f"request:{task['id']}"),
        "task_id": task["id"],
        "action_semantics": task["category"],
        "validation_level": validation_level,
        "target": context.get("target"),
        "source_ref": context.get("source_ref"),
        "pull_request_number": context.get("pull_request_number"),
        "merge_method": context.get("merge_method"),
        "commit_sha": context["commit_sha"],
        "version": context.get("version"),
        "artifact_digest": context.get("artifact_digest"),
        "environment": context.get("environment"),
        "automation_level": automation["automation_level"],
        "policy_version": SCHEMA_VERSION,
        "grant_digest": context["grant_digest"],
        "manifest_digest": context["manifest_digest"],
        "selection_digest": context["selection_digest"],
    }
    missing_request_fields = _missing_request_fields(task, request)
    if missing_request_fields:
        raise ValueError(
            "EVIDENCE_INCOMPLETE + HANDOFF_REQUIRED: missing "
            + ", ".join(missing_request_fields)
        )
    request = attach_digest(request, "request_digest")
    if not runtime_artifact_is_valid(request):
        raise ValueError(
            "EVIDENCE_BINDING_MISMATCH + HANDOFF_REQUIRED: "
            "Task Request does not satisfy the 1.0 runtime schema"
        )
    return request


def create_confirmation(
    request: dict[str, Any], confirmed_at: str | None = None
) -> dict[str, Any]:
    """Create current confirmation bound to exactly one Task Request."""

    if (
        not runtime_artifact_is_valid(request)
        or request_digest(request) != request.get("request_digest")
    ):
        raise ValueError("EVIDENCE_BINDING_MISMATCH: Task Request digest is invalid")
    return {
        "artifact_type": "confirmation",
        "schema_version": SCHEMA_VERSION,
        "request_digest": request["request_digest"],
        "confirmation_status": "confirmed",
        "confirmed_at": confirmed_at
        or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def authorize_task(
    task: dict[str, Any],
    validation_level: str,
    request: dict[str, Any] | None = None,
    confirmation: dict[str, Any] | None = None,
    require_confirmation: bool | None = None,
) -> dict[str, Any]:
    """Authorize only a current, task-matching Request and Confirmation."""

    automation = effective_automation(task, validation_level)
    if automation["configuration_errors"]:
        return {
            "allowed": False,
            **automation,
            "blocker_codes": ["CONFIG_INVALID", "HANDOFF_REQUIRED"],
            "confirmation_status": "invalid-task-configuration",
        }
    request_matches = (
        isinstance(request, dict)
        and runtime_artifact_is_valid(request)
        and request.get("artifact_type") == "task-request"
        and request.get("schema_version") == SCHEMA_VERSION
        and request.get("task_id") == task.get("id")
        and request.get("action_semantics") == task.get("category")
        and request.get("validation_level") == validation_level
        and request.get("automation_level") == automation["automation_level"]
        and request_digest(request) == request.get("request_digest")
    )
    if not request_matches:
        return {
            "allowed": False,
            **automation,
            "blocker_codes": [
                "EVIDENCE_BINDING_MISMATCH",
                "HANDOFF_REQUIRED",
            ],
            "confirmation_status": "stale-or-mismatched",
        }
    missing_request_fields = _missing_request_fields(task, request)
    if missing_request_fields:
        return {
            "allowed": False,
            **automation,
            "blocker_codes": ["EVIDENCE_INCOMPLETE", "HANDOFF_REQUIRED"],
            "confirmation_status": "stale-or-mismatched",
            "missing_request_fields": missing_request_fields,
        }
    if require_confirmation is False:
        return {
            "allowed": True,
            **automation,
            "confirmation_required": False,
            "blocker_codes": [],
            "confirmation_status": "not-required-by-branch-policy",
        }
    if not automation["confirmation_required"]:
        return {
            "allowed": True,
            **automation,
            "blocker_codes": [],
            "confirmation_status": "not-required-by-explicit-policy",
        }
    confirmation_matches = (
        isinstance(confirmation, dict)
        and runtime_artifact_is_valid(confirmation)
        and confirmation.get("artifact_type") == "confirmation"
        and confirmation.get("schema_version") == SCHEMA_VERSION
        and confirmation.get("confirmation_status") == "confirmed"
        and confirmation.get("request_digest") == request["request_digest"]
    )
    if not confirmation_matches:
        return {
            "allowed": False,
            **automation,
            "blocker_codes": ["HANDOFF_REQUIRED"],
            "confirmation_status": "required",
        }
    return {
        "allowed": True,
        **automation,
        "blocker_codes": [],
        "confirmation_status": "confirmed",
    }
