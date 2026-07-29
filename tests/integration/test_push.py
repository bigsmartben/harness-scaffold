from __future__ import annotations

from pathlib import Path

from harness_core.codex_adapter import runtime_state
from harness_core.contracts import validate_runtime_artifact
from harness_core.decisions import create_task_decision
from harness_core.push import apply_push_plan, build_push_plan
from harness_core.workspace import workspace_state

from conftest import git, initialize


def _ready(repository: Path) -> None:
    initialize(repository)
    git(repository, "add", ".")
    git(repository, "commit", "-m", "initialize harness")


def test_exact_push_uses_non_force_refspec_and_verifies_remote(
    private_repository: Path,
) -> None:
    _ready(private_repository)
    remote = private_repository.with_name(
        f"{private_repository.name}-remote.git"
    )
    git(private_repository.parent, "init", "--bare", str(remote))
    git(private_repository, "remote", "add", "delivery", str(remote))

    branch = "codex/test"
    plan = build_push_plan(
        private_repository,
        remote="delivery",
        branch=branch,
    )
    assert plan["blocker_codes"] == []
    assert validate_runtime_artifact(plan) == []
    runtime = runtime_state(private_repository)
    workspace = workspace_state(private_repository)
    target = {
        key: plan[key]
        for key in (
            "plan_digest",
            "remote",
            "remote_url_digest",
            "branch",
            "commit_sha",
        )
    }
    decision = create_task_decision(
        task_id="push-exact",
        projection_id=runtime["projection_id"],
        workspace_digest=workspace["workspace_digest"],
        exact_action="delivery:push",
        target=target,
    )
    result = apply_push_plan(
        private_repository, plan, decision=decision
    )
    assert result["status"] == "pushed"
    assert result["commit_sha"] == git(private_repository, "rev-parse", "HEAD")
    assert git(
        private_repository,
        "ls-remote",
        "--heads",
        "delivery",
        "refs/heads/codex/test",
    ).startswith(result["commit_sha"])


def test_push_plan_blocks_controlled_branch(
    private_repository: Path,
) -> None:
    _ready(private_repository)
    remote = private_repository.with_name(
        f"{private_repository.name}-remote.git"
    )
    git(private_repository.parent, "init", "--bare", str(remote))
    git(private_repository, "remote", "add", "delivery", str(remote))
    git(private_repository, "checkout", "-b", "main")
    plan = build_push_plan(
        private_repository,
        remote="delivery",
        branch="main",
    )
    assert plan["blocker_codes"] == [
        "CONTROLLED_BRANCH_GATE_REQUIRED",
        "HANDOFF_REQUIRED",
    ]
