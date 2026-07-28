"""Execute one registered local task_ref and write stable validation Evidence."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import yaml

from .artifacts import SCHEMA_VERSION, attach_digest, canonical_digest


def _load_tasks(repository: Path) -> list[dict[str, Any]]:
    path = repository / ".harness" / "tasks.yaml"
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or not isinstance(
        document.get("tasks"), list
    ):
        raise ValueError("CONFIG_INVALID: .harness/tasks.yaml has no tasks list")
    return [
        task for task in document["tasks"] if isinstance(task, dict)
    ]


def resolve_local_task(repository: Path, task_ref: str) -> dict[str, Any]:
    matches = [
        task
        for task in _load_tasks(repository)
        if task.get("id") == task_ref
    ]
    if len(matches) != 1:
        raise ValueError(
            f"TOOL_ACTION_UNCLASSIFIED: task_ref {task_ref!r} must resolve once"
        )
    task = matches[0]
    if task.get("backend") != "local":
        raise ValueError(
            f"HANDOFF_REQUIRED: task_ref {task_ref!r} requires "
            f"{task.get('backend', 'an external platform')}"
        )
    if not task.get("auto_allowed") or task.get("automation_level") != "routine":
        raise ValueError(
            f"TASK_DECISION_REQUIRED: task_ref {task_ref!r} is not routine"
        )
    command = task.get("command")
    if not isinstance(command, list) or not all(
        isinstance(item, str) and item for item in command
    ):
        raise ValueError(f"CONFIG_INVALID: {task_ref!r} has no argv command")
    return task


def _timeout_seconds(value: Any) -> int:
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and value.endswith("m"):
        return int(value[:-1]) * 60
    if isinstance(value, str) and value.endswith("s"):
        return int(value[:-1])
    return 300


def run_local_task_ref(
    repository: Path,
    task_ref: str,
    *,
    scope: str,
) -> dict[str, Any]:
    root = repository.resolve()
    task = resolve_local_task(root, task_ref)
    if scope != task.get("supports_scope"):
        raise ValueError(
            f"GOVERNANCE_SCOPE_UNRESOLVED: {task_ref!r} supports only "
            f"{task.get('supports_scope')!r}"
        )
    source_command = list(task["command"])
    command = list(source_command)
    child_environment: dict[str, str] | None = None
    if command[0] == "@harness-python":
        command[0] = sys.executable
        child_environment = os.environ.copy()
        import_paths = [
            item
            for item in sys.path
            if item
            and (
                Path(item).resolve() == (root / "src").resolve()
                or "site-packages" in Path(item).parts
            )
        ]
        child_environment["PYTHONPATH"] = os.pathsep.join(
            import_paths
        )
    started = time.monotonic()
    completed = subprocess.run(
        command,
        cwd=root,
        env=child_environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=_timeout_seconds(task.get("timeout")),
    )
    elapsed = round(time.monotonic() - started, 3)
    report = {
        "artifact_type": "task-evidence",
        "schema_version": SCHEMA_VERSION,
        "task_ref": task_ref,
        "scope": scope,
        "status": "passed" if completed.returncode == 0 else "failed",
        "returncode": completed.returncode,
        "duration_seconds": elapsed,
        "source_command": source_command,
        "resolved_command_digest": canonical_digest(command),
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "blocker_codes": (
            []
            if completed.returncode == 0
            else ["GOVERNANCE_EVIDENCE_INCOMPLETE"]
        ),
    }
    report = attach_digest(report, "evidence_digest")
    output = task.get("outputs", {}).get("report")
    if not isinstance(output, str) or not output:
        raise ValueError(f"CONFIG_INVALID: {task_ref!r} has no report path")
    target = (root / output).resolve()
    if not target.is_relative_to(root):
        raise ValueError("GOVERNANCE_SCOPE_UNRESOLVED: report leaves repository")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report
