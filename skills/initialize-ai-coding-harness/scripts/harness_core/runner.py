"""Run Local or Adapter-backed Tasks and emit digest-bound Evidence."""

from __future__ import annotations

import re
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Protocol

from .artifacts import SCHEMA_VERSION, attach_digest, canonical_digest
from .automation import CRITICAL_CATEGORIES, authorize_task
from .bindings import execution_binding_blockers
from .branching import branch_is_controlled, default_branch_gate
from .platform import normalize_git_remote_evidence, platform_evidence_complete


DIGEST = re.compile(r"^sha256:[a-f0-9]{64}$")
MISSING_DIGEST = canonical_digest({"binding": "missing"})
EVIDENCE_FIELDS = {
    "artifact_type",
    "schema_version",
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
    "grant_digest",
    "manifest_digest",
    "diff_digest",
    "selection_digest",
    "request_digest",
    "commit_sha",
    "confirmation_status",
    "automation_level",
    "backend_calls",
    "formal_authority",
    "platform",
    "evidence_digest",
}


class PlatformAdapter(Protocol):
    """The only supported platform execution protocol."""

    def prepare(
        self, task: dict[str, Any], request: dict[str, Any]
    ) -> dict[str, Any]: ...

    def dispatch(self, prepared: dict[str, Any]) -> dict[str, Any]: ...

    def poll(self, locator: dict[str, Any]) -> dict[str, Any]: ...

    def normalize(
        self,
        run: dict[str, Any],
        request: dict[str, Any],
        confirmation: dict[str, Any] | None,
    ) -> dict[str, Any]: ...


def _timeout_seconds(value: str) -> float:
    if value.endswith("ms"):
        return int(value[:-2]) / 1000
    return int(value[:-1]) * {"s": 1, "m": 60, "h": 3600}[value[-1]]


def _primary_error(output: str) -> str | None:
    for line in output.splitlines():
        if stripped := line.strip():
            return stripped[:500]
    return None


def _digest(document: dict[str, Any] | None, field: str) -> str:
    value = document.get(field) if isinstance(document, dict) else None
    return value if isinstance(value, str) and DIGEST.match(value) else MISSING_DIGEST


def _write_log(repository: Path, run_id: str, output: str) -> str:
    log_path = repository / ".harness" / "runs" / run_id / "full.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(output, encoding="utf-8", newline="\n")
    return log_path.relative_to(repository).as_posix()


def _evidence(
    *,
    task: dict[str, Any],
    validation_level: str,
    backend: str,
    status: str,
    duration: float,
    output: str,
    full_log: str,
    grant: dict[str, Any] | None,
    manifest: dict[str, Any] | None,
    selection: dict[str, Any] | None,
    request: dict[str, Any] | None,
    confirmation_status: str,
    automation_level: str,
    backend_calls: int,
    formal_authority: bool,
    platform: dict[str, Any] | None,
    blocker_codes: list[str] | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    failed = status in {"failed", "blocked"}
    evidence = {
        "artifact_type": "evidence",
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id or f"run-{uuid.uuid4().hex}",
        "task_id": task["id"],
        "status": status,
        "validation_level": validation_level,
        "duration": f"{duration:.3f}s",
        "summary": (
            f"{task['id']} passed via {backend}"
            if status == "passed"
            else f"{task['id']} {status} via {backend}: "
            f"{_primary_error(output) or 'no error output'}"
        ),
        "primary_error": _primary_error(output) if failed else None,
        "artifacts": task.get("outputs", {}).get("artifacts", []),
        "full_log": full_log,
        "blocker_codes": sorted(set(blocker_codes or [])),
        "backend": backend,
        "grant_digest": _digest(grant, "grant_digest"),
        "manifest_digest": _digest(manifest, "manifest_digest"),
        "diff_digest": _digest(selection, "diff_digest"),
        "selection_digest": _digest(selection, "selection_digest"),
        "request_digest": _digest(request, "request_digest"),
        "commit_sha": (
            str(request.get("commit_sha"))
            if isinstance(request, dict) and request.get("commit_sha")
            else "missing"
        ),
        "confirmation_status": confirmation_status,
        "automation_level": automation_level,
        "backend_calls": backend_calls,
        "formal_authority": formal_authority,
        "platform": platform,
    }
    return attach_digest(evidence, "evidence_digest")


def _preflight(
    task: dict[str, Any],
    validation_level: str,
    grant: dict[str, Any] | None,
    manifest: dict[str, Any] | None,
    selection: dict[str, Any] | None,
    request: dict[str, Any] | None,
    confirmation: dict[str, Any] | None,
    require_confirmation: bool | None = None,
) -> tuple[dict[str, Any], list[str]]:
    authorization = authorize_task(
        task,
        validation_level,
        request=request,
        confirmation=confirmation,
        require_confirmation=require_confirmation,
    )
    bindings = execution_binding_blockers(
        grant,
        manifest,
        selection,
        request,
        confirmation if authorization["confirmation_required"] else None,
    )
    blockers = sorted(
        set(authorization["blocker_codes"]) | set(bindings)
    )
    return authorization, blockers


def run_local_task(
    task: dict[str, Any],
    command: list[str],
    repository: Path,
    validation_level: str,
    *,
    grant: dict[str, Any] | None = None,
    manifest: dict[str, Any] | None = None,
    selection: dict[str, Any] | None = None,
    request: dict[str, Any] | None = None,
    confirmation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run a registered non-critical command array without a shell."""

    started = time.monotonic()
    run_id = f"run-{uuid.uuid4().hex}"
    authorization, blockers = _preflight(
        task,
        validation_level,
        grant,
        manifest,
        selection,
        request,
        confirmation,
        require_confirmation=False,
    )
    registered_command = task.get("command")
    if (
        not isinstance(registered_command, list)
        or not registered_command
        or not all(isinstance(item, str) and item for item in registered_command)
    ):
        blockers = sorted(set(blockers) | {"CONFIG_INVALID", "HANDOFF_REQUIRED"})
    elif command != registered_command:
        blockers = sorted(
            set(blockers) | {"TASK_BYPASS_ATTEMPT", "HANDOFF_REQUIRED"}
        )
    if task.get("category") in CRITICAL_CATEGORIES:
        blockers = sorted(set(blockers) | {"BACKEND_UNAVAILABLE", "HANDOFF_REQUIRED"})
    if task.get("backend") != "local":
        blockers = sorted(set(blockers) | {"BACKEND_UNAVAILABLE"})
    repository = repository.resolve()
    working_directory = repository
    if task.get("working_directory") not in {None, "repository-root"}:
        working_directory = (repository / task["working_directory"]).resolve()
        if not working_directory.is_relative_to(repository):
            blockers = sorted(
                set(blockers) | {"CONFIG_INVALID", "HANDOFF_REQUIRED"}
            )
    if blockers or not authorization["allowed"]:
        output = f"{task['id']} was not dispatched: {', '.join(blockers)}"
        full_log = _write_log(repository, run_id, output)
        return _evidence(
            task=task,
            validation_level=validation_level,
            backend="local",
            status="blocked",
            duration=time.monotonic() - started,
            output=output,
            full_log=full_log,
            grant=grant,
            manifest=manifest,
            selection=selection,
            request=request,
            confirmation_status=authorization["confirmation_status"],
            automation_level=authorization["automation_level"],
            backend_calls=0,
            formal_authority=False,
            platform=None,
            blocker_codes=blockers,
            run_id=run_id,
        )

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
        blockers = []
    except subprocess.TimeoutExpired as exc:
        output = (
            f"Task timed out after {task['timeout']}\n"
            f"{exc.stdout or ''}{exc.stderr or ''}"
        )
        status = "failed"
        blockers = []
    except (FileNotFoundError, OSError) as exc:
        output = str(exc)
        status = "blocked"
        blockers = ["BACKEND_UNAVAILABLE"]
    full_log = _write_log(repository, run_id, output)
    return _evidence(
        task=task,
        validation_level=validation_level,
        backend="local",
        status=status,
        duration=time.monotonic() - started,
        output=output,
        full_log=full_log,
        grant=grant,
        manifest=manifest,
        selection=selection,
        request=request,
        confirmation_status=authorization["confirmation_status"],
        automation_level=authorization["automation_level"],
        backend_calls=1,
        formal_authority=False,
        platform=None,
        blocker_codes=blockers,
        run_id=run_id,
    )


def run_git_remote_push_task(
    task: dict[str, Any],
    adapter: dict[str, Any],
    repository: Path,
    validation_level: str,
    *,
    grant: dict[str, Any] | None = None,
    manifest: dict[str, Any] | None = None,
    selection: dict[str, Any] | None = None,
    request: dict[str, Any] | None = None,
    confirmation: dict[str, Any] | None = None,
    branch_gate: dict[str, Any] | None = None,
    executor: Any = subprocess.run,
) -> dict[str, Any]:
    """Push one confirmed commit to one exact remote branch without a shell."""

    started = time.monotonic()
    run_id = f"run-{uuid.uuid4().hex}"
    target = request.get("target") if isinstance(request, dict) else None
    gate = branch_gate or default_branch_gate()
    controlled_target = (
        isinstance(target, str)
        and branch_is_controlled(target, "push", gate)
    )
    authorization, blockers = _preflight(
        task,
        validation_level,
        grant,
        manifest,
        selection,
        request,
        confirmation,
        require_confirmation=True if controlled_target else False,
    )
    if (
        task.get("backend") != "git-remote"
        or task.get("category") != "push"
        or adapter.get("type") != "git-remote"
    ):
        blockers = sorted(
            set(blockers) | {"CONFIG_INVALID", "HANDOFF_REQUIRED"}
        )
    execution = adapter.get("execution", {})
    if (
        execution.get("shell") is not False
        or execution.get("force") is not False
        or execution.get("operation") != "push-ref"
    ):
        blockers = sorted(
            set(blockers) | {"CONFIG_INVALID", "HANDOFF_REQUIRED"}
        )
    remote = adapter.get("remote")
    commit_sha = request.get("commit_sha") if isinstance(request, dict) else None
    if not isinstance(remote, str) or not remote:
        blockers = sorted(set(blockers) | {"CONFIG_INVALID", "HANDOFF_REQUIRED"})
    if not isinstance(target, str) or not target:
        blockers = sorted(
            set(blockers) | {"EVIDENCE_INCOMPLETE", "HANDOFF_REQUIRED"}
        )
    elif controlled_target:
        blockers = sorted(
            set(blockers)
            | {"CONTROLLED_BRANCH_GATE_REQUIRED", "HANDOFF_REQUIRED"}
        )
    if not isinstance(commit_sha, str) or not commit_sha:
        blockers = sorted(
            set(blockers) | {"EVIDENCE_INCOMPLETE", "HANDOFF_REQUIRED"}
        )
    repository = repository.resolve()
    try:
        local_head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository,
            capture_output=True,
            text=True,
            shell=False,
            timeout=30,
            check=False,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        local_head = None
    if (
        local_head is None
        or local_head.returncode != 0
        or local_head.stdout.strip() != commit_sha
    ):
        blockers = sorted(
            set(blockers) | {"EVIDENCE_BINDING_MISMATCH", "HANDOFF_REQUIRED"}
        )
    if blockers or not authorization["allowed"]:
        output = f"{task['id']} was not dispatched: {', '.join(blockers)}"
        full_log = _write_log(repository, run_id, output)
        return _evidence(
            task=task,
            validation_level=validation_level,
            backend="git-remote",
            status="blocked",
            duration=time.monotonic() - started,
            output=output,
            full_log=full_log,
            grant=grant,
            manifest=manifest,
            selection=selection,
            request=request,
            confirmation_status=authorization["confirmation_status"],
            automation_level=authorization["automation_level"],
            backend_calls=0,
            formal_authority=False,
            platform=None,
            blocker_codes=blockers,
            run_id=run_id,
        )

    branch = target.removeprefix("refs/heads/")
    target_ref = f"refs/heads/{branch}"
    command = [
        "git",
        "push",
        "--porcelain",
        "--set-upstream",
        remote,
        f"{commit_sha}:{target_ref}",
    ]
    try:
        completed = executor(
            command,
            cwd=repository,
            capture_output=True,
            text=True,
            shell=False,
            timeout=_timeout_seconds(task["timeout"]),
            check=False,
        )
        output = completed.stdout + completed.stderr
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as exc:
        output = str(exc)
        completed = None
    if completed is None or completed.returncode != 0:
        full_log = _write_log(repository, run_id, output)
        return _evidence(
            task=task,
            validation_level=validation_level,
            backend="git-remote",
            status="blocked",
            duration=time.monotonic() - started,
            output=output,
            full_log=full_log,
            grant=grant,
            manifest=manifest,
            selection=selection,
            request=request,
            confirmation_status=authorization["confirmation_status"],
            automation_level=authorization["automation_level"],
            backend_calls=1,
            formal_authority=False,
            platform=None,
            blocker_codes=["BACKEND_UNAVAILABLE"],
            run_id=run_id,
        )

    platform = normalize_git_remote_evidence(
        remote=remote,
        target_ref=target_ref,
        commit_sha=commit_sha,
        request=request,
        confirmation=confirmation,
        operation_id=run_id,
    )
    complete = platform_evidence_complete(platform, "push", request)
    full_log = _write_log(repository, run_id, output)
    return _evidence(
        task=task,
        validation_level=validation_level,
        backend="git-remote",
        status="passed" if complete else "blocked",
        duration=time.monotonic() - started,
        output=output,
        full_log=full_log,
        grant=grant,
        manifest=manifest,
        selection=selection,
        request=request,
        confirmation_status=authorization["confirmation_status"],
        automation_level=authorization["automation_level"],
        backend_calls=1,
        formal_authority=complete,
        platform=platform if complete else None,
        blocker_codes=[] if complete else ["EVIDENCE_INCOMPLETE"],
        run_id=run_id,
    )


def run_github_actions_task(
    task: dict[str, Any],
    adapter: PlatformAdapter,
    repository: Path,
    validation_level: str,
    *,
    grant: dict[str, Any] | None = None,
    manifest: dict[str, Any] | None = None,
    selection: dict[str, Any] | None = None,
    request: dict[str, Any] | None = None,
    confirmation: dict[str, Any] | None = None,
    branch_gate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute prepare → dispatch → poll → normalize exactly once."""

    started = time.monotonic()
    target = request.get("target") if isinstance(request, dict) else None
    category = str(task.get("category") or "")
    controlled_target = (
        isinstance(target, str)
        and branch_is_controlled(
            target, category, branch_gate or default_branch_gate()
        )
    )
    authorization, blockers = _preflight(
        task,
        validation_level,
        grant,
        manifest,
        selection,
        request,
        confirmation,
        require_confirmation=controlled_target,
    )
    if controlled_target and not authorization["allowed"]:
        blockers = sorted(
            set(blockers)
            | {"CONTROLLED_BRANCH_GATE_REQUIRED", "HANDOFF_REQUIRED"}
        )
    if task.get("backend") != "github-actions":
        blockers = sorted(set(blockers) | {"BACKEND_UNAVAILABLE"})
    source = task.get("source")
    if not isinstance(source, str) or not source:
        blockers = sorted(set(blockers) | {"CONFIG_INVALID", "HANDOFF_REQUIRED"})
    if blockers or not authorization["allowed"] or request is None:
        output = f"{task['id']} was not dispatched: {', '.join(blockers)}"
        return _evidence(
            task=task,
            validation_level=validation_level,
            backend="github-actions",
            status="blocked",
            duration=time.monotonic() - started,
            output=output,
            full_log="",
            grant=grant,
            manifest=manifest,
            selection=selection,
            request=request,
            confirmation_status=authorization["confirmation_status"],
            automation_level=authorization["automation_level"],
            backend_calls=0,
            formal_authority=False,
            platform=None,
            blocker_codes=blockers,
        )

    backend_calls = 0
    try:
        prepared = adapter.prepare(task, request)
        locator = adapter.dispatch(prepared)
        backend_calls = 1
        run = adapter.poll(locator)
        platform = adapter.normalize(run, request, confirmation)
    except Exception as exc:  # Adapter boundary normalizes external failures.
        output = str(exc)
        return _evidence(
            task=task,
            validation_level=validation_level,
            backend="github-actions",
            status="blocked",
            duration=time.monotonic() - started,
            output=output,
            full_log="",
            grant=grant,
            manifest=manifest,
            selection=selection,
            request=request,
            confirmation_status=authorization["confirmation_status"],
            automation_level=authorization["automation_level"],
            backend_calls=backend_calls,
            formal_authority=False,
            platform=None,
            blocker_codes=["BACKEND_UNAVAILABLE"],
        )

    if not isinstance(platform, dict):
        platform = {}
    output = str(run.get("log", ""))
    platform_complete = platform_evidence_complete(
        platform, task.get("category", ""), request
    )
    binding_blockers = execution_binding_blockers(
        grant,
        manifest,
        selection,
        request,
        confirmation if authorization["confirmation_required"] else None,
        platform,
    )
    expected_workflow = source.split("#", 1)[0]
    if platform.get("workflow") != expected_workflow:
        binding_blockers = sorted(
            set(binding_blockers)
            | {"EVIDENCE_BINDING_MISMATCH", "HANDOFF_REQUIRED"}
        )
    status = run.get("status", "blocked")
    blockers = list(binding_blockers)
    if status == "passed" and not platform_complete:
        status = "blocked"
        blockers.append("EVIDENCE_INCOMPLETE")
    elif status not in {"passed", "failed", "cancelled"}:
        status = "blocked"
        blockers.append("BACKEND_UNAVAILABLE")
    if binding_blockers:
        status = "blocked"
    platform_required_keys = {
        "artifact_type",
        "schema_version",
        "platform",
        "workflow",
        "run_id",
        "commit_sha",
        "request_digest",
        "confirmation_status",
        "approval_status",
        "required_checks",
        "protected_ref",
        "protected_environment",
        "artifact_digest",
        "source_ref",
        "platform_evidence_digest",
    }
    platform_required_values = {
        "artifact_type",
        "schema_version",
        "platform",
        "workflow",
        "run_id",
        "commit_sha",
        "request_digest",
        "confirmation_status",
        "approval_status",
        "required_checks",
        "source_ref",
        "platform_evidence_digest",
    }
    platform_shape_valid = platform_required_keys.issubset(platform) and all(
        platform.get(field)
        for field in platform_required_values
    )
    evidence_platform = platform if platform_shape_valid else None
    run_id = str(run.get("run_id") or uuid.uuid4().hex)
    evidence_run_id = run_id if run_id.startswith("run-") else f"run-{run_id}"
    full_log = _write_log(repository, evidence_run_id, output)
    formal_authority = (
        task.get("category") in CRITICAL_CATEGORIES
        and status == "passed"
        and platform_complete
        and not binding_blockers
    )
    return _evidence(
        task=task,
        validation_level=validation_level,
        backend="github-actions",
        status=status,
        duration=time.monotonic() - started,
        output=output,
        full_log=full_log,
        grant=grant,
        manifest=manifest,
        selection=selection,
        request=request,
        confirmation_status=authorization["confirmation_status"],
        automation_level=authorization["automation_level"],
        backend_calls=backend_calls,
        formal_authority=formal_authority,
        platform=evidence_platform,
        blocker_codes=blockers,
        run_id=evidence_run_id,
    )
