"""Read-only repository fact discovery for Harness planning."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml


PROTECTED_TRIGGERS = {"push", "pull_request", "schedule"}


def _package_scripts(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    scripts = document.get("scripts", {})
    return scripts if isinstance(scripts, dict) else {}


def _workflow_triggers(path: Path) -> list[str]:
    try:
        document = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    except (OSError, yaml.YAMLError):
        return []
    if not isinstance(document, dict):
        return []
    triggers = document.get("on", {})
    if isinstance(triggers, str):
        return [triggers]
    if isinstance(triggers, list):
        return [item for item in triggers if isinstance(item, str)]
    if isinstance(triggers, dict):
        return [item for item in triggers if isinstance(item, str)]
    return []


def discover_repository(root: Path) -> dict[str, Any]:
    """Return source-backed facts without modifying the repository."""

    root = root.resolve()
    project_types: list[str] = []
    fact_sources: dict[str, str] = {}

    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        project_types.append("python")
        fact_sources["python"] = "pyproject.toml"
    elif (root / "requirements.txt").is_file():
        project_types.append("python")
        fact_sources["python"] = "requirements.txt"

    package_json = root / "package.json"
    scripts = _package_scripts(package_json)
    if package_json.is_file():
        project_types.append("node")
        fact_sources["node"] = "package.json"

    workflows: list[dict[str, Any]] = []
    workflow_root = root / ".github" / "workflows"
    if workflow_root.is_dir():
        for path in sorted((*workflow_root.glob("*.yml"), *workflow_root.glob("*.yaml"))):
            triggers = _workflow_triggers(path)
            workflows.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "triggers": triggers,
                    "controlled_entry": "workflow_dispatch" in triggers,
                    "protected_trigger_uncontrolled": bool(
                        PROTECTED_TRIGGERS.intersection(triggers)
                    )
                    or (
                        "workflow_call" in triggers
                        and "workflow_dispatch" not in triggers
                    ),
                }
            )

    source_roots = [
        name
        for name in ("src", "lib", "app", "packages")
        if (root / name).is_dir()
    ]
    test_roots = [
        name for name in ("tests", "test", "__tests__") if (root / name).is_dir()
    ]

    return {
        "repository_root": str(root),
        "project_types": project_types,
        "fact_sources": fact_sources,
        "agents": {
            "exists": (root / "AGENTS.md").is_file(),
            "path": "AGENTS.md",
        },
        "harness": {
            "exists": (root / ".harness").is_dir(),
            "path": ".harness",
        },
        "source_roots": source_roots,
        "test_roots": test_roots,
        "package_scripts": scripts,
        "workflows": workflows,
        "gaps": (
            [{"code": "NO_PROJECT_TYPE", "severity": "blocking"}]
            if not project_types
            else []
        ),
    }
