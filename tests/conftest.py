from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from harness_core.initializer import (
    apply_initialization_plan,
    build_initialization_plan,
)


def git(repository: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def initialize(repository: Path, *, with_hooks: bool = False) -> dict:
    plan = build_initialization_plan(repository, with_hooks=with_hooks)
    assert plan["blocker_codes"] == []
    result = apply_initialization_plan(
        repository,
        plan,
        approved_plan_digest=plan["plan_digest"],
    )
    assert result["status"] == "applied"
    return result


@pytest.fixture
def private_repository(tmp_path: Path) -> Path:
    git(tmp_path, "init")
    git(tmp_path, "checkout", "-b", "codex/test")
    git(tmp_path, "config", "user.name", "Harness Test")
    git(tmp_path, "config", "user.email", "harness@example.invalid")
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = \"fixture\"\nversion = \"0.1.0\"\n",
        encoding="utf-8",
    )
    git(tmp_path, "add", "pyproject.toml")
    git(tmp_path, "commit", "-m", "fixture")
    return tmp_path
