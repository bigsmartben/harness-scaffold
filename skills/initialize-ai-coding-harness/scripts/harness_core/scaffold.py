"""Apply only explicitly approved Harness scaffold actions."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Any


HARNESS_MARKER = "<!-- ai-coding-harness -->"
PLACEHOLDER = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


def _render(text: str, context: dict[str, str]) -> str:
    missing: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in context:
            missing.add(key)
            return match.group(0)
        return str(context[key])

    rendered = PLACEHOLDER.sub(replace, text)
    if missing:
        raise ValueError(f"missing template values: {', '.join(sorted(missing))}")
    return rendered


def _in_scope(path: str, scopes: list[str]) -> bool:
    candidate = PurePosixPath(path)
    for scope in scopes:
        if scope.endswith("/**") and (
            path == scope[:-3] or path.startswith(scope[:-2])
        ):
            return True
        if candidate == PurePosixPath(scope):
            return True
    return False


def apply_plan(plan: dict[str, Any], assets: Path) -> dict[str, Any]:
    """Apply an approved plan and return changed/unchanged paths."""

    if not plan.get("approved"):
        raise PermissionError("plan is not approved")
    if plan.get("blocker_codes"):
        raise PermissionError("plan contains blockers")
    repository_root = Path(plan["repository_root"]).resolve()
    scopes = plan.get("write_scope", [])
    context = plan.get("render_context", {})
    changed: list[str] = []
    unchanged: list[str] = []

    for action in plan.get("actions", []):
        relative = action["path"].replace("\\", "/")
        if not _in_scope(relative, scopes):
            raise PermissionError(f"WRITE_SCOPE_EXPANDED: {relative}")
        target = (repository_root / relative).resolve()
        if not target.is_relative_to(repository_root):
            raise PermissionError(f"WRITE_SCOPE_EXPANDED: {relative}")
        template = (assets / action["template"]).resolve()
        if not template.is_relative_to(assets.resolve()) or not template.is_file():
            raise FileNotFoundError(action["template"])
        desired = _render(template.read_text(encoding="utf-8"), context)

        if action.get("merge") == "preserve-existing" and target.is_file():
            current = target.read_text(encoding="utf-8")
            if HARNESS_MARKER not in current:
                desired = f"{current.rstrip()}\n\n{desired}"
            else:
                unchanged.append(relative)
                continue
        current = target.read_text(encoding="utf-8") if target.is_file() else None
        if current == desired:
            unchanged.append(relative)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(desired, encoding="utf-8", newline="\n")
        changed.append(relative)

    return {"changed": changed, "unchanged": unchanged}
