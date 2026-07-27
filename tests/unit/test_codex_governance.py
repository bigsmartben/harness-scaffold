from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from harness_core import (
    apply_initialization_plan,
    build_initialization_plan,
    expected_projection_lanes,
    handle_hook,
    runtime_state,
    validate_agent_directory,
    validate_parent_permissions,
    validate_projection_results,
    validate_single_writer,
)
from harness_core.mcp_server import TOOLS, call_tool


ROOT = Path(__file__).parents[2]
PLUGIN = ROOT / "plugins" / "harness"


def _initialized_repository(tmp_path: Path) -> Path:
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "fixture"
version = "0.1.0"
dependencies = ["pytest>=8"]

[tool.ai-coding-harness.tasks]
test = ["python", "-m", "pytest"]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    plan = build_initialization_plan(tmp_path)
    assert apply_initialization_plan(tmp_path, plan)["status"] == "applied"
    return tmp_path


def test_generated_custom_agents_have_valid_single_responsibility_contracts(
    tmp_path: Path,
) -> None:
    repository = _initialized_repository(tmp_path)
    assert not validate_agent_directory(repository / ".codex" / "agents")
    assert len(list((repository / ".codex" / "agents").glob("*.toml"))) == 6


def test_agent_discovery_rejects_missing_unmanaged_and_parent_permission_escalation(
    tmp_path: Path,
) -> None:
    repository = _initialized_repository(tmp_path)
    agent_dir = repository / ".codex" / "agents"
    missing = agent_dir / "repo-mapper.toml"
    missing.unlink()
    issues = validate_agent_directory(agent_dir)
    assert any(
        "AGENT_BINDING_UNAVAILABLE" in issue["blocker_codes"] for issue in issues
    )

    plan = build_initialization_plan(repository)
    assert "GOVERNANCE_CONFLICT" not in plan["blocker_codes"]
    assert apply_initialization_plan(repository, plan)["status"] == "applied"
    governed = agent_dir / "governed-worker.toml"
    governed.write_text(
        governed.read_text(encoding="utf-8").removeprefix(
            "# managed-by: sdd-harness\n"
        ),
        encoding="utf-8",
    )
    assert any(
        "AGENT_CONFIGURATION_UNTRUSTED" in issue["blocker_codes"]
        for issue in validate_agent_directory(agent_dir)
    )
    assert "GOVERNANCE_CONFLICT" in build_initialization_plan(repository)[
        "blocker_codes"
    ]
    assert validate_parent_permissions("governed_worker", "read-only") == [
        "AGENT_CONFIGURATION_UNTRUSTED",
        "HANDOFF_REQUIRED",
    ]
    assert not validate_parent_permissions("repo_mapper", "workspace-write")


def test_projection_orchestration_requires_all_twelve_lanes() -> None:
    results = [
        {
            "audience": audience,
            "subdomain": subdomain,
            "status": "completed",
            "candidate_digest": f"sha256:{index:064x}",
        }
        for index, (audience, subdomain) in enumerate(expected_projection_lanes())
    ]
    assert len(results) == 12
    assert not validate_projection_results(results)
    assert "GOVERNANCE_COVERAGE_INCOMPLETE" in validate_projection_results(results[:-1])
    assert "GOVERNANCE_COVERAGE_INCOMPLETE" in validate_projection_results(
        results + [results[0]]
    )
    invalid = [dict(item) for item in results]
    invalid[0]["candidate_digest"] = "not-a-digest"
    assert "AGENT_BINDING_UNAVAILABLE" in validate_projection_results(invalid)


def test_parallel_writers_must_have_non_overlapping_ownership() -> None:
    assert not validate_single_writer(
        [
            {
                "owner": "worker-a",
                "sandbox_mode": "workspace-write",
                "scope": ["src/a"],
            },
            {
                "owner": "worker-b",
                "sandbox_mode": "workspace-write",
                "scope": ["src/b"],
            },
        ]
    )
    assert "GOVERNANCE_SCOPE_UNRESOLVED" in validate_single_writer(
        [
            {
                "owner": "worker-a",
                "sandbox_mode": "workspace-write",
                "scope": ["src"],
            },
            {
                "owner": "worker-b",
                "sandbox_mode": "workspace-write",
                "scope": ["src/api"],
            },
        ]
    )


def test_codex_hook_enters_bootstrap_only_and_blocks_raw_test_bypass(
    tmp_path: Path,
) -> None:
    uninitialized = handle_hook(
        {
            "hook_event_name": "SessionStart",
            "cwd": str(tmp_path),
            "permission_mode": "default",
        },
        tmp_path,
    )
    assert "bootstrap-only" in uninitialized["systemMessage"]

    repository = _initialized_repository(tmp_path)
    assert runtime_state(repository)["mode"] == "active"
    blocked = handle_hook(
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "python -m pytest"},
            "cwd": str(repository),
        },
        repository,
    )
    assert (
        blocked["hookSpecificOutput"]["permissionDecisionReason"].startswith(
            "INVOCATION_BYPASS_ATTEMPT"
        )
    )


def test_plugin_declares_only_narrow_mcp_tools_and_valid_hook_events() -> None:
    manifest = json.loads(
        (PLUGIN / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    hooks = json.loads((PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    tool_names = {item["name"] for item in TOOLS}

    assert manifest["name"] == "harness"
    assert manifest["version"] == "1.0.0"
    assert tool_names == {
        "get_projection",
        "resolve_action",
        "explain_blocker",
        "prepare_action_request",
    }
    assert "execute" not in " ".join(tool_names)
    assert set(hooks["hooks"]) == {
        "SessionStart",
        "PreToolUse",
        "PermissionRequest",
        "PostToolUse",
        "Stop",
    }


def test_mcp_get_projection_is_read_only(tmp_path: Path) -> None:
    repository = _initialized_repository(tmp_path)
    before = {
        path.relative_to(repository).as_posix(): path.read_bytes()
        for path in repository.rglob("*")
        if path.is_file()
    }
    result = call_tool("get_projection", {"repository": str(repository)})
    after = {
        path.relative_to(repository).as_posix(): path.read_bytes()
        for path in repository.rglob("*")
        if path.is_file()
    }
    assert result["isError"] is False
    assert before == after


def test_console_module_exposes_help_and_plan_without_writes(tmp_path: Path) -> None:
    help_result = subprocess.run(
        [sys.executable, "-m", "harness_core.cli", "--help"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert help_result.returncode == 0
    assert "sdd-harness" in help_result.stdout

    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "fixture"
version = "0.1.0"
dependencies = ["pytest>=8"]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, "-m", "harness_core.cli", "init", str(tmp_path), "--json"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 2
    assert json.loads(result.stdout)["status"] == "confirmation-required"
    assert not (tmp_path / ".harness").exists()
