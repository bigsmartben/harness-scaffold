"""Versioned project-policy loading and rendering."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .artifacts import SCHEMA_VERSION, canonical_digest
from .contracts import validate_project_config


def default_project_config(
    *,
    mode: str,
    hooks_enabled: bool = False,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "project_policy": {
            "local_execution": "continuous",
            "validation": "minimum-sufficient",
            "hooks": "enabled" if hooks_enabled else "optional",
            "declarations": {},
        },
        "issue_planning": {
            "default_provider": "local",
            "local_directory": ".harness/issues",
            "remote": None,
        },
        "branch_policy": {
            "private": ["refs/heads/codex/**", "refs/heads/agent/**"],
            "controlled": [
                "refs/heads/main",
                "refs/heads/master",
                "refs/heads/release/**",
                "refs/heads/hotfix/**",
            ],
            "unmatched": "controlled",
            "actions": [
                "write",
                "commit",
                "issue-write",
                "push",
                "pull-request",
                "merge",
                "publish",
                "release",
                "deploy",
            ],
        },
    }


def load_project_config(repository: Path) -> dict[str, Any] | None:
    path = repository / ".harness" / "harness.yaml"
    if not path.is_file():
        return None
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return None
    if not isinstance(value, dict) or validate_project_config(value):
        return None
    return value


def render_project_config(document: dict[str, Any]) -> str:
    return yaml.safe_dump(
        document,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )


def project_policy_digest(config: dict[str, Any]) -> str:
    return canonical_digest(config["project_policy"])

