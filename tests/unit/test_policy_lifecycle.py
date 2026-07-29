from __future__ import annotations

import os
from pathlib import Path

import pytest

from harness_core.codex_adapter import runtime_state
from harness_core.cli import build_parser
from harness_core.contracts import validate_runtime_artifact
from harness_core.decisions import (
    DecisionStateError,
    create_task_decision,
    end_task_decision,
    load_task_decision,
    save_task_decision,
    task_decision_blockers,
)
from harness_core.policy import (
    apply_project_policy_plan,
    build_project_policy_plan,
)
from harness_core.workspace import workspace_state

from conftest import git, initialize


def test_policy_decision_and_delivery_cli_surfaces_are_explicit() -> None:
    parser = build_parser()
    policy = parser.parse_args(
        ["policy-plan", ".", "--changes-json", '{"hooks":"optional"}']
    )
    assert policy.command == "policy-plan"
    assert policy.changes_json == '{"hooks":"optional"}'

    ended = parser.parse_args(["decision-end", ".", "--task-id", "task-22"])
    assert ended.command == "decision-end"
    assert ended.task_id == "task-22"

    gate = parser.parse_args(
        [
            "gate-evidence",
            "--action",
            "delivery:pull-request",
            "--target-file",
            "target.json",
            "--checks-file",
            "checks.json",
        ]
    )
    assert gate.command == "gate-evidence"
    assert gate.action == "delivery:pull-request"


def test_blocked_policy_plan_still_has_a_valid_machine_contract(
    private_repository: Path,
) -> None:
    initialize(private_repository)
    plan = build_project_policy_plan(private_repository, changes={})
    assert plan["blocker_codes"] == ["CONFIG_INVALID"]
    assert validate_runtime_artifact(plan) == []


def test_policy_plan_is_zero_write_and_atomically_refreshes_projection(
    private_repository: Path,
) -> None:
    initialize(private_repository)
    before = runtime_state(private_repository)
    config = private_repository / ".harness/harness.yaml"
    original = config.read_bytes()

    plan = build_project_policy_plan(
        private_repository,
        changes={"declarations": {"validation_profile": "strict-contracts"}},
    )

    assert config.read_bytes() == original
    assert plan["blocker_codes"] == []
    assert plan["previous_projection_id"] == before["projection_id"]
    assert plan["projection_id"] != before["projection_id"]
    assert validate_runtime_artifact(plan) == []

    workspace = workspace_state(private_repository)
    decision = create_task_decision(
        task_id="old-policy-decision",
        projection_id=before["projection_id"],
        workspace_digest=workspace["workspace_digest"],
        exact_action="delivery:push",
        target={"remote": "origin"},
    )
    save_task_decision(private_repository, decision)

    result = apply_project_policy_plan(
        private_repository,
        plan,
        approved_plan_digest=plan["plan_digest"],
    )

    assert result["status"] == "applied"
    assert result["projection_id"] == plan["projection_id"]
    assert result["projection_id"] != result["previous_projection_id"]
    assert runtime_state(private_repository)["projection_id"] == result[
        "projection_id"
    ]
    assert task_decision_blockers(
        decision,
        task_id=decision["task_id"],
        projection_id=result["projection_id"],
        workspace_digest=workspace_state(private_repository)["workspace_digest"],
        exact_action="delivery:push",
        target={"remote": "origin"},
    ) == ["TASK_DECISION_STALE", "HANDOFF_REQUIRED"]


def test_policy_plan_rejects_wrong_approval_and_changed_workspace(
    private_repository: Path,
) -> None:
    initialize(private_repository)
    plan = build_project_policy_plan(
        private_repository,
        changes={"declarations": {"channel": "stable"}},
    )
    config = private_repository / ".harness/harness.yaml"
    original = config.read_bytes()

    wrong = apply_project_policy_plan(
        private_repository,
        plan,
        approved_plan_digest="sha256:" + "0" * 64,
    )
    assert wrong["blocker_codes"] == [
        "PROJECT_POLICY_PLAN_STALE",
        "HANDOFF_REQUIRED",
    ]
    assert config.read_bytes() == original

    (private_repository / "new.txt").write_text("changed\n", encoding="utf-8")
    stale = apply_project_policy_plan(
        private_repository,
        plan,
        approved_plan_digest=plan["plan_digest"],
    )
    assert stale["blocker_codes"] == [
        "PROJECT_POLICY_PLAN_STALE",
        "HANDOFF_REQUIRED",
    ]
    assert config.read_bytes() == original


def test_policy_publication_rolls_back_every_touched_file_on_failure(
    private_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialize(private_repository)
    before_projection = runtime_state(private_repository)["projection_id"]
    plan = build_project_policy_plan(
        private_repository,
        changes={"declarations": {"channel": "rollback-test"}},
    )
    protected = {
        path.relative_to(private_repository).as_posix(): path.read_bytes()
        for path in (
            private_repository / ".harness/governance"
        ).glob("*.json")
    }
    protected[".harness/harness.yaml"] = (
        private_repository / ".harness/harness.yaml"
    ).read_bytes()

    real_replace = os.replace
    calls = 0

    def fail_second_replace(source: str | Path, target: str | Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated publication failure")
        real_replace(source, target)

    monkeypatch.setattr("harness_core.initializer.os.replace", fail_second_replace)
    result = apply_project_policy_plan(
        private_repository,
        plan,
        approved_plan_digest=plan["plan_digest"],
    )

    assert result["status"] == "blocked"
    assert result["blocker_codes"] == [
        "GOVERNANCE_SCOPE_UNRESOLVED",
        "HANDOFF_REQUIRED",
    ]
    for relative, expected in protected.items():
        assert (private_repository / relative).read_bytes() == expected
    assert runtime_state(private_repository)["projection_id"] == before_projection


def test_decision_end_expires_only_ignored_runtime_state(
    private_repository: Path,
) -> None:
    initialize(private_repository)
    state = runtime_state(private_repository)
    workspace = workspace_state(private_repository)
    decision = create_task_decision(
        task_id="finish-once",
        projection_id=state["projection_id"],
        workspace_digest=workspace["workspace_digest"],
        exact_action="delivery:push",
        target={"remote": "origin"},
    )
    path = save_task_decision(private_repository, decision)
    assert git(
        private_repository,
        "check-ignore",
        path.relative_to(private_repository).as_posix(),
    )

    ended = end_task_decision(private_repository, decision["task_id"])

    assert ended["status"] == "expired"
    assert load_task_decision(private_repository, decision["task_id"]) is None
    assert not path.exists()


@pytest.mark.parametrize("repository_visible_as", ["unignored", "tracked"])
def test_decision_end_preserves_repository_visible_state(
    private_repository: Path,
    repository_visible_as: str,
) -> None:
    initialize(private_repository)
    state = runtime_state(private_repository)
    workspace = workspace_state(private_repository)
    decision = create_task_decision(
        task_id=f"visible-{repository_visible_as}",
        projection_id=state["projection_id"],
        workspace_digest=workspace["workspace_digest"],
        exact_action="delivery:push",
        target={"remote": "origin"},
    )
    path = save_task_decision(private_repository, decision)
    relative = path.relative_to(private_repository).as_posix()

    if repository_visible_as == "unignored":
        ignore_path = private_repository / ".harness/.gitignore"
        ignore_path.write_text(
            ignore_path.read_text(encoding="utf-8").replace("runtime/\n", ""),
            encoding="utf-8",
            newline="\n",
        )
    else:
        git(private_repository, "add", "-f", relative)

    ended = end_task_decision(private_repository, decision["task_id"])

    assert ended["status"] == "blocked"
    assert ended["blocker_codes"] == [
        "GOVERNANCE_PRECONDITION_FAILED",
        "HANDOFF_REQUIRED",
    ]
    assert path.exists()
    assert load_task_decision(private_repository, decision["task_id"]) == decision


def test_decision_refuses_runtime_state_that_git_does_not_ignore(
    tmp_path: Path,
) -> None:
    git(tmp_path, "init")
    decision = create_task_decision(
        task_id="unsafe",
        projection_id="sha256:" + "1" * 64,
        workspace_digest="sha256:" + "2" * 64,
        exact_action="delivery:push",
        target={"remote": "origin"},
    )

    with pytest.raises(DecisionStateError) as raised:
        save_task_decision(tmp_path, decision)

    assert raised.value.blocker_codes == [
        "GOVERNANCE_PRECONDITION_FAILED",
        "HANDOFF_REQUIRED",
    ]
    assert not (tmp_path / ".harness/runtime").exists()
