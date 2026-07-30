"""Minimal zero-migration Harness 3.0 repository initialization."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

import yaml

from .contracts import ValidationIssue, validate_project_config
from .package_resources import repo_skill_bytes
from .projection import (
    default_model_lock_path,
    project_model_lock,
)


CONFIG_RELATIVE_PATH = ".harness/harness.yaml"
SKILL_RELATIVE_PATH = ".agents/skills/harness/SKILL.md"

LEGACY_PATHS = (
    ".harness/adapters",
    ".harness/pipelines",
    ".harness/tasks.yaml",
    ".harness/tools.yaml",
    ".harness/boundaries.yaml",
    ".harness/impact.yaml",
    ".harness/governance/sources.lock.json",
    ".harness/governance/action-graph.json",
    ".harness/governance/rules.json",
    ".harness/governance/projection.lock.json",
    ".harness/governance/compatibility.json",
    ".codex",
    "plugins/harness",
)

MINIMAL_CONFIG = {
        "schema_version": "3.0.1",
    "rule_instances": {
        "specification": [],
        "implementation": [],
        "verification": [],
        "delivery": [],
    },
}


def render_minimal_config() -> bytes:
    return (
        yaml.safe_dump(
            MINIMAL_CONFIG,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        )
        .replace("\r\n", "\n")
        .encode("utf-8")
    )


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _diagnostic(
    code: str,
    path: str,
    message: str,
    *,
    expected: Any | None = None,
    actual: Any | None = None,
) -> dict[str, Any]:
    return ValidationIssue(
        code,
        path,
        message,
        expected=expected,
        actual=actual,
    ).as_dict()


def initialize_repository(repository: Path) -> dict[str, Any]:
    """Create only config, the minimal Skill, and the initial model lock."""

    root = repository.resolve()
    if not root.is_dir():
        return {
            "status": "blocked",
            "repository": str(root),
            "created_paths": [],
            "diagnostics": [
                _diagnostic(
                    "REPOSITORY_NOT_FOUND",
                    "",
                    "target repository directory does not exist",
                    expected="existing directory",
                    actual=str(root),
                )
            ],
        }

    config_path = root / CONFIG_RELATIVE_PATH
    skill_path = root / SKILL_RELATIVE_PATH
    lock_path = default_model_lock_path(root)

    if config_path.exists():
        config_issues = validate_project_config(config_path)
        if config_issues:
            return {
                "status": "blocked",
                "repository": str(root),
                "created_paths": [],
                "diagnostics": [
                    issue.as_dict() for issue in config_issues
                ],
            }
        source: dict[str, Any] | Path = config_path
    else:
        legacy = [
            relative
            for relative in LEGACY_PATHS
            if (root / relative).exists()
        ]
        if legacy:
            return {
                "status": "blocked",
                "repository": str(root),
                "created_paths": [],
                "diagnostics": [
                    _diagnostic(
                        "LEGACY_HARNESS_INPUT",
                        "",
                        "legacy Harness input must be removed manually",
                        expected="clean repository without v1/v2 Harness input",
                        actual=legacy,
                    )
                ],
            }
        source = MINIMAL_CONFIG

    expected_skill = repo_skill_bytes()
    if skill_path.exists() and skill_path.read_bytes() != expected_skill:
        return {
            "status": "blocked",
            "repository": str(root),
            "created_paths": [],
            "diagnostics": [
                _diagnostic(
                    "INITIALIZATION_CONFLICT",
                    f"/{SKILL_RELATIVE_PATH}",
                    "existing Harness Skill differs from the v3 resource",
                    expected="exact Harness 3.0 Skill",
                    actual="different bytes",
                )
            ],
        }

    created: list[str] = []
    try:
        if not config_path.exists():
            _atomic_write(config_path, render_minimal_config())
            created.append(CONFIG_RELATIVE_PATH)
            source = config_path
        if not skill_path.exists():
            _atomic_write(skill_path, expected_skill)
            created.append(SKILL_RELATIVE_PATH)
    except OSError as exc:
        return {
            "status": "blocked",
            "repository": str(root),
            "created_paths": created,
            "diagnostics": [
                _diagnostic(
                    "INITIALIZATION_WRITE_FAILED",
                    "",
                    str(exc),
                    expected="atomic local file creation",
                    actual=type(exc).__name__,
                )
            ],
        }

    lock_result = project_model_lock(source, lock_path)
    if lock_result["status"] == "blocked":
        return {
            "status": "blocked",
            "repository": str(root),
            "created_paths": created,
            "diagnostics": lock_result["diagnostics"],
        }
    if lock_result["status"] == "projected":
        created.append(
            lock_path.relative_to(root).as_posix()
        )
    return {
        "status": "initialized",
        "repository": str(root),
        "created_paths": created,
        "source_digest": lock_result["source_digest"],
        "projection_digest": lock_result["projection_digest"],
        "diagnostics": [],
    }
