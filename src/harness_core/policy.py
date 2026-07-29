"""Versioned project-policy loading, planning, and atomic publication."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .artifacts import (
    SCHEMA_VERSION,
    attach_digest,
    canonical_digest,
    digest_matches,
)
from .contracts import validate_project_config


def default_project_config(
    *,
    mode: str,
    hooks_enabled: bool = False,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "project_policy": {
            "local_execution": "continuous",
            "validation": "minimum-sufficient",
            "hooks": "enabled" if hooks_enabled else "optional",
            "declarations": {},
        },
        "issue_planning": {
            "default_provider": "local",
            "local_directory": ".harness/issues",
            "remote": None,
        },
        "branch_policy": {
            "private": ["refs/heads/codex/**", "refs/heads/agent/**"],
            "controlled": [
                "refs/heads/main",
                "refs/heads/master",
                "refs/heads/release/**",
                "refs/heads/hotfix/**",
            ],
            "unmatched": "controlled",
            "actions": [
                "write",
                "commit",
                "issue-write",
                "push",
                "pull-request",
                "merge",
                "publish",
                "release",
                "deploy",
            ],
        },
    }


def load_project_config(repository: Path) -> dict[str, Any] | None:
    path = repository / ".harness" / "harness.yaml"
    if not path.is_file():
        return None
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return None
    if not isinstance(value, dict) or validate_project_config(value):
        return None
    return value


def render_project_config(document: dict[str, Any]) -> str:
    return yaml.safe_dump(
        document,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )


def project_policy_digest(config: dict[str, Any]) -> str:
    return canonical_digest(config["project_policy"])


def build_project_policy_plan(
    repository: Path,
    *,
    changes: dict[str, Any],
) -> dict[str, Any]:
    """Build a zero-write plan for one explicit project-policy change."""

    from .codex_adapter import runtime_state
    from .initializer import build_initialization_plan
    from .workspace import workspace_state

    root = repository.resolve()
    current = load_project_config(root)
    runtime = runtime_state(root)
    blockers = set(runtime["blocker_codes"])
    if current is None or not isinstance(changes, dict) or not changes:
        blockers.add("CONFIG_INVALID")
        next_config = current or {}
    else:
        next_config = {
            **current,
            "project_policy": {
                **current["project_policy"],
                **changes,
            },
        }
        blockers.update(
            issue.code for issue in validate_project_config(next_config)
        )

    initialization_plan = (
        build_initialization_plan(
            root,
            project_config_override=next_config,
            include_projection=True,
        )
        if current is not None and not blockers
        else None
    )
    if initialization_plan is not None:
        blockers.update(initialization_plan["blocker_codes"])
    workspace = workspace_state(root)
    document = {
        "artifact_type": "project-policy-plan",
        "schema_version": SCHEMA_VERSION,
        "workspace_digest": workspace["workspace_digest"],
        "previous_projection_id": runtime.get("projection_id"),
        "projection_id": (
            initialization_plan["projection_id"]
            if initialization_plan is not None
            else None
        ),
        "current_policy_digest": (
            project_policy_digest(current) if current is not None else None
        ),
        "changes": changes,
        "initialization_plan": initialization_plan,
        "write_scope": (
            initialization_plan["write_scope"]
            if initialization_plan is not None
            else []
        ),
        "blocker_codes": sorted(blockers),
    }
    return attach_digest(document, "plan_digest")


def apply_project_policy_plan(
    repository: Path,
    plan: dict[str, Any],
    *,
    approved_plan_digest: str | None,
) -> dict[str, Any]:
    """Apply a current policy plan through the initializer's rollback boundary."""

    from .codex_adapter import runtime_state
    from .initializer import apply_initialization_plan
    from .workspace import workspace_state

    root = repository.resolve()
    if (
        not digest_matches(plan, "plan_digest")
        or approved_plan_digest != plan.get("plan_digest")
    ):
        return {
            "status": "blocked",
            "blocker_codes": ["PROJECT_POLICY_PLAN_STALE", "HANDOFF_REQUIRED"],
        }
    if plan.get("blocker_codes"):
        return {"status": "blocked", "blocker_codes": plan["blocker_codes"]}
    current = load_project_config(root)
    runtime = runtime_state(root)
    workspace = workspace_state(root)
    if (
        current is None
        or runtime["status"] != "active"
        or workspace["workspace_digest"] != plan.get("workspace_digest")
        or runtime["projection_id"] != plan.get("previous_projection_id")
        or project_policy_digest(current) != plan.get("current_policy_digest")
    ):
        return {
            "status": "blocked",
            "blocker_codes": ["PROJECT_POLICY_PLAN_STALE", "HANDOFF_REQUIRED"],
        }
    initialization_plan = plan.get("initialization_plan")
    if not isinstance(initialization_plan, dict):
        return {
            "status": "blocked",
            "blocker_codes": ["PROJECT_POLICY_PLAN_STALE", "HANDOFF_REQUIRED"],
        }
    result = apply_initialization_plan(
        root,
        initialization_plan,
        approved_plan_digest=initialization_plan.get("plan_digest"),
    )
    if result["status"] != "applied":
        return result
    return {
        "status": "applied",
        "previous_projection_id": plan["previous_projection_id"],
        "projection_id": result["projection_id"],
        "changed_paths": result["changed_paths"],
        "plan_digest": plan["plan_digest"],
        "blocker_codes": [],
    }
