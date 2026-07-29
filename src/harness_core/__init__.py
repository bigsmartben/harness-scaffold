"""Public Harness 3.0 contract API."""

from .artifacts import (
    canonical_digest,
    canonical_json,
    canonical_json_bytes,
    content_digest,
)
from .contracts import (
    ValidationIssue,
    validate_fixed_model_cells,
    validate_governance_artifact,
    validate_project_config,
)
from .initializer import (
    CONFIG_RELATIVE_PATH,
    MINIMAL_CONFIG,
    SKILL_RELATIVE_PATH,
    initialize_repository,
    render_minimal_config,
)
from .model import (
    AUDIENCES,
    CELL_IDS,
    CONTRACT_VERSION,
    CORE_VERSION,
    DOMAINS,
    PROJECTION_COMPILER_VERSION,
    RESPONSIBILITIES,
    SCHEMA_VERSION,
)
from .projection import (
    MODEL_LOCK_RELATIVE_PATH,
    ContractValidationError,
    compile_model_lock,
    default_model_lock_path,
    normalize_project_config,
    project_model_lock,
    render_model_lock,
    validate_model_lock,
)

__version__ = CORE_VERSION

__all__ = [
    "AUDIENCES",
    "CELL_IDS",
    "CONTRACT_VERSION",
    "CONFIG_RELATIVE_PATH",
    "CORE_VERSION",
    "DOMAINS",
    "MODEL_LOCK_RELATIVE_PATH",
    "MINIMAL_CONFIG",
    "PROJECTION_COMPILER_VERSION",
    "RESPONSIBILITIES",
    "SCHEMA_VERSION",
    "SKILL_RELATIVE_PATH",
    "ValidationIssue",
    "ContractValidationError",
    "canonical_digest",
    "canonical_json",
    "canonical_json_bytes",
    "content_digest",
    "compile_model_lock",
    "default_model_lock_path",
    "initialize_repository",
    "normalize_project_config",
    "project_model_lock",
    "render_minimal_config",
    "render_model_lock",
    "validate_fixed_model_cells",
    "validate_governance_artifact",
    "validate_model_lock",
    "validate_project_config",
]
