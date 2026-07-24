"""AI Coding Harness deterministic implementation."""

__version__ = "0.2.0"

from .contracts import ValidationIssue, blocker_codes, validate_config
from .discovery import discover_repository
from .automation import (
    AUTOMATION_LEVELS,
    authorize_task,
    create_task_request,
    effective_automation,
    resolve_action_policy,
    request_digest,
)
from .planning import build_plan
from .platform import (
    assess_github_platform,
    normalize_github_platform_evidence,
    platform_evidence_complete,
)
from .pipeline import (
    create_external_request,
    evaluate_merge,
    execute_publish,
)
from .runner import EVIDENCE_FIELDS, run_github_actions_task, run_local_task
from .routing import route_intent
from .scaffold import apply_plan
from .selection import select_validation

__all__ = [
    "ValidationIssue",
    "apply_plan",
    "blocker_codes",
    "build_plan",
    "assess_github_platform",
    "normalize_github_platform_evidence",
    "platform_evidence_complete",
    "discover_repository",
    "EVIDENCE_FIELDS",
    "create_external_request",
    "evaluate_merge",
    "execute_publish",
    "request_digest",
    "AUTOMATION_LEVELS",
    "authorize_task",
    "create_task_request",
    "effective_automation",
    "resolve_action_policy",
    "run_github_actions_task",
    "run_local_task",
    "route_intent",
    "select_validation",
    "validate_config",
]
