"""Branch classification and controlled-boundary checks."""

from __future__ import annotations

import fnmatch
from typing import Any

from .policy import default_project_config


def default_branch_gate() -> dict[str, Any]:
    return default_project_config(mode="bootstrap")["branch_policy"]


def classify_branch(ref: str | None, policy: dict[str, Any]) -> str:
    if not ref:
        return "unclassified"
    if any(fnmatch.fnmatchcase(ref, pattern) for pattern in policy["private"]):
        return "private"
    if any(fnmatch.fnmatchcase(ref, pattern) for pattern in policy["controlled"]):
        return "controlled"
    return "unclassified"


def branch_is_controlled(
    ref: str | None,
    policy: dict[str, Any] | None = None,
) -> bool:
    return classify_branch(ref, policy or default_branch_gate()) != "private"


def branch_action_blockers(
    ref: str | None,
    action: str,
    policy: dict[str, Any],
) -> list[str]:
    if action not in policy["actions"]:
        return []
    if classify_branch(ref, policy) == "private":
        return []
    return ["CONTROLLED_BRANCH_GATE_REQUIRED", "HANDOFF_REQUIRED"]
