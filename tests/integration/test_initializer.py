from __future__ import annotations

import json
from pathlib import Path

from harness_core.cli import main
from harness_core.codex_adapter import runtime_state
from harness_core.initializer import (
    apply_initialization_plan,
    build_initialization_plan,
)
from harness_core.package_resources import iter_resource_files, repo_skill_root

from conftest import initialize


def test_init_publishes_exact_skill_without_hooks_and_is_idempotent(
    private_repository: Path,
) -> None:
    (private_repository / "AGENTS.md").write_text(
        "# User instructions\n\nKeep this line.\n",
        encoding="utf-8",
    )
    initialize(private_repository)
    assert "Keep this line." in (
        private_repository / "AGENTS.md"
    ).read_text(encoding="utf-8")
    for relative, expected in iter_resource_files(repo_skill_root()):
        assert (
            private_repository / ".agents/skills/harness" / relative
        ).read_bytes() == expected
    assert (
        private_repository
        / ".agents/skills/harness/agents/openai.yaml"
    ).is_file()
    assert not (private_repository / ".codex/hooks.json").exists()
    assert runtime_state(private_repository)["status"] == "active"

    second = build_initialization_plan(private_repository)
    assert second["blocker_codes"] == []
    assert second["write_scope"] == []


def test_with_hooks_is_explicit_and_does_not_change_runtime_authority(
    private_repository: Path,
) -> None:
    config_dir = private_repository / ".codex"
    config_dir.mkdir()
    (config_dir / "config.toml").write_text(
        "[features]\nweb_search = true\n",
        encoding="utf-8",
    )
    initialize(private_repository, with_hooks=True)
    config = (config_dir / "config.toml").read_text(encoding="utf-8")
    assert config.count("[features]") == 1
    assert "hooks = true" in config
    hooks = json.loads((config_dir / "hooks.json").read_text(encoding="utf-8"))
    assert "sdd-harness hook" in json.dumps(hooks)
    state = runtime_state(private_repository)
    assert state["status"] == "active"
    assert state["hook_defense"] == "configured"


def test_v1_migration_is_zero_write_then_digest_approved(
    private_repository: Path,
) -> None:
    harness = private_repository / ".harness"
    harness.mkdir()
    legacy = (
        "schema_version: 1.0.0\n"
        "mode: adopt\n"
        "standing_policy: {}\n"
    )
    (harness / "harness.yaml").write_text(legacy, encoding="utf-8")
    before = {
        path.relative_to(private_repository).as_posix(): path.read_bytes()
        for path in private_repository.rglob("*")
        if path.is_file() and ".git" not in path.parts
    }
    plan = build_initialization_plan(private_repository)
    after_plan = {
        path.relative_to(private_repository).as_posix(): path.read_bytes()
        for path in private_repository.rglob("*")
        if path.is_file() and ".git" not in path.parts
    }
    assert before == after_plan
    assert plan["migration_from"] == "1.0.0"
    assert plan["drift_report"]

    refused = apply_initialization_plan(
        private_repository, plan, approved_plan_digest=None
    )
    assert refused["blocker_codes"] == ["MIGRATION_REQUIRED"]
    applied = apply_initialization_plan(
        private_repository,
        plan,
        approved_plan_digest=plan["plan_digest"],
    )
    assert applied["status"] == "applied"
    assert runtime_state(private_repository)["status"] == "active"


def test_migration_yes_is_refused_and_changed_plan_is_stale(
    private_repository: Path,
    capsys,
) -> None:
    harness = private_repository / ".harness"
    harness.mkdir()
    (harness / "harness.yaml").write_text(
        "schema_version: 1.0.0\nmode: adopt\n",
        encoding="utf-8",
    )
    plan = build_initialization_plan(private_repository)
    assert main(
        ["init", str(private_repository), "--yes", "--json"]
    ) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "migration-required"
    (private_repository / "pyproject.toml").write_text(
        "[project]\nname='changed'\nversion='0.2.0'\n",
        encoding="utf-8",
    )
    result = apply_initialization_plan(
        private_repository,
        plan,
        approved_plan_digest=plan["plan_digest"],
    )
    assert result["blocker_codes"] == ["MIGRATION_PLAN_STALE"]
