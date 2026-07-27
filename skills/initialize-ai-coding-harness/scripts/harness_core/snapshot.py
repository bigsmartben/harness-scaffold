"""Deterministic repository snapshots for governance projection inputs."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .artifacts import (
    GOVERNANCE_SCHEMA_VERSION,
    attach_digest,
    content_digest,
    path_digest,
)
from .templates import HARNESS_MARKER_END, HARNESS_MARKER_START


_IGNORED_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "node_modules",
}
_IGNORED_HARNESS_DIRS = {"evidence", "governance", "reports", "runs"}
_RELEVANT_NAMES = {
    "AGENTS.md",
    "Cargo.lock",
    "Cargo.toml",
    "Gemfile",
    "Gemfile.lock",
    "Makefile",
    "package-lock.json",
    "package.json",
    "pnpm-lock.yaml",
    "pyproject.toml",
    "requirements.txt",
    "uv.lock",
    "yarn.lock",
}
_RELEVANT_SUFFIXES = {
    ".json",
    ".jsonc",
    ".lock",
    ".toml",
    ".yaml",
    ".yml",
}
_RELEVANT_ROOTS = {
    ".agents",
    ".codex",
    ".github",
    ".harness",
    "scripts",
}
_TOML_MARKER_START = "# ai-coding-harness:start"
_TOML_MARKER_END = "# ai-coding-harness:end"


def _normalized_relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def governance_relevant_paths(root: Path) -> tuple[str, ...]:
    """Return stable repository-relative governance input paths.

    Runtime Evidence and generated caches are deliberately excluded. Uncommitted
    file content is included because the snapshot reads the working tree.
    """

    repository = root.resolve()
    paths: set[str] = set()
    for path in repository.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(repository)
        parts = relative.parts
        if any(part in _IGNORED_PARTS for part in parts):
            continue
        if (
            parts
            and parts[0] == ".harness"
            and len(parts) > 1
            and parts[1] in _IGNORED_HARNESS_DIRS
        ):
            if (
                parts[1] == "governance"
                and len(parts) == 3
                and parts[2] == "declarations.json"
            ):
                paths.add(_normalized_relative(repository, path))
            continue
        if parts[:3] == (".agents", "skills", "harness"):
            continue
        if (
            len(parts) >= 3
            and parts[:2] == (".codex", "agents")
            and path.read_text(encoding="utf-8", errors="ignore").startswith(
                "# managed-by: sdd-harness"
            )
        ):
            continue
        if path.name == "AGENTS.md":
            external = _without_marked_block(
                path.read_text(encoding="utf-8"),
                HARNESS_MARKER_START,
                HARNESS_MARKER_END,
            )
            if not external.strip():
                continue
        if relative_path := _normalized_relative(repository, path):
            if relative_path == ".codex/config.toml":
                external = _without_marked_block(
                    path.read_text(encoding="utf-8"),
                    _TOML_MARKER_START,
                    _TOML_MARKER_END,
                )
                if not external.strip():
                    continue
            if relative_path == ".codex/hooks.json" and not _external_hooks(path):
                continue
        if (
            path.name in _RELEVANT_NAMES
            or (parts and parts[0] in _RELEVANT_ROOTS)
            or path.suffix.lower() in _RELEVANT_SUFFIXES
        ):
            paths.add(_normalized_relative(repository, path))
    return tuple(sorted(paths))


def _without_marked_block(text: str, start: str, end: str) -> str:
    start_index = text.find(start)
    if start_index < 0:
        return text
    end_index = text.find(end, start_index + len(start))
    if end_index < 0:
        return text
    end_index += len(end)
    return text[:start_index] + text[end_index:]


def _external_text_digest(text: str) -> str:
    """Hash user-owned text without managed separator whitespace."""

    normalized = text.rstrip()
    return content_digest(f"{normalized}\n" if normalized else "")


def _external_hooks(path: Path) -> dict:
    try:
        document = __import__("json").loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"invalid": True}
    if not isinstance(document, dict):
        return {"invalid": True}
    result = {
        key: value
        for key, value in document.items()
        if key not in {"description", "hooks"}
    }
    external_hooks = {}
    hooks = document.get("hooks", {})
    if isinstance(hooks, dict):
        for event, groups in hooks.items():
            if not isinstance(groups, list):
                external_hooks[event] = groups
                continue
            retained = [
                group
                for group in groups
                if "sdd-harness hook"
                not in __import__("json").dumps(group, sort_keys=True)
            ]
            if retained:
                external_hooks[event] = retained
    if external_hooks:
        result["hooks"] = external_hooks
    return result


def _governance_input_digest(relative: str, target: Path) -> str:
    if relative == "AGENTS.md":
        text = target.read_text(encoding="utf-8")
        return _external_text_digest(
            _without_marked_block(text, HARNESS_MARKER_START, HARNESS_MARKER_END)
        )
    if relative == ".codex/config.toml":
        text = target.read_text(encoding="utf-8")
        return _external_text_digest(
            _without_marked_block(text, _TOML_MARKER_START, _TOML_MARKER_END)
        )
    if relative == ".codex/hooks.json":
        return content_digest(
            __import__("json").dumps(
                _external_hooks(target),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    return path_digest(target)


def create_repository_snapshot(
    root: Path,
    *,
    paths: Iterable[str] | None = None,
) -> dict:
    """Create a path-independent, byte-stable RepositorySnapshot."""

    repository = root.resolve()
    selected = tuple(
        sorted(
            {
                str(path).replace("\\", "/")
                for path in (paths if paths is not None else governance_relevant_paths(repository))
            }
        )
    )
    files = []
    for relative in selected:
        target = (repository / relative).resolve()
        if not target.is_relative_to(repository) or not target.is_file():
            continue
        files.append(
            {
                "path": relative,
                "digest": _governance_input_digest(relative, target),
            }
        )
    document = {
        "artifact_type": "repository-snapshot",
        "schema_version": GOVERNANCE_SCHEMA_VERSION,
        "files": files,
    }
    return attach_digest(document, "snapshot_digest")


def snapshot_matches(root: Path, snapshot: dict) -> bool:
    """Return whether current governance inputs still match a snapshot."""

    expected_paths = [
        item["path"]
        for item in snapshot.get("files", [])
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    ]
    current = create_repository_snapshot(root, paths=expected_paths)
    return (
        current.get("files") == snapshot.get("files")
        and current.get("snapshot_digest") == snapshot.get("snapshot_digest")
    )
