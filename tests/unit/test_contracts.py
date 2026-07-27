from __future__ import annotations

import shutil
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from harness_core.contracts import blocker_codes, validate_config


ROOT = Path(__file__).parents[2]
SKILL = ROOT / "skills" / "initialize-ai-coding-harness"
SCHEMAS = SKILL / "assets" / "schemas"
FIXTURES = ROOT / "tests" / "fixtures"

EXPECTED_BLOCKER_CODES = {
    "WRITE_SCOPE_EXPANDED",
    "TOOL_NOT_REGISTERED",
    "TOOL_ENTRY_STALE",
    "IMPACT_UNRESOLVED",
    "TASK_BYPASS_ATTEMPT",
    "ACTION_CLASSIFICATION_UNRESOLVED",
    "HANDOFF_REQUIRED",
    "CONTROLLED_BRANCH_GATE_REQUIRED",
    "PUBLISH_CONFIRMATION_REQUIRED",
    "PROTECTED_TRIGGER_UNCONTROLLED",
    "CONFIG_INVALID",
    "BACKEND_UNAVAILABLE",
    "EVIDENCE_INCOMPLETE",
    "PLAN_STALE",
    "GRANT_STALE",
    "EVIDENCE_BINDING_MISMATCH",
    "GOVERNANCE_SOURCE_MISSING",
    "GOVERNANCE_CONFLICT",
    "GOVERNANCE_SCOPE_UNRESOLVED",
    "GOVERNANCE_INHERITANCE_INVALID",
    "GOVERNANCE_PROJECTION_STALE",
    "GOVERNANCE_COVERAGE_INCOMPLETE",
    "TOOL_ACTION_UNCLASSIFIED",
    "TOOL_BINDING_AMBIGUOUS",
    "GOVERNANCE_PRECONDITION_FAILED",
    "INVOCATION_BYPASS_ATTEMPT",
    "GOVERNANCE_NOT_ENFORCEABLE",
    "GOVERNANCE_EVIDENCE_INCOMPLETE",
    "GOVERNANCE_DRIFT_DETECTED",
    "AGENT_BINDING_UNAVAILABLE",
    "AGENT_ROLE_CONTRACT_INVALID",
    "AGENT_CONFIGURATION_UNTRUSTED",
}


def _configured_fixture(tmp_path: Path, overlay: str | None = None) -> Path:
    target = tmp_path / ".harness"
    shutil.copytree(FIXTURES / "valid" / ".harness", target)
    if overlay is not None:
        shutil.copytree(
            FIXTURES / overlay / ".harness", target, dirs_exist_ok=True
        )
    return target


def test_valid_fixture_passes_schema_and_cross_file_validation(tmp_path: Path) -> None:
    config = _configured_fixture(tmp_path)

    assert validate_config(config, SCHEMAS) == []


def test_all_committed_schemas_are_valid_draft_2020_12() -> None:
    for schema_path in SCHEMAS.glob("*.schema.json"):
        schema = yaml.safe_load(schema_path.read_text("utf-8"))
        Draft202012Validator.check_schema(schema)
        expected = "1.0.0" if schema_path.name == "governance.schema.json" else "0.3.0"
        assert schema["x-harness-schema-version"] == expected


def test_repository_self_configuration_uses_same_contracts() -> None:
    assert validate_config(ROOT / ".harness", SCHEMAS) == []


def test_missing_required_field_has_stable_failure(tmp_path: Path) -> None:
    config = _configured_fixture(tmp_path, "invalid-missing-field")

    issues = validate_config(config, SCHEMAS)

    assert any(
        issue.code == "SCHEMA_INVALID"
        and issue.path == "harness.yaml"
        and "'delivery_authority' is a required property" in issue.message
        for issue in issues
    )


def test_unknown_identity_authorization_field_is_rejected(tmp_path: Path) -> None:
    config = _configured_fixture(tmp_path, "invalid-unknown-field")

    issues = validate_config(config, SCHEMAS)

    assert any(
        issue.code == "SCHEMA_INVALID"
        and issue.path == "tools.yaml#tools/0"
        and "allowed_agents" in issue.message
        for issue in issues
    )


def test_cross_file_task_and_mcp_server_references_are_checked(
    tmp_path: Path,
) -> None:
    config = _configured_fixture(tmp_path, "invalid-references")

    issues = validate_config(config, SCHEMAS)
    issue_pairs = {(issue.code, issue.path) for issue in issues}

    assert ("TASK_REF_UNRESOLVED", "tools.yaml#tools/0/task_ref") in issue_pairs
    assert ("TOOL_REF_UNRESOLVED", "tools.yaml#tools/1/server_ref") in issue_pairs
    assert ("TASK_REF_UNRESOLVED", "impact.yaml#rules/0/tasks") in issue_pairs


def test_managed_tool_requires_task_ref(tmp_path: Path) -> None:
    config = _configured_fixture(tmp_path)
    tools_path = config / "tools.yaml"
    document = yaml.safe_load(tools_path.read_text("utf-8"))
    managed_tool = next(
        tool for tool in document["tools"] if tool["invocation_mode"] == "managed"
    )
    del managed_tool["task_ref"]
    tools_path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")

    issues = validate_config(config, SCHEMAS)

    assert any(
        issue.code == "SCHEMA_INVALID"
        and "'task_ref' is a required property" in issue.message
        for issue in issues
    )


def test_every_tool_requires_action_semantics(tmp_path: Path) -> None:
    config = _configured_fixture(tmp_path)
    tools_path = config / "tools.yaml"
    document = yaml.safe_load(tools_path.read_text("utf-8"))
    del document["tools"][0]["action_semantics"]
    tools_path.write_text(
        yaml.safe_dump(document, sort_keys=False), encoding="utf-8"
    )

    issues = validate_config(config, SCHEMAS)

    assert any(
        issue.code == "SCHEMA_INVALID"
        and "'action_semantics' is a required property" in issue.message
        for issue in issues
    )
    assert {
        "ACTION_CLASSIFICATION_UNRESOLVED",
        "HANDOFF_REQUIRED",
    }.issubset({issue.code for issue in issues})


def test_direct_publish_entry_is_rejected_as_task_bypass(
    tmp_path: Path,
) -> None:
    config = _configured_fixture(tmp_path)
    tools_path = config / "tools.yaml"
    document = yaml.safe_load(tools_path.read_text("utf-8"))
    publish = next(
        tool
        for tool in document["tools"]
        if tool["action_semantics"] == "publish"
    )
    publish["invocation_mode"] = "direct"
    publish["entrypoint"] = "publish-now"
    publish.pop("task_ref")
    tools_path.write_text(
        yaml.safe_dump(document, sort_keys=False), encoding="utf-8"
    )

    issues = validate_config(config, SCHEMAS)

    assert {"TASK_BYPASS_ATTEMPT", "HANDOFF_REQUIRED"}.issubset(
        {issue.code for issue in issues}
    )


def test_action_semantics_must_match_task_category(tmp_path: Path) -> None:
    config = _configured_fixture(tmp_path)
    tools_path = config / "tools.yaml"
    document = yaml.safe_load(tools_path.read_text("utf-8"))
    managed = next(
        tool for tool in document["tools"] if tool["invocation_mode"] == "managed"
    )
    managed["action_semantics"] = "build"
    tools_path.write_text(
        yaml.safe_dump(document, sort_keys=False), encoding="utf-8"
    )

    issues = validate_config(config, SCHEMAS)

    assert any(
        issue.code == "CONFIG_INVALID"
        and "must match the referenced Task category" in issue.message
        for issue in issues
    )


def test_blocker_codes_have_one_complete_machine_source() -> None:
    codes = blocker_codes(SCHEMAS)

    assert len(codes) == len(set(codes))
    assert set(codes) == EXPECTED_BLOCKER_CODES


def test_scaffold_snapshot_excludes_runtime_and_skill_development_files() -> None:
    scaffold = SKILL / "assets" / "scaffold"
    relative_files = {
        path.relative_to(scaffold).as_posix()
        for path in scaffold.rglob("*")
        if path.is_file()
    }

    snapshot = {
        line
        for line in (
            ROOT / "tests" / "snapshots" / "scaffold-files.txt"
        ).read_text("utf-8").splitlines()
        if line
    }

    assert relative_files == snapshot
    assert {
        ".harness/runs",
        ".harness/reports",
        ".harness/cache",
    }.isdisjoint(relative_files)
    assert not any(path.startswith("skills/") for path in relative_files)
    assert not any(
        Path(path).name.lower() in {"readme.md", "quickstart.md", "changelog.md"}
        for path in relative_files
    )


def test_scaffold_gitignore_excludes_runtime_directories() -> None:
    ignored = {
        line.strip()
        for line in (
            SKILL / "assets" / "scaffold" / ".harness" / ".gitignore"
        ).read_text("utf-8").splitlines()
        if line.strip()
    }

    assert ignored == {"runs/", "reports/", "cache/"}


def test_p2_assets_are_the_only_contract_and_template_source() -> None:
    assert not (ROOT / "contracts" / "schemas").exists()
    assert not (ROOT / "templates" / "scaffold").exists()
    assert not (ROOT / "templates" / "backends").exists()


def test_valid_fixture_covers_required_tool_kinds_and_invocation_modes() -> None:
    document = yaml.safe_load(
        (FIXTURES / "valid" / ".harness" / "tools.yaml").read_text("utf-8")
    )
    tool_types = {tool["type"] for tool in document["tools"]}

    assert {"runtime", "cli", "shell", "mcp-server", "mcp-tool"} <= tool_types
    assert {tool["invocation_mode"] for tool in document["tools"]} == {
        "direct",
        "managed",
    }
    assert all(
        "task_ref" in tool
        for tool in document["tools"]
        if tool["invocation_mode"] == "managed"
    )


def test_backend_templates_cover_local_github_actions_and_git_remote() -> None:
    assert (SKILL / "assets" / "backends" / "local" / "adapter.yaml").is_file()
    assert (
        SKILL / "assets" / "backends" / "github-actions" / "adapter.yaml"
    ).is_file()
    git_remote = (
        SKILL / "assets" / "backends" / "git-remote" / "adapter.yaml"
    )
    assert git_remote.is_file()
    git_remote_document = yaml.safe_load(git_remote.read_text("utf-8"))
    assert git_remote_document["type"] == "git-remote"
    assert git_remote_document["execution"] == {
        "shell": False,
        "force": False,
        "operation": "push-ref",
    }
    workflow = (
        SKILL
        / "assets"
        / "backends"
        / "github-actions"
        / ".github"
        / "workflows"
        / "harness.yml"
    )
    assert workflow.is_file()
    assert "workflow_dispatch" in workflow.read_text("utf-8")
    for backend in ("local", "github-actions"):
        for runtime in ("python", "node"):
            adapter = (
                SKILL / "assets" / "backends" / backend / f"{runtime}.yaml"
            )
            assert adapter.is_file()
            document = yaml.safe_load(adapter.read_text("utf-8"))
            assert document["runtime"] == runtime
            assert document["type"] == backend


def test_task_contract_requires_explicit_automation_policy() -> None:
    document = yaml.safe_load(
        (FIXTURES / "valid" / ".harness" / "tasks.yaml").read_text("utf-8")
    )

    for task in document["tasks"]:
        assert task["automation_level"] in {"routine", "expensive", "critical"}
        assert isinstance(task["auto_allowed"], bool)
        if task["automation_level"] in {"expensive", "critical"}:
            assert task["auto_allowed"] is False
        if task["category"] in {
            "push",
            "pull-request",
            "merge",
            "publish",
            "release",
            "deploy",
        }:
            assert task["automation_level"] == "critical"
