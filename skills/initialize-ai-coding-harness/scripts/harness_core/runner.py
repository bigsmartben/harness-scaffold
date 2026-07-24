"""Run Local or GitHub Actions tasks and normalize Evidence."""

from __future__ import annotations

import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from .automation import authorize_task
from .platform import (
    normalize_github_platform_evidence,
    platform_evidence_complete,
)


EVIDENCE_FIELDS = {
    "run_id",
    "task_id",
    "status",
    "validation_level",
    "duration",
    "summary",
    "primary_error",
    "artifacts",
    "full_log",
    "blocker_codes",
    "backend",
    "change_manifest",
    "selection",
    "confirmation",
    "automation_level",
    "confirmation_status",
    "backend_calls",
    "formal_authority",
    "platform",
}


def _timeout_seconds(value: str) -> float:
    if value.endswith("ms"):
        return int(value[:-2]) / 1000
    unit = value[-1]
    amount = int(value[:-1])
    return amount * {"s": 1, "m": 60, "h": 3600}[unit]


def _primary_error(output: str) -> str | None:
    for line in output.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:500]
    return None


def _evidence(
    *,
    task: dict[str, Any],
    validation_level: str,
    backend: str,
    status: str,
    duration: float,
    output: str,
    full_log: str,
    change_manifest: str | None,
    selection: str | None,
    confirmation: dict[str, Any] | None,
    automation_level: str,
    confirmation_status: str,
    backend_calls: int,
    formal_authority: bool,
    platform: dict[str, Any] | None,
    blocker_codes: list[str] | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    failed = status in {"failed", "blocked"}
    return {
        "run_id": run_id or f"run-{uuid.uuid4().hex}",
        "task_id": task["id"],
        "status": status,
        "validation_level": validation_level,
        "duration": f"{duration:.3f}s",
        "summary": (
            f"{task['id']} passed via {backend}"
            if status == "passed"
            else f"{task['id']} {status} via {backend}: {_primary_error(output) or 'no error output'}"
        ),
        "primary_error": _primary_error(output) if failed else None,
        "artifacts": task.get("outputs", {}).get("artifacts", []),
        "full_log": full_log,
        "blocker_codes": blocker_codes or [],
        "backend": backend,
        "change_manifest": change_manifest,
        "selection": selection,
        "confirmation": confirmation,
        "automation_level": automation_level,
        "confirmation_status": confirmation_status,
        "backend_calls": backend_calls,
        "formal_authority": formal_authority,
        "platform": platform,
    }


def run_local_task(
    task: dict[str, Any],
    command: list[str],
    repository: Path,
    validation_level: str,
    *,
    change_manifest: str | None = None,
    selection: str | None = None,
    request: dict[str, Any] | None = None,
    confirmation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run a registered command array without a shell and save its full log."""

    started = time.monotonic()
    run_id = uuid.uuid4().hex
    log_path = repository / ".harness" / "runs" / run_id / "full.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    authorization = authorize_task(
        task, validation_level, request=request, confirmation=confirmation
    )
    if not authorization["allowed"]:
        output = (
            f"{task['id']} was not dispatched: "
            f"{authorization['confirmation_status']}"
        )
        log_path.write_text(output, encoding="utf-8")
        return _evidence(
            task=task,
            validation_level=validation_level,
            backend="local",
            status="blocked",
            duration=time.monotonic() - started,
            output=output,
            full_log=log_path.relative_to(repository).as_posix(),
            change_manifest=change_manifest,
            selection=selection,
            confirmation=confirmation,
            automation_level=authorization["automation_level"],
            confirmation_status=authorization["confirmation_status"],
            backend_calls=0,
            formal_authority=False,
            platform=None,
            blocker_codes=authorization["blocker_codes"],
            run_id=f"run-{run_id}",
        )
    working_directory = repository
    if task.get("working_directory") not in {None, "repository-root"}:
        working_directory = repository / task["working_directory"]
    try:
        completed = subprocess.run(
            command,
            cwd=working_directory,
            capture_output=True,
            text=True,
            shell=False,
            timeout=_timeout_seconds(task["timeout"]),
            check=False,
        )
        output = completed.stdout + completed.stderr
        status = "passed" if completed.returncode == 0 else "failed"
        blockers: list[str] = []
    except subprocess.TimeoutExpired as exc:
        output = f"Task timed out after {task['timeout']}\n{exc.stdout or ''}{exc.stderr or ''}"
        status = "failed"
        blockers = []
    except (FileNotFoundError, OSError) as exc:
        output = str(exc)
        status = "blocked"
        blockers = ["BACKEND_UNAVAILABLE"]
    log_path.write_text(output, encoding="utf-8")
    return _evidence(
        task=task,
        validation_level=validation_level,
        backend="local",
        status=status,
        duration=time.monotonic() - started,
        output=output,
        full_log=log_path.relative_to(repository).as_posix(),
        change_manifest=change_manifest,
        selection=selection,
        confirmation=confirmation,
        automation_level=authorization["automation_level"],
        confirmation_status=authorization["confirmation_status"],
        backend_calls=1,
        formal_authority=False,
        platform=None,
        blocker_codes=blockers,
        run_id=f"run-{run_id}",
    )


def run_github_actions_task(
    task: dict[str, Any],
    dispatch: Callable[[dict[str, Any]], dict[str, Any]],
    repository: Path,
    validation_level: str,
    *,
    change_manifest: str | None = None,
    selection: str | None = None,
    request: dict[str, Any] | None = None,
    confirmation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Normalize an injected GitHub Actions dispatcher result."""

    started = time.monotonic()
    authorization = authorize_task(
        task, validation_level, request=request, confirmation=confirmation
    )
    if not authorization["allowed"]:
        return _evidence(
            task=task,
            validation_level=validation_level,
            backend="github-actions",
            status="blocked",
            duration=time.monotonic() - started,
            output=f"{task['id']} was not dispatched",
            full_log="",
            change_manifest=change_manifest,
            selection=selection,
            confirmation=confirmation,
            automation_level=authorization["automation_level"],
            confirmation_status=authorization["confirmation_status"],
            backend_calls=0,
            formal_authority=False,
            platform=None,
            blocker_codes=authorization["blocker_codes"],
        )
    result = dispatch(task)
    output = str(result.get("log", ""))
    run_id = str(result.get("run_id", uuid.uuid4().hex))
    log_path = repository / ".harness" / "runs" / run_id / "full.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(output, encoding="utf-8")
    status = result.get("status", "blocked")
    blockers = [] if status in {"passed", "failed", "cancelled"} else ["BACKEND_UNAVAILABLE"]
    platform_request = request or {
        "task_id": task["id"],
        "category": task.get("category"),
        "validation_level": validation_level,
        "automation_level": authorization["automation_level"],
    }
    platform = normalize_github_platform_evidence(
        result,
        platform_request,
        confirmation or {},
    )
    formal_authority = (
        authorization["automation_level"] == "critical"
        and platform_evidence_complete(platform, task.get("category", ""))
    )
    if authorization["automation_level"] == "critical" and not formal_authority:
        status = "blocked"
        blockers = ["EVIDENCE_INCOMPLETE"]
    return _evidence(
        task=task,
        validation_level=validation_level,
        backend="github-actions",
        status=status,
        duration=time.monotonic() - started,
        output=output,
        full_log=log_path.relative_to(repository).as_posix(),
        change_manifest=change_manifest,
        selection=selection,
        confirmation=confirmation,
        automation_level=authorization["automation_level"],
        confirmation_status=authorization["confirmation_status"],
        backend_calls=1,
        formal_authority=formal_authority,
        platform=platform,
        blocker_codes=blockers,
        run_id=run_id if run_id.startswith("run-") else f"run-{run_id}",
    )
