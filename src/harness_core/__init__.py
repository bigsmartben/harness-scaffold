"""Public Harness 4 contract API."""

from .artifacts import (
    canonical_digest,
    canonical_json,
    canonical_json_bytes,
    content_digest,
)
from .bootstrap import (
    LEGACY_ARCHIVE_ROOT,
    load_and_bootstrap,
)
from .lifecycle import (
    OPERATION_STATUSES,
    OPERATION_TYPES,
    RULE_STATUSES,
    apply_operation,
    build_operation_request,
    cancel_operation,
    empty_governance_state,
    governance_rule_digest,
    register_operation,
    validate_operation_request,
)
from .load_core import (
    LOAD_CONTRACT_VERSION,
    build_load_request,
    load_repository,
)
from .model import (
    AUDIENCES,
    CELL_DIRECTIVES,
    CELL_IDS,
    CONTRACT_VERSION,
    CORE_VERSION,
    DOMAINS,
    GENERATE_STAGES,
    LAYER_RESPONSIBILITIES,
    PROJECTION_COMPILER_VERSION,
    RESPONSIBILITY_SEMANTICS,
    RESPONSIBILITIES,
    SCHEMA_VERSION,
    consumer_rule_cell_ids,
)
from .skill_adapter import (
    adapt_app_intent,
    adapt_cli_intent,
    adapt_governance_intent,
)
from .scaffold import (
    ENFORCEMENT_DECISIONS,
    EVIDENCE_TYPES,
    GOVERNANCE_STATE_RELATIVE_PATH,
    GovernanceRepository,
    compile_governance_projection,
    create_enforcement_obligations,
    evaluate_enforcement,
    ingest_load_result,
)

__version__ = CORE_VERSION

__all__ = [
    "AUDIENCES",
    "CELL_DIRECTIVES",
    "CELL_IDS",
    "CONTRACT_VERSION",
    "CORE_VERSION",
    "DOMAINS",
    "ENFORCEMENT_DECISIONS",
    "EVIDENCE_TYPES",
    "GENERATE_STAGES",
    "GOVERNANCE_STATE_RELATIVE_PATH",
    "GovernanceRepository",
    "LAYER_RESPONSIBILITIES",
    "LEGACY_ARCHIVE_ROOT",
    "LOAD_CONTRACT_VERSION",
    "PROJECTION_COMPILER_VERSION",
    "RESPONSIBILITY_SEMANTICS",
    "RESPONSIBILITIES",
    "RULE_STATUSES",
    "OPERATION_TYPES",
    "OPERATION_STATUSES",
    "SCHEMA_VERSION",
    "canonical_digest",
    "canonical_json",
    "canonical_json_bytes",
    "content_digest",
    "consumer_rule_cell_ids",
    "compile_governance_projection",
    "create_enforcement_obligations",
    "apply_operation",
    "adapt_app_intent",
    "adapt_cli_intent",
    "adapt_governance_intent",
    "build_operation_request",
    "build_load_request",
    "cancel_operation",
    "ingest_load_result",
    "load_repository",
    "load_and_bootstrap",
    "empty_governance_state",
    "evaluate_enforcement",
    "governance_rule_digest",
    "register_operation",
    "validate_operation_request",
]
