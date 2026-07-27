from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from harness_core import (
    apply_plan,
    attach_digest,
    build_plan,
    create_plan_approval,
    discover_repository,
    validate_config,
    validate_runtime_artifact,
)


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


def test_python_test_command_uses_only_a_source_backed_runner() -> None:
    without_uv = discover_repository(FIXTURES / "python-project")
    command = without_uv["project_units"][0]["commands"][0]

    assert command["argv"] == ["python", "-m", "pytest"]
    assert command["source"] == "pyproject.toml#pytest-dependency"


def test_delivery_semantics_inside_a_misleading_script_name_fail_closed(
    tmp_path: Path,
) -> None:
    repository = _copy_fixture(tmp_path, "node-project")
    package_path = repository / "package.json"
    package = json.loads(package_path.read_text("utf-8"))
    package["scripts"]["lint"] = "npm publish"
    package_path.write_text(json.dumps(package), encoding="utf-8")

    plan = build_plan(discover_repository(repository), "adopt")
    tasks = yaml.safe_load(plan["render_context"]["tasks_yaml"])["tasks"]
    tools = yaml.safe_load(plan["render_context"]["tools_yaml"])["tools"]
    publish_task = next(task for task in tasks if task["category"] == "publish")

    assert publish_task["automation_level"] == "critical"
    assert publish_task["auto_allowed"] is False
    assert any(
        tool.get("task_ref") == publish_task["id"]
        and tool["action_semantics"] == "publish"
        and tool["invocation_mode"] == "managed"
        for tool in tools
    )


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
    approval = create_plan_approval(plan, "2026-07-24T00:00:00Z")

    first = apply_plan(plan, ASSETS, approval)
    second = apply_plan(plan, ASSETS, approval)

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


def test_bootstrap_python_manifest_without_commands_creates_empty_catalog(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "minimal-python"
    repository.mkdir()
    (repository / "pyproject.toml").write_text(
        '[project]\nname = "minimal"\nversion = "0.1.0"\n'
        'requires-python = ">=3.12"\n',
        encoding="utf-8",
    )

    plan = build_plan(discover_repository(repository), "bootstrap")

    assert plan["blocker_codes"] == []
    assert yaml.safe_load(plan["render_context"]["tasks_yaml"]) == {"tasks": []}
    approval = create_plan_approval(plan, "2026-07-24T00:00:00Z")
    first = apply_plan(plan, ASSETS, approval)
    second = apply_plan(plan, ASSETS, approval)

    assert first["changed"]
    assert second["changed"] == []
    assert validate_config(repository / ".harness", ASSETS / "schemas") == []
    assert validate_config(repository / ".harness", SCHEMAS) == []
    assert validate_runtime_artifact(plan, SCHEMAS) == []
    assert validate_runtime_artifact(approval, SCHEMAS) == []
    assert not (repository / ".github").exists()
    assert "approved" not in plan


def test_unapproved_plan_cannot_write(tmp_path: Path) -> None:
    repository = _copy_fixture(tmp_path, "python-project")
    plan = build_plan(discover_repository(repository), "bootstrap")

    with pytest.raises(PermissionError, match="HANDOFF_REQUIRED"):
        apply_plan(plan, ASSETS)

    assert not (repository / ".harness").exists()


def test_out_of_scope_action_is_rejected(tmp_path: Path) -> None:
    repository = _copy_fixture(tmp_path, "python-project")
    before = _checksums(repository)
    plan = build_plan(discover_repository(repository), "bootstrap")
    plan["actions"][0]["path"] = "pyproject.toml"
    plan = attach_digest(plan, "plan_digest")
    approval = create_plan_approval(plan, "2026-07-24T00:00:00Z")

    with pytest.raises(PermissionError, match="WRITE_SCOPE_EXPANDED"):
        apply_plan(plan, ASSETS, approval)

    assert _checksums(repository) == before
    assert not (repository / ".harness").exists()


def test_mismatched_approval_is_rejected_without_writes(tmp_path: Path) -> None:
    repository = _copy_fixture(tmp_path, "python-project")
    before = _checksums(repository)
    plan = build_plan(discover_repository(repository), "bootstrap")
    approval = create_plan_approval(plan, "2026-07-24T00:00:00Z")
    approval["plan_digest"] = "sha256:" + "0" * 64

    with pytest.raises(PermissionError, match="PLAN_STALE"):
        apply_plan(plan, ASSETS, approval)

    assert _checksums(repository) == before
    assert not (repository / ".harness").exists()


def test_adopt_preserves_existing_agents_and_workflow(tmp_path: Path) -> None:
    repository = _copy_fixture(tmp_path, "existing-github-actions")
    workflow = repository / ".github" / "workflows" / "ci.yml"
    original_workflow = workflow.read_bytes()
    plan = build_plan(discover_repository(repository), "adopt")
    approval = create_plan_approval(plan, "2026-07-24T00:00:00Z")

    result = apply_plan(plan, ASSETS, approval)
    agents = (repository / "AGENTS.md").read_text("utf-8")

    assert "Keep this instruction." in agents
    assert "<!-- ai-coding-harness:start -->" in agents
    assert "<!-- ai-coding-harness:end -->" in agents
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
    bootstrap_approval = create_plan_approval(
        bootstrap, "2026-07-24T00:00:00Z"
    )
    apply_plan(bootstrap, ASSETS, bootstrap_approval)

    update = build_plan(discover_repository(repository), "update")
    update_approval = create_plan_approval(
        update, "2026-07-24T00:01:00Z"
    )
    result = apply_plan(update, ASSETS, update_approval)

    assert all(action["action"] == "update" for action in update["actions"])
    assert result["changed"] == []


def test_bootstrap_creates_github_actions_only_when_selected(
    tmp_path: Path,
) -> None:
    repository = _copy_fixture(tmp_path, "python-project")
    facts = discover_repository(repository)
    facts["selected_backends"] = ["local", "github-actions"]
    plan = build_plan(facts, "bootstrap")
    approval = create_plan_approval(plan, "2026-07-24T00:00:00Z")

    result = apply_plan(plan, ASSETS, approval)

    assert ".github/workflows/harness.yml" in result["changed"]
    assert ".harness/adapters/github-actions.yaml" in result["changed"]
    assert "workflow_dispatch" in (
        repository / ".github" / "workflows" / "harness.yml"
    ).read_text("utf-8")


def test_plan_change_after_approval_is_stale_and_writes_nothing(
    tmp_path: Path,
) -> None:
    repository = _copy_fixture(tmp_path, "python-project")
    plan = build_plan(discover_repository(repository), "bootstrap")
    approval = create_plan_approval(plan, "2026-07-24T00:00:00Z")
    plan["write_scope"].append("src/**")

    with pytest.raises(PermissionError, match="PLAN_STALE"):
        apply_plan(plan, ASSETS, approval)

    assert not (repository / ".harness").exists()


def test_target_change_after_plan_is_stale_and_writes_nothing(
    tmp_path: Path,
) -> None:
    repository = _copy_fixture(tmp_path, "existing-github-actions")
    plan = build_plan(discover_repository(repository), "adopt")
    approval = create_plan_approval(plan, "2026-07-24T00:00:00Z")
    (repository / "AGENTS.md").write_text(
        "# Changed after planning\n", encoding="utf-8"
    )

    with pytest.raises(PermissionError, match="PLAN_STALE"):
        apply_plan(plan, ASSETS, approval)

    assert not (repository / ".harness").exists()


def test_monorepo_generates_independent_tools_tasks_and_impact_rules() -> None:
    facts = discover_repository(FIXTURES / "monorepo")
    plan = build_plan(facts, "bootstrap")
    tasks = yaml.safe_load(plan["render_context"]["tasks_yaml"])["tasks"]
    tools = yaml.safe_load(plan["render_context"]["tools_yaml"])["tools"]
    rules = yaml.safe_load(plan["render_context"]["impact_yaml"])["rules"]

    task_ids = {task["id"] for task in tasks}
    assert task_ids == {"test:python-root", "test:node-packages-web"}
    assert {
        tool["task_ref"]
        for tool in tools
        if tool["invocation_mode"] == "managed"
    } == task_ids
    assert {
        tool["id"]
        for tool in tools
        if tool["type"] == "runtime"
    } == {"runtime-python-root", "runtime-node-packages-web"}
    assert {"unit-python-root", "unit-node-packages-web"} <= {
        rule["id"] for rule in rules
    }


def test_existing_workflow_job_uses_github_actions_source() -> None:
    facts = discover_repository(FIXTURES / "existing-github-actions")
    plan = build_plan(facts, "adopt")
    tasks = yaml.safe_load(plan["render_context"]["tasks_yaml"])["tasks"]
    workflow_task = next(
        task for task in tasks if task["id"] == "test:github-ci-test"
    )

    assert workflow_task["backend"] == "github-actions"
    assert workflow_task["source"] == ".github/workflows/ci.yml#jobs.test"
    assert "command_source" not in workflow_task
    assert any(
        task["backend"] == "local"
        and task["command_source"] == "package.json#scripts.test"
        for task in tasks
    )


def test_unsupported_systems_are_source_backed_gaps(tmp_path: Path) -> None:
    repository = _copy_fixture(tmp_path, "node-project")
    (repository / "Makefile").write_text("test:\n\tnpm test\n", encoding="utf-8")
    (repository / "build.gradle.kts").write_text(
        "plugins { java }\n", encoding="utf-8"
    )
    (repository / "pom.xml").write_text("<project />\n", encoding="utf-8")
    (repository / "Fastfile").write_text(
        "lane :release do\nend\n", encoding="utf-8"
    )
    (repository / ".mcp.json").write_text("{}\n", encoding="utf-8")

    facts = discover_repository(repository)
    gaps = {(gap["source"], gap["code"]) for gap in facts["gaps"]}
    plan = build_plan(facts, "adopt")

    assert ("Makefile", "ACTION_CLASSIFICATION_UNRESOLVED") in gaps
    assert ("build.gradle.kts", "ACTION_CLASSIFICATION_UNRESOLVED") in gaps
    assert ("pom.xml", "ACTION_CLASSIFICATION_UNRESOLVED") in gaps
    assert ("Fastfile", "ACTION_CLASSIFICATION_UNRESOLVED") in gaps
    assert (".mcp.json", "TOOL_NOT_REGISTERED") in gaps
    assert all(gap["severity"] == "source-backed" for gap in facts["gaps"])
    assert "ACTION_CLASSIFICATION_UNRESOLVED" in plan["blocker_codes"]
    assert "TOOL_NOT_REGISTERED" in plan["blocker_codes"]


def test_unreferenced_repository_script_is_a_blocking_source_gap(
    tmp_path: Path,
) -> None:
    repository = _copy_fixture(tmp_path, "node-project")
    script = repository / "scripts" / "mystery.ps1"
    script.parent.mkdir()
    script.write_text("Write-Output 'unknown'\n", encoding="utf-8")

    facts = discover_repository(repository)
    plan = build_plan(facts, "adopt")
    tasks = yaml.safe_load(plan["render_context"]["tasks_yaml"])["tasks"]

    assert any(
        gap["source"] == "scripts/mystery.ps1"
        and gap["severity"] == "source-backed"
        and gap["blocks_plan"] is True
        for gap in facts["gaps"]
    )
    assert "ACTION_CLASSIFICATION_UNRESOLVED" in plan["blocker_codes"]
    assert not any("mystery" in task["id"] for task in tasks)


def test_update_preserves_custom_configuration_mode_and_adapter(
    tmp_path: Path,
) -> None:
    repository = _copy_fixture(tmp_path, "node-project")
    bootstrap = build_plan(discover_repository(repository), "bootstrap")
    apply_plan(
        bootstrap,
        ASSETS,
        create_plan_approval(bootstrap, "2026-07-24T00:00:00Z"),
    )
    harness_path = repository / ".harness" / "harness.yaml"
    harness = yaml.safe_load(harness_path.read_text("utf-8"))
    harness["mode"] = "adopt"
    harness_path.write_text(
        yaml.safe_dump(harness, sort_keys=False), encoding="utf-8"
    )
    tools_path = repository / ".harness" / "tools.yaml"
    tools = yaml.safe_load(tools_path.read_text("utf-8"))
    tools["tools"][0]["purpose"] = "custom-repository-search"
    tools_path.write_text(
        yaml.safe_dump(tools, sort_keys=False), encoding="utf-8"
    )
    custom_adapter = repository / ".harness" / "adapters" / "custom.yaml"
    custom_adapter.write_text("id: custom\ntype: custom\n", encoding="utf-8")
    before = _checksums(repository)

    update = build_plan(discover_repository(repository), "update")
    result = apply_plan(
        update,
        ASSETS,
        create_plan_approval(update, "2026-07-24T00:01:00Z"),
    )

    assert result["changed"] == []
    assert _checksums(repository) == before
    assert ".harness/adapters/custom.yaml" in update["preserve"]
    assert all(item["decision"] == "preserve" for item in update["drift"])
    assert all(item["field"] != "*" for item in update["drift"])


def test_update_rejects_legacy_configuration_without_migration(
    tmp_path: Path,
) -> None:
    repository = _copy_fixture(tmp_path, "node-project")
    bootstrap = build_plan(discover_repository(repository), "bootstrap")
    apply_plan(
        bootstrap,
        ASSETS,
        create_plan_approval(bootstrap, "2026-07-24T00:00:00Z"),
    )
    harness_path = repository / ".harness" / "harness.yaml"
    harness_path.write_text(
        harness_path.read_text("utf-8").replace("0.3.0", "0.2.0"),
        encoding="utf-8",
    )

    update = build_plan(discover_repository(repository), "update")

    assert {"CONFIG_INVALID", "HANDOFF_REQUIRED"} <= set(
        update["blocker_codes"]
    )
    assert any(
        item["field"] == "schema_version" and item["decision"] == "block"
        for item in update["drift"]
    )


def test_discovery_fact_change_after_approval_is_zero_write(
    tmp_path: Path,
) -> None:
    repository = _copy_fixture(tmp_path, "node-project")
    plan = build_plan(discover_repository(repository), "bootstrap")
    approval = create_plan_approval(plan, "2026-07-24T00:00:00Z")
    package_path = repository / "package.json"
    package = json.loads(package_path.read_text("utf-8"))
    package["scripts"]["build"] = "node build.js"
    package_path.write_text(json.dumps(package), encoding="utf-8")

    with pytest.raises(PermissionError, match="PLAN_STALE"):
        apply_plan(plan, ASSETS, approval)

    assert not (repository / ".harness").exists()


def test_referenced_script_change_after_approval_is_zero_write(
    tmp_path: Path,
) -> None:
    repository = _copy_fixture(tmp_path, "node-project")
    script = repository / "scripts" / "test.js"
    script.parent.mkdir()
    script.write_text("console.log('before')\n", encoding="utf-8")
    package_path = repository / "package.json"
    package = json.loads(package_path.read_text("utf-8"))
    package["scripts"]["test"] = "node scripts/test.js"
    package_path.write_text(json.dumps(package), encoding="utf-8")
    plan = build_plan(discover_repository(repository), "bootstrap")
    approval = create_plan_approval(plan, "2026-07-24T00:00:00Z")
    script.write_text("console.log('after')\n", encoding="utf-8")

    with pytest.raises(PermissionError, match="PLAN_STALE"):
        apply_plan(plan, ASSETS, approval)

    assert not (repository / ".harness").exists()


def test_update_preserved_config_change_after_approval_is_zero_write(
    tmp_path: Path,
) -> None:
    repository = _copy_fixture(tmp_path, "node-project")
    bootstrap = build_plan(discover_repository(repository), "bootstrap")
    apply_plan(
        bootstrap,
        ASSETS,
        create_plan_approval(bootstrap, "2026-07-24T00:00:00Z"),
    )
    update = build_plan(discover_repository(repository), "update")
    approval = create_plan_approval(update, "2026-07-24T00:01:00Z")
    tools_path = repository / ".harness" / "tools.yaml"
    tools = yaml.safe_load(tools_path.read_text("utf-8"))
    tools["tools"][0]["purpose"] = "changed-after-approval"
    tools_path.write_text(
        yaml.safe_dump(tools, sort_keys=False), encoding="utf-8"
    )
    before_agents = (repository / "AGENTS.md").read_bytes()

    with pytest.raises(PermissionError, match="PLAN_STALE"):
        apply_plan(update, ASSETS, approval)

    assert (repository / "AGENTS.md").read_bytes() == before_agents
    assert yaml.safe_load(tools_path.read_text("utf-8"))["tools"][0][
        "purpose"
    ] == "changed-after-approval"


def test_discover_and_plan_refuse_output_inside_target_repository(
    tmp_path: Path,
) -> None:
    repository = _copy_fixture(tmp_path, "node-project")
    discover_script = SKILL / "scripts" / "discover_repository.py"
    discover_result = subprocess.run(
        [
            sys.executable,
            str(discover_script),
            str(repository),
            "--output",
            str(repository / "facts.json"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    facts_path = tmp_path / "facts.json"
    facts_path.write_text(
        json.dumps(discover_repository(repository)), encoding="utf-8"
    )
    plan_result = subprocess.run(
        [
            sys.executable,
            str(SKILL / "scripts" / "build_plan.py"),
            str(facts_path),
            "--mode",
            "bootstrap",
            "--output",
            str(repository / "plan.json"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert discover_result.returncode != 0
    assert plan_result.returncode != 0
    assert not (repository / "facts.json").exists()
    assert not (repository / "plan.json").exists()
