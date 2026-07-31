from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml
import pytest

import harness_core
import harness_core.bootstrap as bootstrap
from harness_core.package_resources import repo_skill_bytes


ROOT = Path(__file__).parents[2]


def run_cli(*arguments: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "harness_core.cli", *arguments],
        cwd=cwd or ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def test_version_and_public_cli_are_the_four_v4_commands() -> None:
    version = run_cli("--version")
    help_result = run_cli("--help")

    assert version.returncode == 0
    assert version.stdout.strip() == "harness 4.0.0"
    assert help_result.returncode == 0
    assert "{load,operate,cancel,inspect}" in help_result.stdout
    for legacy in ("init", "project", "validate"):
        assert f"  {legacy} " not in help_result.stdout


def test_new_repository_load_bootstraps_without_existing_skill(
    tmp_path: Path,
) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src/main.py").write_text("VALUE = 1\n", encoding="utf-8")
    assert not (tmp_path / ".agents/skills/harness/SKILL.md").exists()

    result = run_cli("load", str(tmp_path), "--json")
    payload = json.loads(result.stdout)

    assert result.returncode == 0, result.stderr
    assert payload["status"] == "loaded"
    assert (tmp_path / ".harness/governance/state.json").is_file()
    assert (
        tmp_path / ".agents/skills/harness/SKILL.md"
    ).read_bytes() == repo_skill_bytes()
    assert len(payload["projection"]["rules"]) == 4


def test_v301_consumer_is_imported_archived_and_not_a_second_ssot(
    tmp_path: Path,
) -> None:
    harness = tmp_path / ".harness"
    governance = harness / "governance"
    governance.mkdir(parents=True)
    (harness / "harness.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": "3.0.1",
                "rule_instances": {
                    "specification": [],
                    "implementation": [],
                    "verification": [
                        {
                            "rule_id": "contract-tests",
                            "directive": "Run contract tests.",
                            "scope": ["tests/**"],
                        }
                    ],
                    "delivery": [],
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (governance / "model.lock.json").write_text(
        '{"artifact_type":"harness-model-lock"}\n',
        encoding="utf-8",
    )
    old_skill = tmp_path / ".agents/skills/harness/SKILL.md"
    old_skill.parent.mkdir(parents=True)
    old_skill.write_text("# Harness 3.0\n", encoding="utf-8")

    first = run_cli("load", str(tmp_path), "--json")
    first_payload = json.loads(first.stdout)
    state_path = tmp_path / ".harness/governance/state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))

    assert first.returncode == 0
    assert "contract-tests" in state["rules"]
    assert state["rules"]["contract-tests"]["sources"][0][
        "reference"
    ].startswith(".harness/legacy/3.0.1/harness.yaml#")
    assert not (harness / "harness.yaml").exists()
    assert not (governance / "model.lock.json").exists()
    assert (harness / "legacy/3.0.1/harness.yaml").is_file()
    assert (harness / "legacy/3.0.1/model.lock.json").is_file()
    assert (harness / "legacy/3.0.1/SKILL.md").is_file()
    assert first_payload["archived_paths"]

    before = state_path.read_bytes()
    second = run_cli("load", str(tmp_path), "--json")
    second_payload = json.loads(second.stdout)
    assert second.returncode == 0
    assert second_payload["changed"] is False
    assert state_path.read_bytes() == before


def test_recognizable_v2_governance_keeps_its_actual_archive_version(
    tmp_path: Path,
) -> None:
    config = tmp_path / ".harness/harness.yaml"
    config.parent.mkdir(parents=True)
    config.write_text(
        yaml.safe_dump(
            {
                "schema_version": "2.0.0",
                "rule_instances": {
                    "specification": [],
                    "implementation": [],
                    "verification": [
                        {
                            "rule_id": "legacy-tests",
                            "directive": "Run legacy contract tests.",
                            "scope": ["tests/**"],
                        }
                    ],
                    "delivery": [],
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    result = run_cli("load", str(tmp_path), "--json")
    state = harness_core.GovernanceRepository(tmp_path).read()

    assert result.returncode == 0
    assert not config.exists()
    assert (
        tmp_path / ".harness/legacy/2.0.0/harness.yaml"
    ).is_file()
    assert state["rules"]["legacy-tests"]["sources"][0][
        "reference"
    ].startswith(".harness/legacy/2.0.0/harness.yaml#")


def test_cli_operate_cancel_and_inspect_share_authoritative_state(
    tmp_path: Path,
) -> None:
    assert run_cli("load", str(tmp_path), "--json").returncode == 0
    source = {
        "source_type": "user_intent",
        "reference": "user:add-api-rule",
        "digest": "sha256:" + ("6" * 64),
    }
    request = harness_core.build_operation_request(
        "op-add-api-rule",
        "add",
        "api-rule",
        base_revision=0,
        payload={
            "domain": "implementation",
            "directive": "API boundaries use explicit types.",
            "scope": ["src/**"],
            "sources": [source],
        },
    )
    operated = run_cli(
        "operate",
        str(tmp_path),
        "--request-json",
        json.dumps(request),
        "--json",
    )
    assert operated.returncode == 0
    assert json.loads(operated.stdout)["status"] == "applied"

    pending = harness_core.build_operation_request(
        "op-disable-api-rule",
        "disable",
        "api-rule",
        base_revision=1,
    )
    harness_core.GovernanceRepository(tmp_path).register(pending)
    cancelled = run_cli(
        "cancel", str(tmp_path), "op-disable-api-rule", "--json"
    )
    assert cancelled.returncode == 0
    assert json.loads(cancelled.stdout)["status"] == "cancelled"

    inspected = run_cli("inspect", str(tmp_path), "--json")
    summary = json.loads(inspected.stdout)
    assert inspected.returncode == 0
    assert summary["contract_version"] == "4.0.0"
    assert summary["rule_counts"]["enabled"] == 5
    assert summary["pending_operations"] == []


def test_maintainer_repository_cannot_be_loaded_as_consumer() -> None:
    result = run_cli("load", str(ROOT), "--json")
    payload = json.loads(result.stdout)

    assert result.returncode == 2
    assert payload["diagnostics"][0]["code"] == (
        "MAINTAINER_REPOSITORY_FORBIDDEN"
    )
    assert not (ROOT / ".harness/governance/state.json").exists()
    assert not (ROOT / ".agents/skills/harness/SKILL.md").exists()


def test_bootstrap_skill_write_failure_rolls_back_state_and_legacy_move(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = tmp_path / ".harness/harness.yaml"
    config.parent.mkdir(parents=True)
    config.write_text(
        yaml.safe_dump(
            {
                "schema_version": "3.0.1",
                "rule_instances": {
                    "specification": [],
                    "implementation": [],
                    "verification": [],
                    "delivery": [],
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    before = config.read_bytes()

    def fail_write(path: Path, payload: bytes) -> None:
        raise OSError("simulated Skill write failure")

    monkeypatch.setattr(bootstrap, "_atomic_write", fail_write)
    result = bootstrap.load_and_bootstrap(tmp_path)

    assert result["status"] == "blocked"
    assert result["diagnostics"][0]["code"] == "BOOTSTRAP_WRITE_FAILED"
    assert config.read_bytes() == before
    assert not (tmp_path / ".harness/governance/state.json").exists()
    assert not (tmp_path / ".harness/legacy/3.0.1/harness.yaml").exists()
    assert not (tmp_path / ".agents/skills/harness/SKILL.md").exists()
