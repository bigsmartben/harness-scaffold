from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness_core.cli import build_parser
from harness_core.codex_adapter import runtime_state
from harness_core.decisions import (
    create_task_decision,
    task_decision_blockers,
)
from harness_core.issues import (
    apply_local_issue_plan,
    build_issue_plan,
    prepare_remote_issue_request,
    validate_remote_issue_receipt,
)
from harness_core.selection import select_validation
from harness_core.runner import run_local_task_ref
from harness_core.workspace import workspace_state

from conftest import git, initialize


ROOT = Path(__file__).parents[2]


def test_t0_t3_selector_uses_minimum_sufficient_validation() -> None:
    assert select_validation(["docs/readme.md"])["validation_level"] == "T0"
    assert select_validation(["src/widget.py"])["validation_level"] == "T1"
    assert select_validation(
        ["src/a.py", "tests/test_a.py"]
    )["validation_level"] == "T2"
    assert select_validation(
        ["schemas/public.schema.json"]
    )["validation_level"] == "T2"
    assert select_validation(
        ["src/harness_core/projection.py"]
    )["validation_level"] == "T3"
    assert select_validation(
        [".github/workflows/ci.yml"]
    )["validation_level"] == "T3"


def test_task_ref_scope_and_cli_order_are_exact() -> None:
    arguments = build_parser().parse_args(
        ["run-task", ".", "test:contracts", "--scope", "contract"]
    )
    assert arguments.task_ref == "test:contracts"
    assert arguments.scope == "contract"
    with pytest.raises(ValueError, match="GOVERNANCE_SCOPE_UNRESOLVED"):
        run_local_task_ref(ROOT, "test:contracts", scope="full")


def test_task_decision_is_exact_and_stales_on_workspace_change(
    private_repository: Path,
) -> None:
    initialize(private_repository)
    state = runtime_state(private_repository)
    workspace = workspace_state(private_repository)
    target = {"provider": "github", "repository": "owner/repo"}
    decision = create_task_decision(
        task_id="issue-22",
        projection_id=state["projection_id"],
        workspace_digest=workspace["workspace_digest"],
        exact_action="delivery:remote-issue",
        target=target,
    )
    assert task_decision_blockers(
        decision,
        task_id="issue-22",
        projection_id=state["projection_id"],
        workspace_digest=workspace["workspace_digest"],
        exact_action="delivery:remote-issue",
        target=target,
    ) == []
    (private_repository / "change.txt").write_text("changed", encoding="utf-8")
    assert task_decision_blockers(
        decision,
        task_id="issue-22",
        projection_id=state["projection_id"],
        workspace_digest=workspace_state(private_repository)["workspace_digest"],
        exact_action="delivery:remote-issue",
        target=target,
    ) == ["TASK_DECISION_STALE", "HANDOFF_REQUIRED"]


def test_local_and_remote_issue_adapters_do_not_fallback(
    private_repository: Path,
) -> None:
    initialize(private_repository)
    local = build_issue_plan(
        private_repository, title="Local task", body="Implement it."
    )
    created = apply_local_issue_plan(private_repository, local)
    assert created["status"] == "created"
    assert (private_repository / created["path"]).is_file()

    remote = build_issue_plan(
        private_repository,
        title="Remote task",
        body="Implement remotely.",
        provider="github",
        remote_repository="owner/repo",
        labels=["kind/feature"],
    )
    state = runtime_state(private_repository)
    workspace = workspace_state(private_repository)
    target = {
        key: remote[key]
        for key in (
            "provider",
            "repository",
            "title",
            "body",
            "labels",
            "assignee",
            "target_digest",
        )
    }
    decision = create_task_decision(
        task_id="remote-issue",
        projection_id=state["projection_id"],
        workspace_digest=workspace["workspace_digest"],
        exact_action="delivery:remote-issue",
        target=target,
    )
    request = prepare_remote_issue_request(
        private_repository,
        remote,
        decision=decision,
        projection_id=state["projection_id"],
    )
    assert request["status"] == "provider-required"
    assert request["request"] == target
    assert not list((private_repository / ".harness/issues").glob("*Remote*"))
    assert validate_remote_issue_receipt(
        remote,
        {"provider": "github", "repository": "owner/repo"},
    ) == ["REMOTE_ISSUE_WRITE_FAILED", "HANDOFF_REQUIRED"]
    valid_receipt = {
        "status": "succeeded",
        "provider": "github",
        "repository": "owner/repo",
        "target_digest": remote["target_digest"],
        "url": "https://github.com/owner/repo/issues/23",
        "issue_number": 23,
    }
    assert validate_remote_issue_receipt(remote, valid_receipt) == []

    failed_receipt = {**valid_receipt, "status": "failed"}
    assert validate_remote_issue_receipt(remote, failed_receipt) == [
        "REMOTE_ISSUE_WRITE_FAILED",
        "HANDOFF_REQUIRED",
    ]

    wrong_target_receipt = {
        **valid_receipt,
        "target_digest": "sha256:" + "0" * 64,
    }
    assert validate_remote_issue_receipt(remote, wrong_target_receipt) == [
        "REMOTE_ISSUE_WRITE_FAILED",
        "HANDOFF_REQUIRED",
    ]


def test_local_issue_write_rejects_a_stale_projection(
    private_repository: Path,
) -> None:
    initialize(private_repository)
    plan = build_issue_plan(
        private_repository, title="Stale task", body="Do not write."
    )
    config = private_repository / ".harness/harness.yaml"
    config.write_text(
        config.read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )
    result = apply_local_issue_plan(private_repository, plan)
    assert result["status"] == "blocked"
    assert result["blocker_codes"] == ["GOVERNANCE_PROJECTION_STALE"]
    assert not (private_repository / plan["local_path"]).exists()


def test_remote_issue_is_blocked_on_controlled_branch(
    private_repository: Path,
) -> None:
    initialize(private_repository)
    git(private_repository, "add", ".")
    git(private_repository, "commit", "-m", "initialize harness")
    git(private_repository, "checkout", "-b", "main")
    remote = build_issue_plan(
        private_repository,
        title="Remote task",
        body="Body.",
        provider="github",
        remote_repository="owner/repo",
    )
    result = prepare_remote_issue_request(
        private_repository,
        remote,
        decision=None,
        projection_id=runtime_state(private_repository)["projection_id"],
    )
    assert result["blocker_codes"] == [
        "CONTROLLED_BRANCH_GATE_REQUIRED",
        "HANDOFF_REQUIRED",
    ]
