"""Ephemeral task decisions bound to one action and repository state."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from .artifacts import SCHEMA_VERSION, attach_digest, canonical_digest, digest_matches
from .workspace import run_git


_TASK_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class DecisionStateError(ValueError):
    """Stable failure for unsafe or inconsistent ephemeral decision state."""

    def __init__(self, *blocker_codes: str) -> None:
        self.blocker_codes = list(blocker_codes)
        super().__init__(", ".join(self.blocker_codes))


def create_task_decision(
    *,
    task_id: str,
    projection_id: str,
    workspace_digest: str,
    exact_action: str,
    target: dict[str, Any],
) -> dict[str, Any]:
    if not _TASK_ID.fullmatch(task_id):
        raise ValueError("task_id must be a safe stable identifier")
    document = {
        "artifact_type": "task-decision",
        "schema_version": SCHEMA_VERSION,
        "task_id": task_id,
        "projection_id": projection_id,
        "workspace_digest": workspace_digest,
        "exact_action": exact_action,
        "target_digest": canonical_digest(target),
        "status": "active",
    }
    return attach_digest(document, "decision_digest")


def decision_path(repository: Path, task_id: str) -> Path:
    if not _TASK_ID.fullmatch(task_id):
        raise ValueError("task_id must be a safe stable identifier")
    root = repository.resolve()
    target = (root / ".harness" / "runtime" / task_id / "decision.json").resolve()
    if not target.is_relative_to(root):
        raise ValueError("task decision escapes the repository")
    return target


def save_task_decision(repository: Path, decision: dict[str, Any]) -> Path:
    if not digest_matches(decision, "decision_digest"):
        raise DecisionStateError("TASK_DECISION_STALE", "HANDOFF_REQUIRED")
    target = decision_path(repository, decision["task_id"])
    relative = target.relative_to(repository.resolve()).as_posix()
    ignored = run_git(
        repository,
        ["check-ignore", "--quiet", "--", relative],
        check=False,
    )
    if ignored.returncode != 0:
        raise DecisionStateError(
            "GOVERNANCE_PRECONDITION_FAILED",
            "HANDOFF_REQUIRED",
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, target)
    return target


def end_task_decision(repository: Path, task_id: str) -> dict[str, Any]:
    """Expire one exact task decision by removing its ignored runtime state."""

    path = decision_path(repository, task_id)
    decision = load_task_decision(repository, task_id)
    if decision is None or not digest_matches(decision, "decision_digest"):
        return {
            "status": "blocked",
            "task_id": task_id,
            "blocker_codes": ["TASK_DECISION_STALE", "HANDOFF_REQUIRED"],
        }
    try:
        path.unlink()
        path.parent.rmdir()
    except OSError:
        if path.exists():
            return {
                "status": "blocked",
                "task_id": task_id,
                "blocker_codes": [
                    "GOVERNANCE_PRECONDITION_FAILED",
                    "HANDOFF_REQUIRED",
                ],
            }
    return {
        "status": "expired",
        "task_id": task_id,
        "decision_digest": decision["decision_digest"],
        "blocker_codes": [],
    }


def load_task_decision(repository: Path, task_id: str) -> dict[str, Any] | None:
    path = decision_path(repository, task_id)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def task_decision_blockers(
    decision: dict[str, Any] | None,
    *,
    task_id: str,
    projection_id: str,
    workspace_digest: str,
    exact_action: str,
    target: dict[str, Any],
) -> list[str]:
    if decision is None:
        return ["TASK_DECISION_REQUIRED", "HANDOFF_REQUIRED"]
    expected = {
        "task_id": task_id,
        "projection_id": projection_id,
        "workspace_digest": workspace_digest,
        "exact_action": exact_action,
        "target_digest": canonical_digest(target),
        "status": "active",
    }
    if (
        not digest_matches(decision, "decision_digest")
        or any(decision.get(key) != value for key, value in expected.items())
    ):
        return ["TASK_DECISION_STALE", "HANDOFF_REQUIRED"]
    return []
