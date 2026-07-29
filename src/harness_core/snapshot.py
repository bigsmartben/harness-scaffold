"""Deterministic repository snapshot generation."""

from __future__ import annotations

from pathlib import Path

from .artifacts import (
    ABSENT,
    SCHEMA_VERSION,
    attach_digest,
    content_digest,
)
from .workspace import run_git


_SOURCE_NAMES = {
    "AGENTS.md",
    "AGENTS.override.md",
    "pyproject.toml",
    "uv.lock",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "Cargo.toml",
    "Cargo.lock",
    "go.mod",
    "go.sum",
    "Makefile",
    "justfile",
}
_HARNESS_SOURCE_NAMES = {
    "harness.yaml",
    "tools.yaml",
    "tasks.yaml",
    "boundaries.yaml",
    "impact.yaml",
}
_IGNORED_SOURCE_PREFIXES = {
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".tmp",
    ".venv",
    "__pycache__",
    "evals",
}


def _portable_content_digest(content: str | bytes) -> str:
    payload = content.encode("utf-8") if isinstance(content, str) else content
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        return content_digest(payload)
    return content_digest(text.replace("\r\n", "\n"))


def _tracked_and_untracked(repository: Path) -> list[str]:
    result = run_git(
        repository,
        ["ls-files", "-co", "--exclude-standard", "-z"],
        check=False,
    )
    if result.returncode == 0:
        return sorted(
            {
                item.decode("utf-8", errors="surrogateescape").replace("\\", "/")
                for item in result.stdout.split(b"\0")
                if item
            }
        )
    return sorted(
        path.relative_to(repository).as_posix()
        for path in repository.rglob("*")
        if path.is_file() and ".git" not in path.parts
    )


def governance_relevant_paths(repository: Path) -> tuple[str, ...]:
    root = repository.resolve()
    selected: list[str] = []
    for relative in _tracked_and_untracked(root):
        path = Path(relative)
        parts = path.parts
        if (
            not parts
            or parts[0] in _IGNORED_SOURCE_PREFIXES
            or parts[:2] == ("tests", "fixtures")
        ):
            continue
        if path.name in _SOURCE_NAMES:
            selected.append(relative)
        elif (
            len(parts) >= 2
            and parts[0] == ".harness"
            and path.name in _HARNESS_SOURCE_NAMES
        ):
            selected.append(relative)
        elif (
            len(parts) >= 3
            and parts[0] == ".github"
            and parts[1] == "workflows"
            and path.suffix.lower() in {".yml", ".yaml"}
        ):
            selected.append(relative)
        elif (
            path.name in {"requirements.txt", "requirements-dev.txt"}
            or relative.startswith("scripts/")
        ):
            selected.append(relative)
    return tuple(sorted(set(selected)))


def create_repository_snapshot(
    repository: Path,
    *,
    content_overrides: dict[str, str | bytes | None] | None = None,
) -> dict:
    root = repository.resolve()
    overrides = {
        key.replace("\\", "/"): value
        for key, value in (content_overrides or {}).items()
    }
    paths = set(governance_relevant_paths(root)) | set(overrides)
    files = []
    for relative in sorted(paths):
        if relative in overrides:
            value = overrides[relative]
            digest = (
                ABSENT
                if value is None
                else _portable_content_digest(value)
            )
        else:
            target = root / relative
            digest = (
                ABSENT
                if not target.exists()
                else _portable_content_digest(target.read_bytes())
            )
        if digest != ABSENT or relative in overrides:
            files.append({"path": relative, "digest": digest})
    payload = {
        "artifact_type": "repository-snapshot",
        "schema_version": SCHEMA_VERSION,
        "files": files,
    }
    return attach_digest(payload, "snapshot_digest")


def snapshot_matches(repository: Path, snapshot: dict) -> bool:
    return create_repository_snapshot(repository).get(
        "snapshot_digest"
    ) == snapshot.get("snapshot_digest")
