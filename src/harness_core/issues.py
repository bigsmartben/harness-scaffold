"""Provider-neutral Issue planning with local and exact remote adapters."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Iterable

from .artifacts import (
    SCHEMA_VERSION,
    attach_digest,
    canonical_digest,
    digest_matches,
)
from .branching import branch_action_blockers
from .codex_adapter import runtime_state
from .decisions import task_decision_blockers
from .policy import load_project_config
from .workspace import workspace_state


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:48] or "issue"


def _safe_local_path(repository: Path, relative: str) -> str:
    root = repository.resolve()
    target = (root / relative.replace("\\", "/")).resolve()
    allowed = (root / ".harness" / "issues").resolve()
    if not target.is_relative_to(allowed):
        raise ValueError("ISSUE_TARGET_REQUIRED")
    return target.relative_to(root).as_posix()


def build_issue_plan(
    repository: Path,
    *,
    title: str,
    body: str,
    provider: str | None = None,
    remote_repository: str | None = None,
    labels: Iterable[str] = (),
    assignee: str | None = None,
    local_path: str | None = None,
) -> dict[str, Any]:
    root = repository.resolve()
    config = load_project_config(root)
    if config is None:
        raise ValueError("CONFIG_INVALID")
    issue_config = config["issue_planning"]
    selected_provider = provider or issue_config["default_provider"]
    if selected_provider not in {"local", "github"}:
        raise ValueError("ISSUE_PROVIDER_UNAVAILABLE")

    resolved_repository: str | None = None
    resolved_local_path: str | None = None
    if selected_provider == "local":
        suffix = canonical_digest({"title": title, "body": body})[7:19]
        proposed = local_path or (
            f"{issue_config['local_directory'].rstrip('/')}/"
            f"{suffix}-{_slug(title)}.md"
        )
        resolved_local_path = _safe_local_path(root, proposed)
    else:
        remote = issue_config.get("remote") or {}
        resolved_repository = (
            remote_repository or remote.get("repository")
        )
        if (
            not isinstance(resolved_repository, str)
            or not re.fullmatch(r"[^/\s]+/[^/\s]+", resolved_repository)
        ):
            raise ValueError("ISSUE_TARGET_REQUIRED")

    target = {
        "provider": selected_provider,
        "repository": resolved_repository,
        "local_path": resolved_local_path,
        "title": title.strip(),
        "body": body.strip(),
        "labels": sorted(set(str(label) for label in labels if str(label))),
        "assignee": assignee,
    }
    if not target["title"] or not target["body"]:
        raise ValueError("ISSUE_TARGET_REQUIRED")
    document = {
        "artifact_type": "issue-plan",
        "schema_version": SCHEMA_VERSION,
        **target,
        "controlled": selected_provider != "local",
        "target_digest": canonical_digest(target),
    }
    return attach_digest(document, "plan_digest")


def _issue_markdown(plan: dict[str, Any]) -> str:
    metadata = {
        "provider": "local",
        "plan_digest": plan["plan_digest"],
        "target_digest": plan["target_digest"],
        "labels": plan["labels"],
        "assignee": plan["assignee"],
    }
    return (
        "---\n"
        + "\n".join(
            f"{key}: {json.dumps(value, ensure_ascii=False)}"
            for key, value in metadata.items()
        )
        + "\n---\n\n"
        + f"# {plan['title']}\n\n{plan['body'].rstrip()}\n"
    )


def apply_local_issue_plan(
    repository: Path,
    plan: dict[str, Any],
) -> dict[str, Any]:
    root = repository.resolve()
    if (
        not digest_matches(plan, "plan_digest")
        or plan.get("provider") != "local"
        or not plan.get("local_path")
    ):
        return {"status": "blocked", "blocker_codes": ["ISSUE_TARGET_REQUIRED"]}
    config = load_project_config(root)
    state = workspace_state(root)
    if config:
        blockers = branch_action_blockers(
            state["head_ref"], "write", config["branch_policy"]
        )
        if blockers:
            return {"status": "blocked", "blocker_codes": blockers}
    runtime = runtime_state(root)
    if runtime["status"] != "active":
        return {
            "status": "blocked",
            "blocker_codes": runtime["blocker_codes"],
        }
    relative = _safe_local_path(root, plan["local_path"])
    target = root / relative
    if target.exists():
        return {
            "status": "blocked",
            "blocker_codes": ["GOVERNANCE_CONFLICT", "HANDOFF_REQUIRED"],
        }
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        _issue_markdown(plan),
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, target)
    return {
        "status": "created",
        "provider": "local",
        "path": relative,
        "plan_digest": plan["plan_digest"],
        "blocker_codes": [],
    }


def prepare_remote_issue_request(
    repository: Path,
    plan: dict[str, Any],
    *,
    decision: dict[str, Any] | None,
    projection_id: str,
) -> dict[str, Any]:
    if (
        not digest_matches(plan, "plan_digest")
        or plan.get("provider") != "github"
        or not plan.get("repository")
    ):
        return {"status": "blocked", "blocker_codes": ["ISSUE_TARGET_REQUIRED"]}
    state = workspace_state(repository)
    config = load_project_config(repository)
    if config:
        boundary_blockers = branch_action_blockers(
            state["head_ref"], "issue-write", config["branch_policy"]
        )
        if boundary_blockers:
            return {
                "status": "blocked",
                "blocker_codes": boundary_blockers,
            }
    runtime = runtime_state(repository)
    if (
        runtime["status"] != "active"
        or runtime["projection_id"] != projection_id
    ):
        blockers = set(runtime["blocker_codes"])
        if runtime["projection_id"] != projection_id:
            blockers.add("GOVERNANCE_PROJECTION_STALE")
        return {
            "status": "blocked",
            "blocker_codes": sorted(blockers),
        }
    target = {
        key: plan[key]
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
    blockers = task_decision_blockers(
        decision,
        task_id=str((decision or {}).get("task_id") or ""),
        projection_id=projection_id,
        workspace_digest=state["workspace_digest"],
        exact_action="delivery:remote-issue",
        target=target,
    )
    if blockers:
        return {"status": "blocked", "blocker_codes": blockers}
    return {
        "status": "provider-required",
        "provider": "github",
        "request": target,
        "plan_digest": plan["plan_digest"],
        "blocker_codes": [],
    }


def validate_remote_issue_receipt(
    plan: dict[str, Any],
    receipt: dict[str, Any],
) -> list[str]:
    if not digest_matches(plan, "plan_digest") or plan.get("provider") != "github":
        return ["ISSUE_TARGET_REQUIRED"]
    if (
        receipt.get("status") != "succeeded"
        or receipt.get("provider") != "github"
        or receipt.get("repository") != plan.get("repository")
        or receipt.get("target_digest") != plan.get("target_digest")
        or not isinstance(receipt.get("url"), str)
        or not receipt["url"].startswith("https://")
        or not isinstance(receipt.get("issue_number"), int)
        or receipt["issue_number"] < 1
    ):
        return ["REMOTE_ISSUE_WRITE_FAILED", "HANDOFF_REQUIRED"]
    return []
