from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest

from harness_core import apply_plan, build_plan, discover_repository, validate_config


ROOT = Path(__file__).parents[2]
FIXTURES = ROOT / "tests" / "fixtures"
SKILL = ROOT / "skills" / "initialize-ai-coding-harness"
ASSETS = SKILL / "assets"
SCHEMAS = ASSETS / "schemas"


def _copy_fixture(tmp_path: Path, name: str) -> Path:
    target = tmp_path / name
    shutil.copytree(FIXTURES / name, target)
    return target


def _checksums(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
    }


@pytest.mark.parametrize(
    ("fixture", "project_types"),
    [
        ("empty-project", []),
        ("python-project", ["python"]),
        ("node-project", ["node"]),
        ("existing-github-actions", ["node"]),
        ("monorepo", ["python", "node"]),
    ],
)
def test_discovery_reports_project_facts(
    fixture: str, project_types: list[str]
) -> None:
    facts = discover_repository(FIXTURES / fixture)

    assert facts["project_types"] == project_types


def test_audit_is_read_only(tmp_path: Path) -> None:
    repository = _copy_fixture(tmp_path, "python-project")
    before = _checksums(repository)

    facts = discover_repository(repository)
    plan = build_plan(facts, "audit")

    assert plan["read_only"] is True
    assert plan["actions"] == []
    assert _checksums(repository) == before


def test_bootstrap_applies_only_approved_plan_and_is_idempotent(
    tmp_path: Path,
) -> None:
    repository = _copy_fixture(tmp_path, "python-project")
    plan = build_plan(discover_repository(repository), "bootstrap")
    plan["approved"] = True

    first = apply_plan(plan, ASSETS)
    second = apply_plan(plan, ASSETS)

    assert set(first["changed"]) == {
        "AGENTS.md",
        ".harness/harness.yaml",
        ".harness/boundaries.yaml",
        ".harness/tools.yaml",
        ".harness/tasks.yaml",
        ".harness/impact.yaml",
        ".harness/pipelines/merge.yaml",
        ".harness/pipelines/publish.yaml",
        ".harness/adapters/local.yaml",
        ".harness/.gitignore",
    }
    assert second["changed"] == []
    assert validate_config(repository / ".harness", SCHEMAS) == []
    assert not (repository / ".github").exists()


def test_unapproved_plan_cannot_write(tmp_path: Path) -> None:
    repository = _copy_fixture(tmp_path, "python-project")
    plan = build_plan(discover_repository(repository), "bootstrap")

    with pytest.raises(PermissionError, match="not approved"):
        apply_plan(plan, ASSETS)

    assert not (repository / ".harness").exists()


def test_out_of_scope_action_is_rejected(tmp_path: Path) -> None:
    repository = _copy_fixture(tmp_path, "python-project")
    plan = build_plan(discover_repository(repository), "bootstrap")
    plan["approved"] = True
    plan["actions"][0]["path"] = "pyproject.toml"

    with pytest.raises(PermissionError, match="WRITE_SCOPE_EXPANDED"):
        apply_plan(plan, ASSETS)


def test_adopt_preserves_existing_agents_and_workflow(tmp_path: Path) -> None:
    repository = _copy_fixture(tmp_path, "existing-github-actions")
    workflow = repository / ".github" / "workflows" / "ci.yml"
    original_workflow = workflow.read_bytes()
    plan = build_plan(discover_repository(repository), "adopt")
    plan["approved"] = True

    result = apply_plan(plan, ASSETS)
    agents = (repository / "AGENTS.md").read_text("utf-8")

    assert "Keep this instruction." in agents
    assert "<!-- ai-coding-harness -->" in agents
    assert workflow.read_bytes() == original_workflow
    assert ".github/workflows/ci.yml" in plan["preserve"]
    assert "AGENTS.md" in result["changed"]


def test_protected_external_trigger_blocks_adopt() -> None:
    facts = discover_repository(FIXTURES / "protected-github-actions")
    plan = build_plan(facts, "adopt")

    assert plan["blocker_codes"] == ["PROTECTED_TRIGGER_UNCONTROLLED"]


def test_empty_project_blocks_bootstrap() -> None:
    facts = discover_repository(FIXTURES / "empty-project")
    plan = build_plan(facts, "bootstrap")

    assert "CONFIG_INVALID" in plan["blocker_codes"]


def test_update_of_current_scaffold_is_idempotent(tmp_path: Path) -> None:
    repository = _copy_fixture(tmp_path, "node-project")
    bootstrap = build_plan(discover_repository(repository), "bootstrap")
    bootstrap["approved"] = True
    apply_plan(bootstrap, ASSETS)

    update = build_plan(discover_repository(repository), "update")
    update["approved"] = True
    result = apply_plan(update, ASSETS)

    assert all(action["action"] == "update" for action in update["actions"])
    assert result["changed"] == []


def test_bootstrap_creates_github_actions_only_when_selected(
    tmp_path: Path,
) -> None:
    repository = _copy_fixture(tmp_path, "python-project")
    facts = discover_repository(repository)
    facts["selected_backends"] = ["local", "github-actions"]
    plan = build_plan(facts, "bootstrap")
    plan["approved"] = True

    result = apply_plan(plan, ASSETS)

    assert ".github/workflows/harness.yml" in result["changed"]
    assert ".harness/adapters/github-actions.yaml" in result["changed"]
    assert "workflow_dispatch" in (
        repository / ".github" / "workflows" / "harness.yml"
    ).read_text("utf-8")
