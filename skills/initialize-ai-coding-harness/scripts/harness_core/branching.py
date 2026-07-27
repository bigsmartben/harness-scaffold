"""Classify Git refs against the narrow Harness branch boundary."""

from __future__ import annotations

from fnmatch import fnmatchcase
from typing import Any


def default_branch_gate() -> dict[str, Any]:
    """Return the explicit controlled-branch gate for new Harness configs."""

    return {
        "controlled": [
            "refs/heads/main",
            "refs/heads/master",
            "refs/heads/release/**",
            "refs/heads/hotfix/**",
        ],
        "unmatched": "unrestricted",
        "actions": ["push", "merge"],
        "confirmation": "strong",
        "platform_gate": "required",
        "blocker_codes": [
            "CONTROLLED_BRANCH_GATE_REQUIRED",
            "HANDOFF_REQUIRED",
        ],
    }


def branch_is_controlled(
    ref: str, action: str, branch_gate: dict[str, Any]
) -> bool:
    """Return true only for an explicitly gated action and controlled ref."""

    return action in branch_gate.get("actions", []) and any(
        fnmatchcase(ref, pattern)
        for pattern in branch_gate.get("controlled", [])
    )
