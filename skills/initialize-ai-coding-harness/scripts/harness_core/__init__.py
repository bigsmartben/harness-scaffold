"""AI Coding Harness deterministic implementation."""

__version__ = "0.3.0"

from .artifacts import (
    ABSENT,
    ABSENT_DIGEST,
    SCHEMA_VERSION,
    artifact_digest,
    attach_digest,
    canonical_digest,
    canonical_json,
    canonical_json_bytes,
    content_digest,
    digest_matches,
    file_digest,
    normalized_path_digest,
    path_digest,
    verify_digest,
)
from .contracts import (
    ValidationIssue,
    blocker_codes,
    runtime_artifact_is_valid,
    validate_config,
    validate_runtime_artifact,
)
from .discovery import discover_repository, summarize_discovery
from .automation import (
    AUTOMATION_LEVELS,
    authorize_task,
    create_confirmation,
    create_task_request,
    effective_automation,
    resolve_action_policy,
    request_digest,
    tool_entry_blockers,
)
from .bindings import execution_binding_blockers
from .planning import build_plan, create_plan_approval
from .platform import (
    assess_github_platform,
    normalize_github_platform_evidence,
    platform_evidence_complete,
)
from .pipeline import (
    create_external_request,
    dispatch_pipeline,
    evaluate_merge_readiness,
    evaluate_pipeline_readiness,
    evaluate_publish_readiness,
    finalize_pipeline,
)
from .runner import (
    EVIDENCE_FIELDS,
    PlatformAdapter,
    run_github_actions_task,
    run_local_task,
)
from .runtime import (
    create_change_manifest,
    create_confirmation_artifact,
    create_evidence_artifact,
    create_platform_evidence_artifact,
    create_selection_artifact,
    create_task_request_artifact,
    create_work_grant,
    validate_binding_chain,
)
from .routing import route_intent
from .scaffold import apply_plan
from .selection import select_validation

__all__ = [
    "ValidationIssue",
    "ABSENT_DIGEST",
    "SCHEMA_VERSION",
    "artifact_digest",
    "attach_digest",
    "apply_plan",
    "blocker_codes",
    "canonical_json",
    "build_plan",
    "create_plan_approval",
    "create_work_grant",
    "create_change_manifest",
    "create_selection_artifact",
    "create_task_request_artifact",
    "create_confirmation_artifact",
    "create_platform_evidence_artifact",
    "create_evidence_artifact",
    "validate_binding_chain",
    "assess_github_platform",
    "ABSENT",
    "canonical_digest",
    "canonical_json_bytes",
    "content_digest",
    "digest_matches",
    "path_digest",
    "normalize_github_platform_evidence",
    "platform_evidence_complete",
    "discover_repository",
    "summarize_discovery",
    "EVIDENCE_FIELDS",
    "PlatformAdapter",
    "file_digest",
    "create_external_request",
    "dispatch_pipeline",
    "evaluate_merge_readiness",
    "evaluate_pipeline_readiness",
    "evaluate_publish_readiness",
    "finalize_pipeline",
    "request_digest",
    "normalized_path_digest",
    "AUTOMATION_LEVELS",
    "authorize_task",
    "create_confirmation",
    "create_task_request",
    "effective_automation",
    "execution_binding_blockers",
    "resolve_action_policy",
    "tool_entry_blockers",
    "run_github_actions_task",
    "run_local_task",
    "route_intent",
    "runtime_artifact_is_valid",
    "select_validation",
    "validate_config",
    "validate_runtime_artifact",
    "verify_digest",
]
