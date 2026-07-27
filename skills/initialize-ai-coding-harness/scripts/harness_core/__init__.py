"""AI Coding Harness deterministic implementation."""

__version__ = "1.0.0"

from .artifacts import (
    ABSENT,
    ABSENT_DIGEST,
    CORE_VERSION,
    GOVERNANCE_SCHEMA_VERSION,
    PROJECTION_COMPILER_VERSION,
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
    validate_governance_artifact,
    validate_governance_bundle,
    validate_runtime_artifact,
)
from .snapshot import (
    create_repository_snapshot,
    governance_relevant_paths,
    snapshot_matches,
)
from .facts import extract_source_facts
from .action_graph import build_action_graph
from .projection import (
    AUDIENCES,
    RESPONSIBILITIES,
    SUBDOMAINS,
    compile_governance_projection,
)
from .gates import (
    GATE_IDS,
    create_action_request,
    create_confirmation_package,
    create_work_grant as create_governance_work_grant,
    evaluate_gates,
)
from .postconditions import validate_postconditions
from .agent_contracts import (
    ROLE_CONTRACTS,
    validate_agent_contract,
    validate_agent_directory,
    validate_parent_permissions,
)
from .orchestration import (
    expected_projection_lanes,
    validate_projection_results,
    validate_single_writer,
)
from .initializer import (
    apply_initialization_plan,
    build_initialization_plan,
    compile_repository_projection,
)
from .codex_adapter import handle_hook, load_projection_bundle, runtime_state
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
from .branching import branch_is_controlled, default_branch_gate
from .planning import build_plan, create_plan_approval
from .platform import (
    assess_github_platform,
    normalize_git_remote_evidence,
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
    run_governed_action,
    run_github_actions_task,
    run_git_remote_push_task,
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
    "CORE_VERSION",
    "GOVERNANCE_SCHEMA_VERSION",
    "PROJECTION_COMPILER_VERSION",
    "SCHEMA_VERSION",
    "artifact_digest",
    "attach_digest",
    "apply_plan",
    "blocker_codes",
    "build_action_graph",
    "build_initialization_plan",
    "canonical_json",
    "build_plan",
    "create_plan_approval",
    "create_repository_snapshot",
    "create_governance_work_grant",
    "create_action_request",
    "create_confirmation_package",
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
    "normalize_git_remote_evidence",
    "platform_evidence_complete",
    "discover_repository",
    "extract_source_facts",
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
    "branch_is_controlled",
    "default_branch_gate",
    "resolve_action_policy",
    "tool_entry_blockers",
    "run_github_actions_task",
    "run_governed_action",
    "run_git_remote_push_task",
    "run_local_task",
    "route_intent",
    "runtime_artifact_is_valid",
    "select_validation",
    "validate_config",
    "validate_governance_artifact",
    "validate_governance_bundle",
    "validate_postconditions",
    "validate_runtime_artifact",
    "verify_digest",
    "governance_relevant_paths",
    "snapshot_matches",
    "compile_governance_projection",
    "compile_repository_projection",
    "apply_initialization_plan",
    "evaluate_gates",
    "AUDIENCES",
    "SUBDOMAINS",
    "RESPONSIBILITIES",
    "GATE_IDS",
    "ROLE_CONTRACTS",
    "validate_agent_contract",
    "validate_agent_directory",
    "validate_parent_permissions",
    "expected_projection_lanes",
    "validate_projection_results",
    "validate_single_writer",
    "handle_hook",
    "load_projection_bundle",
    "runtime_state",
]
