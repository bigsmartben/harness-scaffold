"""Preflight and apply an explicitly approved 1.0 Harness Plan."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any

from .artifacts import (
    artifact_digest,
    canonical_digest,
    content_digest,
    path_digest,
)
from .contracts import validate_runtime_artifact
from .discovery import discover_repository, summarize_discovery
from .templates import render_template, replace_marked_block


def _in_scope(path: str, scopes: list[str]) -> bool:
    candidate = PurePosixPath(path)
    return any(candidate == PurePosixPath(scope) for scope in scopes)


def _fail(code: str, message: str) -> None:
    raise PermissionError(f"{code} + HANDOFF_REQUIRED: {message}")


def planned_action_content(
    action: dict[str, Any],
    repository_root: Path,
    assets: Path,
    context: dict[str, str],
) -> str:
    """Render the exact approved target content without mutating."""

    template = (assets / action["template"]).resolve()
    if not template.is_relative_to(assets.resolve()) or not template.is_file():
        raise FileNotFoundError(action["template"])
    rendered = render_template(template.read_text(encoding="utf-8"), context)
    if action["merge"] == "replace-marked-block":
        target = repository_root / action["path"]
        current = target.read_text(encoding="utf-8") if target.is_file() else ""
        return replace_marked_block(current, rendered)
    return rendered


def apply_plan(
    plan: dict[str, Any],
    assets: Path,
    approval: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply only after every binding and target passes zero-write preflight."""

    assets = assets.resolve()
    schema_dir = assets / "schemas"
    if validate_runtime_artifact(plan, schema_dir):
        _fail("PLAN_STALE", "Plan does not satisfy the runtime schema")
    if artifact_digest(plan, "plan_digest") != plan.get("plan_digest"):
        _fail("PLAN_STALE", "Plan digest does not match Plan content")
    if (
        not isinstance(approval, dict)
        or validate_runtime_artifact(approval, schema_dir)
        or approval.get("plan_digest") != plan["plan_digest"]
    ):
        _fail("PLAN_STALE", "Approval does not bind the current Plan")
    if plan["blocker_codes"]:
        raise PermissionError(
            f"{' + '.join(plan['blocker_codes'])} + HANDOFF_REQUIRED: "
            "Plan contains blockers"
        )

    repository_root = Path(plan["repository_root"]).resolve()
    scopes = plan["write_scope"]
    actions = plan["actions"]
    action_paths = [action["path"].replace("\\", "/") for action in actions]
    if any(path not in scopes for path in action_paths):
        _fail(
            "WRITE_SCOPE_EXPANDED",
            next(path for path in action_paths if path not in scopes),
        )
    if len(action_paths) != len(set(action_paths)) or set(action_paths) != set(scopes):
        _fail("PLAN_STALE", "actions and exact write_scope differ")

    current_facts = discover_repository(repository_root)
    current_summary = summarize_discovery(
        current_facts, ignored_paths=set(action_paths)
    )
    if (
        current_summary != plan["source_facts"]
        or canonical_digest(current_summary) != plan["source_facts_digest"]
    ):
        _fail("PLAN_STALE", "discovery facts changed after planning")
    for relative, expected in plan["source_state"].items():
        if path_digest(repository_root / relative) != expected:
            _fail("PLAN_STALE", f"fact source changed: {relative}")

    prepared: list[tuple[str, Path, str | None]] = []
    for action in actions:
        relative = action["path"].replace("\\", "/")
        if not _in_scope(relative, scopes):
            _fail("WRITE_SCOPE_EXPANDED", relative)
        target = (repository_root / relative).resolve()
        if not target.is_relative_to(repository_root):
            _fail("WRITE_SCOPE_EXPANDED", relative)

        current_digest = path_digest(target)
        if current_digest == action["after_digest"]:
            prepared.append((relative, target, None))
            continue
        if current_digest != action["before_digest"]:
            _fail("PLAN_STALE", f"target changed: {relative}")
        try:
            desired = planned_action_content(
                action,
                repository_root,
                assets,
                plan["render_context"],
            )
        except (FileNotFoundError, ValueError) as exc:
            _fail("PLAN_STALE", str(exc))
        if content_digest(desired) != action["after_digest"]:
            _fail("PLAN_STALE", f"rendered output changed: {relative}")
        prepared.append((relative, target, desired))

    changed: list[str] = []
    unchanged: list[str] = []
    for relative, target, desired in prepared:
        if desired is None:
            unchanged.append(relative)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(desired, encoding="utf-8", newline="\n")
        changed.append(relative)

    return {
        "status": "applied",
        "plan_digest": plan["plan_digest"],
        "changed": changed,
        "unchanged": unchanged,
    }
