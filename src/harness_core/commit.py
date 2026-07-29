"""Digest-bound selective commits using an isolated temporary Git index."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Iterable

from .artifacts import SCHEMA_VERSION, attach_digest, digest_matches
from .branching import branch_action_blockers
from .codex_adapter import runtime_state
from .decisions import task_decision_blockers
from .policy import load_project_config
from .workspace import run_git, temporary_git_environment, workspace_state


def _normalize_scope(repository: Path, paths: Iterable[str]) -> list[str]:
    root = repository.resolve()
    normalized: list[str] = []
    for raw in paths:
        value = str(raw).replace("\\", "/").strip("/")
        target = (root / value).resolve()
        if not value or not target.is_relative_to(root):
            raise ValueError("GOVERNANCE_SCOPE_UNRESOLVED")
        normalized.append(target.relative_to(root).as_posix())
    return sorted(set(normalized))


def _projection_id(repository: Path) -> str | None:
    path = repository / ".harness" / "governance" / "projection.lock.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    result = value.get("projection_id") if isinstance(value, dict) else None
    return result if isinstance(result, str) else None


def build_commit_plan(
    repository: Path,
    *,
    commit_scope: Iterable[str],
    message: str,
    workspace_impact_scope: Iterable[str] | None = None,
) -> dict[str, Any]:
    root = repository.resolve()
    state = workspace_state(root)
    scope = _normalize_scope(root, commit_scope)
    impact_scope = _normalize_scope(
        root,
        (
            workspace_impact_scope
            if workspace_impact_scope is not None
            else scope
        ),
    )
    blockers: set[str] = set()
    if not scope or not set(scope).issubset(state["changed_paths"]):
        blockers.add("GOVERNANCE_SCOPE_UNRESOLVED")
    partial = sorted(set(scope) & set(state["partial_paths"]))
    if partial:
        blockers.add("PARTIAL_STAGING_UNSUPPORTED")
    config = load_project_config(root)
    if config:
        blockers.update(
            branch_action_blockers(
                state["head_ref"], "commit", config["branch_policy"]
            )
        )
    document = {
        "artifact_type": "commit-plan",
        "schema_version": SCHEMA_VERSION,
        "base_commit": state["base_commit"],
        "workspace_digest": state["workspace_digest"],
        "workspace_impact_scope": impact_scope,
        "commit_scope": scope,
        "message": message.strip(),
        "partial_paths": partial,
        "blocker_codes": sorted(blockers),
    }
    if not document["message"]:
        document["blocker_codes"] = sorted(
            set(document["blocker_codes"]) | {"GOVERNANCE_SCOPE_UNRESOLVED"}
        )
    return attach_digest(document, "plan_digest")


def _index_entries(repository: Path, paths: list[str]) -> bytes:
    if not paths:
        return b""
    return run_git(repository, ["ls-files", "-s", "-z", "--", *paths]).stdout


def apply_commit_plan(
    repository: Path,
    plan: dict[str, Any],
    *,
    decision: dict[str, Any] | None,
) -> dict[str, Any]:
    root = repository.resolve()
    if not digest_matches(plan, "plan_digest"):
        return {"status": "blocked", "blocker_codes": ["COMMIT_PLAN_STALE"]}
    if plan.get("blocker_codes"):
        return {"status": "blocked", "blocker_codes": plan["blocker_codes"]}
    state = workspace_state(root)
    if (
        state["workspace_digest"] != plan.get("workspace_digest")
        or state["base_commit"] != plan.get("base_commit")
    ):
        return {"status": "blocked", "blocker_codes": ["COMMIT_PLAN_STALE"]}
    runtime = runtime_state(root)
    if runtime["status"] != "active":
        return {
            "status": "blocked",
            "blocker_codes": runtime["blocker_codes"],
        }

    projection_id = runtime["projection_id"] or _projection_id(root)
    if projection_id is None:
        return {
            "status": "blocked",
            "blocker_codes": ["GOVERNANCE_SOURCE_MISSING", "HANDOFF_REQUIRED"],
        }
    target = {
        "plan_digest": plan["plan_digest"],
        "commit_scope": plan["commit_scope"],
        "message": plan["message"],
    }
    decision_blockers = task_decision_blockers(
        decision,
        task_id=str((decision or {}).get("task_id") or ""),
        projection_id=projection_id,
        workspace_digest=state["workspace_digest"],
        exact_action="delivery:commit",
        target=target,
    )
    if decision_blockers:
        return {"status": "blocked", "blocker_codes": decision_blockers}

    excluded_staged = sorted(
        set(state["staged"]) - set(plan["commit_scope"])
    )
    excluded_entries = _index_entries(root, excluded_staged)
    old_head = state["base_commit"]
    with tempfile.TemporaryDirectory(prefix="sdd-harness-commit-") as raw:
        index_path = Path(raw) / "index"
        environment = temporary_git_environment(index_path)
        if old_head == "unborn":
            read_tree = run_git(
                root, ["read-tree", "--empty"], env=environment, check=False
            )
        else:
            read_tree = run_git(
                root, ["read-tree", old_head], env=environment, check=False
            )
        if read_tree.returncode != 0:
            return {
                "status": "blocked",
                "blocker_codes": ["GOVERNANCE_PRECONDITION_FAILED"],
            }
        add = run_git(
            root,
            ["add", "--all", "--", *plan["commit_scope"]],
            env=environment,
            check=False,
        )
        if add.returncode != 0:
            return {
                "status": "blocked",
                "blocker_codes": ["GOVERNANCE_SCOPE_UNRESOLVED"],
            }
        changed = run_git(
            root,
            ["diff", "--cached", "--quiet", "--exit-code"],
            env=environment,
            check=False,
        )
        if changed.returncode == 0:
            return {
                "status": "blocked",
                "blocker_codes": ["GOVERNANCE_SCOPE_UNRESOLVED"],
            }
        committed = run_git(
            root,
            ["commit", "-m", plan["message"]],
            env=environment,
            check=False,
        )
        if committed.returncode != 0:
            return {
                "status": "failed",
                "blocker_codes": ["GOVERNANCE_EVIDENCE_INCOMPLETE"],
                "stderr": committed.stderr.decode("utf-8", errors="replace"),
            }
        new_head = run_git(root, ["rev-parse", "HEAD"]).stdout.decode().strip()
        synchronized = run_git(
            root,
            ["reset", "-q", "HEAD", "--", *plan["commit_scope"]],
            check=False,
        )
        if synchronized.returncode != 0:
            if old_head == "unborn":
                run_git(
                    root,
                    ["update-ref", "-d", "HEAD", new_head],
                    check=False,
                )
            else:
                run_git(
                    root,
                    ["update-ref", "HEAD", old_head, new_head],
                    check=False,
                )
            return {
                "status": "blocked",
                "blocker_codes": [
                    "GOVERNANCE_DRIFT_DETECTED",
                    "HANDOFF_REQUIRED",
                ],
            }

    if _index_entries(root, excluded_staged) != excluded_entries:
        return {
            "status": "blocked",
            "blocker_codes": [
                "GOVERNANCE_DRIFT_DETECTED",
                "HANDOFF_REQUIRED",
            ],
        }
    return {
        "status": "committed",
        "commit_sha": new_head,
        "committed_paths": plan["commit_scope"],
        "preserved_staged_paths": excluded_staged,
        "blocker_codes": [],
    }
