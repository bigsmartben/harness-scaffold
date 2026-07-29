"""Read-only Git workspace facts shared by planning and runtime checks."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from .artifacts import canonical_digest, path_digest


class GitUnavailable(RuntimeError):
    pass


def run_git(
    repository: Path,
    arguments: list[str],
    *,
    env: dict[str, str] | None = None,
    input_bytes: bytes | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        env=env,
        input=input_bytes,
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise GitUnavailable(message or f"git exited with {result.returncode}")
    return result


def _zpaths(payload: bytes) -> list[str]:
    return sorted(
        {
            item.decode("utf-8", errors="surrogateescape").replace("\\", "/")
            for item in payload.split(b"\0")
            if item
        }
    )


def _text(repository: Path, arguments: list[str]) -> str | None:
    result = run_git(repository, arguments, check=False)
    if result.returncode != 0:
        return None
    return result.stdout.decode("utf-8", errors="replace").strip() or None


def workspace_state(repository: Path) -> dict[str, Any]:
    root = repository.resolve()
    base_commit = _text(root, ["rev-parse", "--verify", "HEAD"]) or "unborn"
    head_ref = _text(root, ["symbolic-ref", "-q", "HEAD"])
    staged = _zpaths(
        run_git(root, ["diff", "--cached", "--name-only", "-z"]).stdout
    )
    unstaged = _zpaths(run_git(root, ["diff", "--name-only", "-z"]).stdout)
    untracked = _zpaths(
        run_git(
            root,
            ["ls-files", "--others", "--exclude-standard", "-z"],
        ).stdout
    )
    changed = sorted(set(staged) | set(unstaged) | set(untracked))
    file_states = [
        {
            "path": path,
            "working_tree_digest": path_digest(root / path),
        }
        for path in changed
    ]
    cached_diff = run_git(
        root,
        ["diff", "--cached", "--binary", "--no-ext-diff"],
    ).stdout
    working_diff = run_git(
        root,
        ["diff", "--binary", "--no-ext-diff"],
    ).stdout
    payload = {
        "base_commit": base_commit,
        "head_ref": head_ref,
        "staged": staged,
        "unstaged": unstaged,
        "untracked": untracked,
        "files": file_states,
        "cached_diff_digest": canonical_digest(
            {"bytes": cached_diff.hex()}
        ),
        "working_diff_digest": canonical_digest(
            {"bytes": working_diff.hex()}
        ),
    }
    return {
        **payload,
        "partial_paths": sorted(set(staged) & set(unstaged)),
        "changed_paths": changed,
        "workspace_digest": canonical_digest(payload),
    }


def temporary_git_environment(index_path: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment["GIT_INDEX_FILE"] = str(index_path)
    return environment

