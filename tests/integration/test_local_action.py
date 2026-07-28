from __future__ import annotations

from pathlib import Path

import pytest

from harness_core.initializer import (
    apply_initialization_plan,
    apply_projection_plan,
    build_initialization_plan,
    build_projection_plan,
)
from harness_core.runner import run_local_action

from conftest import git


def _initialize(repository: Path) -> None:
    entrypoint = build_initialization_plan(repository)
    assert apply_initialization_plan(
        repository,
        entrypoint,
        approved_plan_digest=entrypoint["plan_digest"],
    )["status"] == "applied"
    projection = build_projection_plan(repository)
    assert apply_projection_plan(
        repository,
        projection,
        approved_plan_digest=projection["plan_digest"],
    )["status"] == "applied"


def test_source_bound_local_action_completes_a_nearest_parser_fix(
    private_repository: Path,
) -> None:
    (private_repository / "pyproject.toml").write_text(
        "[project]\nname='orders'\nversion='0.1.0'\n"
        "[dependency-groups]\ndev=['pytest>=8']\n"
        "[tool.pytest.ini_options]\npythonpath=['src']\n",
        encoding="utf-8",
    )
    (private_repository / "src").mkdir()
    (private_repository / "tests").mkdir()
    (private_repository / "src" / "parser.py").write_text(
        "def parse(query):\n    return query.strip()\n",
        encoding="utf-8",
    )
    (private_repository / "tests" / "test_parser.py").write_text(
        "from parser import parse\n\n"
        "def test_words():\n    assert parse(' hi ') == 'hi'\n",
        encoding="utf-8",
    )
    git(private_repository, "add", ".")
    git(private_repository, "commit", "-m", "fixture parser")
    _initialize(private_repository)
    git(private_repository, "add", ".")
    git(private_repository, "commit", "-m", "initialize harness")

    (private_repository / "src" / "parser.py").write_text(
        "def parse(query):\n"
        "    return '' if query is None else query.strip()\n",
        encoding="utf-8",
    )
    (private_repository / "tests" / "test_parser.py").write_text(
        "from parser import parse\n\n"
        "def test_words():\n    assert parse(' hi ') == 'hi'\n\n"
        "def test_empty_query_does_not_crash():\n"
        "    assert parse(None) == ''\n",
        encoding="utf-8",
    )
    report = run_local_action(
        private_repository,
        "test:python-root:test",
        validation_level="T1",
    )
    assert report["status"] == "passed"
    assert report["returncode"] == 0
    assert report["cwd"] == "."
    assert report["source_refs"] == ["pyproject.toml#pytest-dependency"]
    assert "2 passed" in report["stdout"]
    assert git(private_repository, "status", "--short").splitlines() == [
        "M src/parser.py",
        " M tests/test_parser.py",
    ]


def test_local_action_fails_closed_on_wrong_level_or_missing_binding(
    private_repository: Path,
) -> None:
    (private_repository / "pyproject.toml").write_text(
        "[project]\nname='orders'\nversion='0.1.0'\n"
        "[dependency-groups]\ndev=['pytest>=8']\n"
        "[tool.pytest.ini_options]\npythonpath=['src']\n",
        encoding="utf-8",
    )
    _initialize(private_repository)
    with pytest.raises(ValueError, match="requires at least T1"):
        run_local_action(
            private_repository,
            "test:python-root:test",
            validation_level="T0",
        )
    with pytest.raises(ValueError, match="VALIDATION_BINDING_MISSING"):
        run_local_action(
            private_repository,
            "test:missing:test",
            validation_level="T1",
        )
