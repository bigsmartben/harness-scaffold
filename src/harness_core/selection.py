"""Four-domain impact analysis and T0-T3 validation selection."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from .artifacts import SCHEMA_VERSION, attach_digest
from .workspace import workspace_state


_LEVEL_ORDER = {"T0": 0, "T1": 1, "T2": 2, "T3": 3}
_DOC_SUFFIXES = {".md", ".rst", ".txt"}
_LOCK_FILES = {
    "uv.lock",
    "poetry.lock",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "Cargo.lock",
    "go.sum",
}


def _max_level(*levels: str) -> str:
    return max(levels, key=lambda value: _LEVEL_ORDER[value])


def _path_level(path: str) -> tuple[str, str]:
    normalized = path.replace("\\", "/")
    candidate = Path(normalized)
    lower = normalized.lower()
    if (
        normalized.startswith(".github/")
        or normalized.startswith(".harness/")
        or normalized.startswith("src/harness_core/")
        or candidate.name in _LOCK_FILES
        or candidate.name in {"pyproject.toml", "package.json"}
        or any(token in lower for token in ("/migration", "/security", "/ci/"))
    ):
        return "T3", f"{normalized} changes framework, dependency, migration, security, or CI policy"
    if (
        candidate.suffix.lower() == ".json"
        and "schema" in candidate.name.lower()
    ) or any(token in lower for token in ("/schema", "/api/", "/public/")):
        return "T2", f"{normalized} changes a public or shared contract"
    if candidate.suffix.lower() in _DOC_SUFFIXES:
        return "T0", f"{normalized} is documentation or inert text"
    return "T1", f"{normalized} is a narrow implementation or test change"


def _path_domains(path: str) -> set[str]:
    normalized = path.replace("\\", "/").lower()
    domains: set[str] = set()
    if normalized.startswith(("docs/", ".harness/issues/")) or Path(
        normalized
    ).suffix in _DOC_SUFFIXES:
        domains.add("specification")
    if normalized.startswith(("tests/", "test/", "__tests__/")):
        domains.add("verification")
    if normalized.startswith((".github/", ".harness/")):
        domains.add("delivery")
    if not domains or normalized.startswith(
        ("src/", "lib/", "app/", "packages/")
    ):
        domains.add("implementation")
    return domains


def select_validation(
    changed_paths: Iterable[str],
    *,
    action_graph: dict[str, Any] | None = None,
    action_ids: Iterable[str] = (),
) -> dict[str, Any]:
    paths = sorted(set(str(path).replace("\\", "/") for path in changed_paths))
    level = "T0"
    reasons: list[str] = []
    for path in paths:
        path_level, reason = _path_level(path)
        level = _max_level(level, path_level)
        reasons.append(reason)
    if len(paths) > 1 and level == "T1":
        level = "T2"
        reasons.append("multiple changed paths require component-level validation")

    actions_by_id = {
        item["action_id"]: item
        for item in (action_graph or {}).get("actions", [])
    }
    for action_id in sorted(set(action_ids)):
        action = actions_by_id.get(action_id)
        if not action:
            reasons.append(f"{action_id} has no source-backed validation binding")
            continue
        level = _max_level(level, action["validation_floor"])
        reasons.append(
            f"{action_id} requires at least {action['validation_floor']}"
        )
    return {
        "validation_level": level,
        "reasons": sorted(set(reasons)),
    }


def analyze_workspace_impact(
    repository: Path,
    *,
    action_graph: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state = workspace_state(repository)
    selection = select_validation(
        state["changed_paths"], action_graph=action_graph
    )
    domains = sorted(
        {
            domain
            for path in state["changed_paths"]
            for domain in _path_domains(path)
        }
    )
    document = {
        "artifact_type": "impact-analysis",
        "schema_version": SCHEMA_VERSION,
        "base_commit": state["base_commit"],
        "workspace_digest": state["workspace_digest"],
        "changed_paths": state["changed_paths"],
        "domains": domains,
        "validation_level": selection["validation_level"],
        "reasons": selection["reasons"],
    }
    return attach_digest(document, "impact_digest")
