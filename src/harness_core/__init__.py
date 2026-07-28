"""Deterministic Harness 2.0 contracts and repository adapters."""

from .action_graph import build_action_graph
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
    paths_digest,
    verify_digest,
)
from .codex_adapter import handle_hook, load_projection_bundle, runtime_state
from .contracts import (
    AUDIENCES,
    DOMAINS,
    RESPONSIBILITIES,
    ValidationIssue,
    blocker_codes,
    runtime_artifact_is_valid,
    validate_governance_artifact,
    validate_governance_bundle,
    validate_project_config,
    validate_runtime_artifact,
)
from .facts import extract_source_facts
from .initializer import (
    apply_initialization_plan,
    build_initialization_plan,
    compile_repository_projection,
)
from .projection import COVERAGE_STATUSES, compile_governance_projection
from .push import apply_push_plan, build_push_plan
from .selection import analyze_workspace_impact, select_validation
from .snapshot import (
    create_repository_snapshot,
    governance_relevant_paths,
    snapshot_matches,
)

__version__ = CORE_VERSION

__all__ = [
    "ABSENT",
    "ABSENT_DIGEST",
    "AUDIENCES",
    "CORE_VERSION",
    "COVERAGE_STATUSES",
    "DOMAINS",
    "GOVERNANCE_SCHEMA_VERSION",
    "PROJECTION_COMPILER_VERSION",
    "RESPONSIBILITIES",
    "SCHEMA_VERSION",
    "ValidationIssue",
    "analyze_workspace_impact",
    "apply_initialization_plan",
    "apply_push_plan",
    "artifact_digest",
    "attach_digest",
    "blocker_codes",
    "build_action_graph",
    "build_initialization_plan",
    "build_push_plan",
    "canonical_digest",
    "canonical_json",
    "canonical_json_bytes",
    "compile_governance_projection",
    "compile_repository_projection",
    "content_digest",
    "create_repository_snapshot",
    "digest_matches",
    "extract_source_facts",
    "file_digest",
    "governance_relevant_paths",
    "handle_hook",
    "load_projection_bundle",
    "normalized_path_digest",
    "path_digest",
    "paths_digest",
    "runtime_artifact_is_valid",
    "runtime_state",
    "select_validation",
    "snapshot_matches",
    "validate_governance_artifact",
    "validate_governance_bundle",
    "validate_project_config",
    "validate_runtime_artifact",
    "verify_digest",
]
