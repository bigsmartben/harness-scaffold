"""Read-only Harness 0.x/1.x detection for explicit 2.0 migration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


def _read_mapping(path: Path) -> dict[str, Any] | None:
    try:
        if path.suffix == ".json":
            value = json.loads(path.read_text(encoding="utf-8"))
        else:
            value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, yaml.YAMLError):
        return None
    return value if isinstance(value, dict) else None


def detect_harness_version(repository: Path) -> str | None:
    candidates = (
        repository / ".harness" / "harness.yaml",
        repository / ".harness" / "governance" / "projection.lock.json",
    )
    for path in candidates:
        if not path.is_file():
            continue
        document = _read_mapping(path)
        version = document.get("schema_version") if document else None
        if isinstance(version, str):
            return version
    agents = repository / "AGENTS.md"
    if agents.is_file() and "ai-coding-harness:start" in agents.read_text(
        encoding="utf-8"
    ):
        return "unknown-pre-2.0"
    return None


def migration_drift_report(repository: Path) -> list[dict[str, str]]:
    """Describe old fields without converting them into 2.0 policy."""

    path = repository / ".harness" / "harness.yaml"
    document = _read_mapping(path) if path.is_file() else None
    if not document:
        return []
    retained = {"schema_version", "mode"}
    return [
        {
            "path": ".harness/harness.yaml",
            "field": str(key),
            "decision": "recompile",
            "reason": "2.0 does not silently map legacy governance fields",
        }
        for key in sorted(set(document) - retained)
    ]

