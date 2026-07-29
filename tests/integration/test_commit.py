from __future__ import annotations

from pathlib import Path

from harness_core.codex_adapter import runtime_state
from harness_core.commit import apply_commit_plan, build_commit_plan
from harness_core.decisions import create_task_decision
from harness_core.workspace import workspace_state

from conftest import git, initialize


def _ready_repository(repository: Path) -> None:
    initialize(repository)
    (repository / "a.txt").write_text("a0\n", encoding="utf-8")
    (repository / "b.txt").write_text("b0\n", encoding="utf-8")
    git(repository, "add", ".")
    git(repository, "commit", "-m", "initialize harness")


def test_selective_commit_preserves_unrelated_staging(
    private_repository: Path,
) -> None:
    _ready_repository(private_repository)
    (private_repository / "a.txt").write_text("a1\n", encoding="utf-8")
    (private_repository / "b.txt").write_text("b1\n", encoding="utf-8")
    git(private_repository, "add", "b.txt")
    plan = build_commit_plan(
        private_repository,
        commit_scope=["a.txt"],
        workspace_impact_scope=["a.txt", "b.txt"],
        message="update a only",
    )
    assert plan["blocker_codes"] == []
    state = runtime_state(private_repository)
    workspace = workspace_state(private_repository)
    target = {
        "plan_digest": plan["plan_digest"],
        "commit_scope": plan["commit_scope"],
        "message": plan["message"],
    }
    decision = create_task_decision(
        task_id="commit-a",
        projection_id=state["projection_id"],
        workspace_digest=workspace["workspace_digest"],
        exact_action="delivery:commit",
        target=target,
    )
    result = apply_commit_plan(
        private_repository, plan, decision=decision
    )
    assert result["status"] == "committed"
    assert git(
        private_repository,
        "show",
        "--pretty=format:",
        "--name-only",
        "HEAD",
    ).splitlines() == ["a.txt"]
    assert git(
        private_repository, "diff", "--cached", "--name-only"
    ).splitlines() == ["b.txt"]


def test_partial_staging_and_controlled_branch_fail_closed(
    private_repository: Path,
) -> None:
    _ready_repository(private_repository)
    (private_repository / "a.txt").write_text("staged\n", encoding="utf-8")
    git(private_repository, "add", "a.txt")
    (private_repository / "a.txt").write_text("unstaged\n", encoding="utf-8")
    partial = build_commit_plan(
        private_repository,
        commit_scope=["a.txt"],
        message="unsafe partial file",
    )
    assert "PARTIAL_STAGING_UNSUPPORTED" in partial["blocker_codes"]

    git(private_repository, "reset", "--hard", "HEAD")
    git(private_repository, "checkout", "-b", "main")
    (private_repository / "a.txt").write_text("controlled\n", encoding="utf-8")
    controlled = build_commit_plan(
        private_repository,
        commit_scope=["a.txt"],
        message="direct main commit",
    )
    assert controlled["blocker_codes"] == [
        "CONTROLLED_BRANCH_GATE_REQUIRED",
        "HANDOFF_REQUIRED",
    ]


def test_commit_adapter_rejects_a_plan_created_while_projection_is_stale(
    private_repository: Path,
) -> None:
    _ready_repository(private_repository)
    config = private_repository / ".harness/harness.yaml"
    config.write_text(
        config.read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )
    (private_repository / "a.txt").write_text("a2\n", encoding="utf-8")
    plan = build_commit_plan(
        private_repository,
        commit_scope=["a.txt"],
        message="must not commit",
    )
    runtime = runtime_state(private_repository)
    workspace = workspace_state(private_repository)
    decision = create_task_decision(
        task_id="stale-commit",
        projection_id=runtime["projection_id"],
        workspace_digest=workspace["workspace_digest"],
        exact_action="delivery:commit",
        target={
            "plan_digest": plan["plan_digest"],
            "commit_scope": plan["commit_scope"],
            "message": plan["message"],
        },
    )
    result = apply_commit_plan(
        private_repository, plan, decision=decision
    )
    assert result["status"] == "blocked"
    assert result["blocker_codes"] == ["GOVERNANCE_PROJECTION_STALE"]
