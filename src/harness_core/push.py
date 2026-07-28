"""Digest-bound, non-force Git branch delivery."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifacts import (
    SCHEMA_VERSION,
    attach_digest,
    content_digest,
    digest_matches,
)
from .branching import branch_action_blockers
from .codex_adapter import runtime_state
from .decisions import task_decision_blockers
from .policy import load_project_config
from .workspace import run_git, workspace_state


def _remote_url(repository: Path, remote: str) -> str | None:
    result = run_git(
        repository, ["remote", "get-url", remote], check=False
    )
    if result.returncode != 0:
        return None
    return result.stdout.decode("utf-8", errors="replace").strip() or None


def _branch_valid(repository: Path, branch: str) -> bool:
    result = run_git(
        repository, ["check-ref-format", "--branch", branch], check=False
    )
    return result.returncode == 0


def build_push_plan(
    repository: Path,
    *,
    remote: str,
    branch: str,
    commit_sha: str | None = None,
) -> dict[str, Any]:
    root = repository.resolve()
    state = workspace_state(root)
    exact_commit = commit_sha or state["base_commit"]
    remote_url = _remote_url(root, remote)
    blockers: set[str] = set()
    if (
        not remote
        or not _branch_valid(root, branch)
        or state["head_ref"] != f"refs/heads/{branch}"
        or exact_commit != state["base_commit"]
        or exact_commit == "unborn"
    ):
        blockers.add("GOVERNANCE_SCOPE_UNRESOLVED")
    if remote_url is None:
        blockers.add("TOOL_BINDING_AMBIGUOUS")
    config = load_project_config(root)
    if config:
        blockers.update(
            branch_action_blockers(
                state["head_ref"], "push", config["branch_policy"]
            )
        )
    document = {
        "artifact_type": "push-plan",
        "schema_version": SCHEMA_VERSION,
        "workspace_digest": state["workspace_digest"],
        "remote": remote,
        "remote_url_digest": (
            content_digest(remote_url) if remote_url is not None else None
        ),
        "branch": branch,
        "commit_sha": exact_commit,
        "blocker_codes": sorted(blockers),
    }
    return attach_digest(document, "plan_digest")


def apply_push_plan(
    repository: Path,
    plan: dict[str, Any],
    *,
    decision: dict[str, Any] | None,
) -> dict[str, Any]:
    root = repository.resolve()
    if not digest_matches(plan, "plan_digest"):
        return {"status": "blocked", "blocker_codes": ["PUSH_PLAN_STALE"]}
    if plan.get("blocker_codes"):
        return {"status": "blocked", "blocker_codes": plan["blocker_codes"]}
    state = workspace_state(root)
    if (
        state["workspace_digest"] != plan.get("workspace_digest")
        or state["base_commit"] != plan.get("commit_sha")
        or state["head_ref"] != f"refs/heads/{plan.get('branch')}"
    ):
        return {"status": "blocked", "blocker_codes": ["PUSH_PLAN_STALE"]}
    runtime = runtime_state(root)
    if runtime["status"] != "active":
        return {
            "status": "blocked",
            "blocker_codes": runtime["blocker_codes"],
        }
    remote_url = _remote_url(root, str(plan.get("remote") or ""))
    if (
        remote_url is None
        or content_digest(remote_url) != plan.get("remote_url_digest")
    ):
        return {
            "status": "blocked",
            "blocker_codes": ["PUSH_PLAN_STALE"],
        }
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
    decision_blockers = task_decision_blockers(
        decision,
        task_id=str((decision or {}).get("task_id") or ""),
        projection_id=str(runtime["projection_id"]),
        workspace_digest=state["workspace_digest"],
        exact_action="delivery:push",
        target=target,
    )
    if decision_blockers:
        return {"status": "blocked", "blocker_codes": decision_blockers}

    ref = f"refs/heads/{plan['branch']}"
    pushed = run_git(
        root,
        [
            "push",
            "--porcelain",
            plan["remote"],
            f"{plan['commit_sha']}:{ref}",
        ],
        check=False,
    )
    if pushed.returncode != 0:
        return {
            "status": "failed",
            "blocker_codes": ["REMOTE_PUSH_FAILED", "HANDOFF_REQUIRED"],
            "stderr": pushed.stderr.decode("utf-8", errors="replace"),
        }
    evidence = run_git(
        root,
        ["ls-remote", "--heads", plan["remote"], ref],
        check=False,
    )
    remote_sha = (
        evidence.stdout.decode("utf-8", errors="replace").split(maxsplit=1)[0]
        if evidence.returncode == 0 and evidence.stdout.strip()
        else None
    )
    if remote_sha != plan["commit_sha"]:
        return {
            "status": "failed",
            "blocker_codes": [
                "GOVERNANCE_EVIDENCE_INCOMPLETE",
                "HANDOFF_REQUIRED",
            ],
        }
    result = {
        "status": "pushed",
        "remote": plan["remote"],
        "branch": plan["branch"],
        "commit_sha": remote_sha,
        "remote_ref": ref,
        "blocker_codes": [],
    }
    return attach_digest(result, "evidence_digest")
