from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

import harness_core


ROOT = Path(__file__).parents[2]


def run_cli(*arguments: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "harness_core.cli", *arguments],
        cwd=cwd or ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def file_snapshot(repository: Path) -> dict[str, bytes]:
    return {
        path.relative_to(repository).as_posix(): path.read_bytes()
        for path in repository.rglob("*")
        if path.is_file()
    }


def test_help_lists_only_four_local_commands() -> None:
    result = run_cli("--help")
    assert result.returncode == 0
    assert "{init,project,validate,inspect}" in result.stdout
    forbidden = [
        "commit-plan",
        "decision",
        "delivery-plan",
        "hook",
        "issue-plan",
        "mcp",
        "policy-plan",
        "projection-plan",
        "push-plan",
        "run-action",
        "run-task",
    ]
    for command in forbidden:
        assert command not in result.stdout

    for command in ("init", "project", "validate", "inspect"):
        child = run_cli(command, "--help")
        assert child.returncode == 0
        for option in (
            "--action",
            "--approve",
            "--assignee",
            "--branch",
            "--provider",
            "--remote",
            "--task",
        ):
            assert option not in child.stdout


def test_empty_directory_init_validate_inspect_is_minimal(
    tmp_path: Path,
) -> None:
    initialized = run_cli("init", str(tmp_path), "--json")
    assert initialized.returncode == 0, initialized.stderr
    init_result = json.loads(initialized.stdout)
    assert init_result["status"] == "initialized"

    files = set(file_snapshot(tmp_path))
    assert files == {
        ".agents/skills/harness/SKILL.md",
        ".harness/governance/model.lock.json",
        ".harness/harness.yaml",
    }
    before_validate = file_snapshot(tmp_path)

    validated = run_cli("validate", str(tmp_path), "--json")
    inspected = run_cli("inspect", str(tmp_path), "--json")

    assert validated.returncode == 0
    assert json.loads(validated.stdout) == {
        "diagnostics": [],
        "repository": str(tmp_path.resolve()),
        "status": "valid",
    }
    assert inspected.returncode == 0
    inspect_result = json.loads(inspected.stdout)
    assert inspect_result["status"] == "valid"
    assert inspect_result["schema_version"] == "3.0.1"
    assert inspect_result["core_version"] == "3.0.1"
    assert inspect_result["contract_version"] == "3.0.1"
    assert inspect_result["compiler_version"] == "3.0.1"
    assert inspect_result["rule_counts"] == {
        "specification": 0,
        "implementation": 0,
        "verification": 0,
        "delivery": 0,
    }
    assert file_snapshot(tmp_path) == before_validate
    assert not (tmp_path / ".codex").exists()
    assert not (tmp_path / "plugins").exists()


def test_project_updates_rules_and_inspect_counts(tmp_path: Path) -> None:
    assert run_cli("init", str(tmp_path), "--json").returncode == 0
    config_path = tmp_path / ".harness" / "harness.yaml"
    value = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    value["rule_instances"]["implementation"] = [
        {
            "rule_id": "typed-boundaries",
            "directive": "Use explicit types at public boundaries.",
            "scope": ["src/**"],
        }
    ]
    config_path.write_text(
        yaml.safe_dump(value, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    projected = run_cli("project", str(tmp_path), "--json")
    validated = run_cli("validate", str(tmp_path), "--json")
    inspected = run_cli("inspect", str(tmp_path), "--json")

    assert projected.returncode == 0
    assert json.loads(projected.stdout)["status"] == "projected"
    assert validated.returncode == 0
    assert json.loads(inspected.stdout)["rule_counts"]["implementation"] == 1


def test_init_is_idempotent_for_exact_v3_files(tmp_path: Path) -> None:
    assert run_cli("init", str(tmp_path), "--json").returncode == 0
    before = file_snapshot(tmp_path)
    second = run_cli("init", str(tmp_path), "--json")
    assert second.returncode == 0
    assert json.loads(second.stdout)["created_paths"] == []
    assert file_snapshot(tmp_path) == before


def test_v2_consumer_is_rejected_with_zero_writes(tmp_path: Path) -> None:
    harness = tmp_path / ".harness"
    harness.mkdir()
    (harness / "harness.yaml").write_text(
        "schema_version: 2.0.0\nmode: adopt\n",
        encoding="utf-8",
    )
    (harness / "tasks.yaml").write_text(
        "tasks: []\n",
        encoding="utf-8",
    )
    before = file_snapshot(tmp_path)

    result = run_cli("init", str(tmp_path), "--json")

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["status"] == "blocked"
    assert any(
        item["code"] == "SCHEMA_VERSION_UNSUPPORTED"
        for item in payload["diagnostics"]
    )
    assert file_snapshot(tmp_path) == before


def test_legacy_artifact_without_config_is_not_deleted_or_migrated(
    tmp_path: Path,
) -> None:
    governance = tmp_path / ".harness" / "governance"
    governance.mkdir(parents=True)
    legacy = governance / "action-graph.json"
    legacy.write_text('{"artifact_type":"action-graph"}\n', encoding="utf-8")
    before = file_snapshot(tmp_path)

    result = run_cli("init", str(tmp_path), "--json")

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["diagnostics"][0]["code"] == "LEGACY_HARNESS_INPUT"
    assert file_snapshot(tmp_path) == before


def test_package_surface_and_source_tree_have_no_old_modules() -> None:
    expected_modules = {
        "__init__.py",
        "artifacts.py",
        "cli.py",
        "contracts.py",
        "initializer.py",
        "model.py",
        "package_resources.py",
        "projection.py",
    }
    source_root = ROOT / "src" / "harness_core"
    assert {
        path.name for path in source_root.glob("*.py")
    } == expected_modules
    assert not [
        path for path in (ROOT / "plugins").rglob("*") if path.is_file()
    ]
    assert not [
        path
        for path in (
            source_root
            / "resources"
            / "repo_skill"
            / "repo-documentation-maker"
        ).rglob("*")
        if path.is_file()
    ]
    assert {
        path.relative_to(
            source_root / "resources" / "repo_skill" / "harness"
        ).as_posix()
        for path in (
            source_root / "resources" / "repo_skill" / "harness"
        ).rglob("*")
        if path.is_file()
    } == {"SKILL.md"}

    forbidden_exports = {
        "build_action_graph",
        "create_task_decision",
        "apply_push_plan",
        "build_controlled_delivery_plan",
        "handle_hook",
        "select_validation",
        "validate_runtime_artifact",
    }
    assert forbidden_exports.isdisjoint(harness_core.__all__)


def test_repository_has_no_tmp_tracking_or_v2_governance_file() -> None:
    tracked = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    assert not [path for path in tracked if path.startswith(".tmp/")]
    forbidden = {
        ".harness/governance/action-graph.json",
        ".harness/governance/compatibility.json",
        ".harness/governance/projection.lock.json",
        ".harness/governance/rules.json",
        ".harness/governance/sources.lock.json",
    }
    assert all(not (ROOT / path).exists() for path in forbidden)
