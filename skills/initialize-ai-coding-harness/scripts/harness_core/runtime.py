"""Build and verify 1.0 runtime artifacts and their digest chain."""

from __future__ import annotations

from typing import Any

from .artifacts import SCHEMA_VERSION, attach_digest, canonical_digest, digest_matches
from .automation import CRITICAL_CATEGORIES, effective_automation
from .contracts import runtime_artifact_is_valid
from .platform import platform_evidence_complete


def create_work_grant(
    *,
    grant_id: str,
    goal: str,
    write_scope: list[str],
    merge_target: str,
    delivery_target: str | None,
    risk_level: str,
) -> dict[str, Any]:
    return attach_digest(
        {
            "artifact_type": "work-grant",
            "schema_version": SCHEMA_VERSION,
            "grant_id": grant_id,
            "goal": goal,
            "write_scope": sorted(set(write_scope)),
            "merge_target": merge_target,
            "validation_policy": "minimum-sufficient",
            "delivery_target": delivery_target,
            "risk_level": risk_level,
            "status": "active",
        },
        "grant_digest",
    )


def create_change_manifest(
    grant: dict[str, Any],
    *,
    manifest_id: str,
    base_commit: str,
    changed_paths: list[str],
    affected_modules: list[str] | None = None,
    public_contract_changed: bool = False,
    dependency_changed: bool = False,
    build_config_changed: bool = False,
    recommended_tasks: list[str] | None = None,
) -> dict[str, Any]:
    if not digest_matches(grant, "grant_digest") or grant.get("status") != "active":
        raise ValueError("GRANT_STALE: active grant digest is required")
    return attach_digest(
        {
            "artifact_type": "change-manifest",
            "schema_version": SCHEMA_VERSION,
            "manifest_id": manifest_id,
            "grant_digest": grant["grant_digest"],
            "base_commit": base_commit,
            "changed_paths": sorted(set(changed_paths)),
            "affected_modules": sorted(set(affected_modules or [])),
            "public_contract_changed": public_contract_changed,
            "dependency_changed": dependency_changed,
            "build_config_changed": build_config_changed,
            "recommended_tasks": sorted(set(recommended_tasks or [])),
        },
        "manifest_digest",
    )


def create_selection_artifact(
    manifest: dict[str, Any],
    actual_diff: list[str],
    selection: dict[str, Any],
    *,
    selection_id: str,
) -> dict[str, Any]:
    if not digest_matches(manifest, "manifest_digest"):
        raise ValueError("EVIDENCE_BINDING_MISMATCH: manifest digest is invalid")
    selected_tasks = [
        {
            "task_id": item["task_id"],
            "automation_level": item["automation_level"],
            "decision": item["decision"],
            "reason": item["reason"],
        }
        for item in selection.get("selected_tasks", [])
    ]
    return attach_digest(
        {
            "artifact_type": "selection",
            "schema_version": SCHEMA_VERSION,
            "selection_id": selection_id,
            "manifest_digest": manifest["manifest_digest"],
            "diff_digest": canonical_digest(sorted(set(actual_diff))),
            "status": selection["status"],
            "validation_level": selection["validation_level"],
            "selected_tasks": selected_tasks,
            "skipped_tasks": selection.get("skipped_tasks", []),
            "reasons": selection.get("reasons", []),
            "blocker_codes": selection.get("blocker_codes", []),
        },
        "selection_digest",
    )


def create_task_request_artifact(
    task: dict[str, Any],
    grant: dict[str, Any],
    manifest: dict[str, Any],
    selection: dict[str, Any],
    *,
    request_id: str,
    target: str | None,
    commit_sha: str,
    source_ref: str | None = None,
    pull_request_number: int | None = None,
    merge_method: str | None = None,
    version: str | None = None,
    artifact_digest: str | None = None,
    environment: str | None = None,
) -> dict[str, Any]:
    blockers = validate_binding_chain(
        grant=grant,
        manifest=manifest,
        selection=selection,
    )
    if blockers:
        raise ValueError(": ".join(blockers))
    if selection.get("status") == "blocked":
        raise ValueError(
            "EVIDENCE_BINDING_MISMATCH + HANDOFF_REQUIRED: "
            "a blocked Selection cannot authorize a Task Request"
        )
    selected = {
        item.get("task_id"): item
        for item in selection.get("selected_tasks", [])
        if isinstance(item, dict)
    }
    if task.get("category") not in CRITICAL_CATEGORIES and task.get("id") not in selected:
        raise ValueError(
            "EVIDENCE_BINDING_MISMATCH + HANDOFF_REQUIRED: "
            "Task is not part of the final Selection"
        )
    validation_level = selection["validation_level"]
    automation = effective_automation(task, validation_level)
    selected_task = selected.get(task.get("id"))
    if (
        selected_task is not None
        and selected_task.get("automation_level")
        != automation["automation_level"]
    ):
        raise ValueError(
            "EVIDENCE_BINDING_MISMATCH + HANDOFF_REQUIRED: "
            "selected automation does not match the Task Request"
        )
    category = task.get("category")
    missing: list[str] = []
    if category in CRITICAL_CATEGORIES and not target:
        missing.append("target")
    if category == "pull-request" and not source_ref:
        missing.append("source_ref")
    if category == "merge":
        if pull_request_number is None:
            missing.append("pull_request_number")
        if merge_method not in {"merge", "squash", "rebase"}:
            missing.append("merge_method")
    if category in {"publish", "release", "deploy"}:
        if not version:
            missing.append("version")
        if not artifact_digest:
            missing.append("artifact_digest")
        if not environment:
            missing.append("environment")
    if missing:
        raise ValueError(
            "EVIDENCE_INCOMPLETE + HANDOFF_REQUIRED: missing "
            + ", ".join(missing)
        )
    return attach_digest(
        {
            "artifact_type": "task-request",
            "schema_version": SCHEMA_VERSION,
            "request_id": request_id,
            "task_id": task["id"],
            "action_semantics": task["category"],
            "validation_level": validation_level,
            "target": target,
            "source_ref": source_ref,
            "pull_request_number": pull_request_number,
            "merge_method": merge_method,
            "commit_sha": commit_sha,
            "version": version,
            "artifact_digest": artifact_digest,
            "environment": environment,
            "automation_level": automation["automation_level"],
            "policy_version": SCHEMA_VERSION,
            "grant_digest": grant["grant_digest"],
            "manifest_digest": manifest["manifest_digest"],
            "selection_digest": selection["selection_digest"],
        },
        "request_digest",
    )


def create_confirmation_artifact(
    request: dict[str, Any],
    *,
    confirmed_at: str,
) -> dict[str, Any]:
    if not digest_matches(request, "request_digest"):
        raise ValueError("EVIDENCE_BINDING_MISMATCH: request digest is invalid")
    return {
        "artifact_type": "confirmation",
        "schema_version": SCHEMA_VERSION,
        "request_digest": request["request_digest"],
        "confirmation_status": "confirmed",
        "confirmed_at": confirmed_at,
    }


def create_platform_evidence_artifact(
    request: dict[str, Any],
    *,
    workflow: str,
    run_id: str,
    commit_sha: str,
    confirmation_status: str,
    approval_status: str,
    required_checks: str,
    protected_environment: str | None,
    artifact_digest: str | None,
    source_ref: str,
    protected_ref: str | None = None,
    platform: str = "github-actions",
) -> dict[str, Any]:
    if not digest_matches(request, "request_digest"):
        raise ValueError("EVIDENCE_BINDING_MISMATCH: request digest is invalid")
    return attach_digest(
        {
            "artifact_type": "platform-evidence",
            "schema_version": SCHEMA_VERSION,
            "platform": platform,
            "workflow": workflow,
            "run_id": run_id,
            "commit_sha": commit_sha,
            "request_digest": request["request_digest"],
            "confirmation_status": confirmation_status,
            "approval_status": approval_status,
            "required_checks": required_checks,
            "protected_ref": protected_ref,
            "protected_environment": protected_environment,
            "artifact_digest": artifact_digest,
            "source_ref": source_ref,
        },
        "platform_evidence_digest",
    )


def create_evidence_artifact(
    *,
    task: dict[str, Any],
    grant: dict[str, Any],
    manifest: dict[str, Any],
    selection: dict[str, Any],
    request: dict[str, Any],
    run_id: str,
    status: str,
    validation_level: str,
    duration: str,
    summary: str,
    primary_error: str | None,
    artifacts: list[str],
    full_log: str,
    blocker_codes: list[str],
    backend: str,
    confirmation_status: str,
    backend_calls: int,
    formal_authority: bool,
    platform: dict[str, Any] | None,
) -> dict[str, Any]:
    blockers = validate_binding_chain(
        grant=grant,
        manifest=manifest,
        selection=selection,
        request=request,
        platform=platform,
    )
    if blockers:
        raise ValueError(": ".join(blockers))
    if request.get("task_id") != task.get("id") or request.get(
        "action_semantics"
    ) != task.get("category"):
        raise ValueError(
            "EVIDENCE_BINDING_MISMATCH + HANDOFF_REQUIRED: "
            "Evidence Task does not match the Request"
        )
    if task.get("backend") is not None and task.get("backend") != backend:
        raise ValueError(
            "EVIDENCE_BINDING_MISMATCH + HANDOFF_REQUIRED: "
            "Evidence Backend does not match the Task"
        )
    if status == "passed" and task.get("category") in CRITICAL_CATEGORIES:
        expected_backend = (
            "git-remote"
            if task.get("category") == "push"
            and isinstance(platform, dict)
            and platform.get("platform") == "git-remote"
            else "github-actions"
        )
        if (
            backend != expected_backend
            or confirmation_status != "confirmed"
            or not formal_authority
            or platform is None
            or not platform_evidence_complete(platform, task["category"], request)
        ):
            raise ValueError(
                "EVIDENCE_INCOMPLETE + HANDOFF_REQUIRED: "
                "critical delivery lacks formal Platform Evidence"
            )
    evidence = attach_digest(
        {
            "artifact_type": "evidence",
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "task_id": task["id"],
            "status": status,
            "validation_level": validation_level,
            "duration": duration,
            "summary": summary,
            "primary_error": primary_error,
            "artifacts": artifacts,
            "full_log": full_log,
            "blocker_codes": blocker_codes,
            "backend": backend,
            "grant_digest": grant["grant_digest"],
            "manifest_digest": manifest["manifest_digest"],
            "diff_digest": selection["diff_digest"],
            "selection_digest": selection["selection_digest"],
            "request_digest": request["request_digest"],
            "commit_sha": request["commit_sha"],
            "confirmation_status": confirmation_status,
            "automation_level": request["automation_level"],
            "backend_calls": backend_calls,
            "formal_authority": formal_authority,
            "platform": platform,
        },
        "evidence_digest",
    )
    final_blockers = validate_binding_chain(
        grant=grant,
        manifest=manifest,
        selection=selection,
        request=request,
        evidence=evidence,
        platform=platform,
    )
    if final_blockers:
        raise ValueError(": ".join(final_blockers))
    return evidence


def validate_binding_chain(
    *,
    grant: dict[str, Any],
    manifest: dict[str, Any],
    selection: dict[str, Any],
    request: dict[str, Any] | None = None,
    evidence: dict[str, Any] | None = None,
    platform: dict[str, Any] | None = None,
) -> list[str]:
    """Return stable blockers when runtime artifacts do not share one chain."""

    if (
        not runtime_artifact_is_valid(grant)
        or grant.get("artifact_type") != "work-grant"
        or grant.get("schema_version") != SCHEMA_VERSION
        or grant.get("status") != "active"
        or not digest_matches(grant, "grant_digest")
    ):
        return ["GRANT_STALE", "HANDOFF_REQUIRED"]
    digest_pairs = [
        (
            runtime_artifact_is_valid(manifest)
            and manifest.get("artifact_type") == "change-manifest"
            and manifest.get("schema_version") == SCHEMA_VERSION
            and digest_matches(manifest, "manifest_digest"),
            manifest.get("grant_digest") == grant.get("grant_digest"),
        ),
        (
            runtime_artifact_is_valid(selection)
            and selection.get("artifact_type") == "selection"
            and selection.get("schema_version") == SCHEMA_VERSION
            and digest_matches(selection, "selection_digest"),
            selection.get("manifest_digest") == manifest.get("manifest_digest"),
        ),
        (
            selection.get("diff_digest")
            == canonical_digest(sorted(set(manifest.get("changed_paths", [])))),
            True,
        ),
    ]
    if request is not None:
        selected = {
            item.get("task_id"): item
            for item in selection.get("selected_tasks", [])
            if isinstance(item, dict)
        }
        selected_task = selected.get(request.get("task_id"))
        task_is_bound = (
            request.get("action_semantics") in CRITICAL_CATEGORIES
            or selected_task is not None
        )
        digest_pairs.append(
            (
                runtime_artifact_is_valid(request)
                and request.get("artifact_type") == "task-request"
                and request.get("schema_version") == SCHEMA_VERSION
                and digest_matches(request, "request_digest"),
                request.get("grant_digest") == grant.get("grant_digest")
                and request.get("manifest_digest") == manifest.get("manifest_digest")
                and request.get("selection_digest")
                == selection.get("selection_digest")
                and request.get("validation_level")
                == selection.get("validation_level")
                and selection.get("status") != "blocked"
                and task_is_bound
                and (
                    selected_task is None
                    or selected_task.get("automation_level")
                    == request.get("automation_level")
                ),
            )
        )
    if platform is not None:
        digest_pairs.append(
            (
                runtime_artifact_is_valid(platform)
                and platform.get("artifact_type") == "platform-evidence"
                and platform.get("schema_version") == SCHEMA_VERSION
                and digest_matches(platform, "platform_evidence_digest"),
                request is not None
                and platform.get("request_digest") == request.get("request_digest")
                and platform.get("commit_sha") == request.get("commit_sha")
                and (
                    request.get("artifact_digest") is None
                    or platform.get("artifact_digest")
                    == request.get("artifact_digest")
                )
                and (
                    request.get("environment") is None
                    or platform.get("protected_environment")
                    == request.get("environment")
                ),
            )
        )
    if evidence is not None:
        digest_pairs.append(
            (
                runtime_artifact_is_valid(evidence)
                and evidence.get("artifact_type") == "evidence"
                and evidence.get("schema_version") == SCHEMA_VERSION
                and digest_matches(evidence, "evidence_digest"),
                evidence.get("grant_digest") == grant.get("grant_digest")
                and evidence.get("manifest_digest") == manifest.get("manifest_digest")
                and evidence.get("diff_digest") == selection.get("diff_digest")
                and evidence.get("selection_digest")
                == selection.get("selection_digest")
                and request is not None
                and evidence.get("request_digest") == request.get("request_digest")
                and evidence.get("task_id") == request.get("task_id")
                and evidence.get("commit_sha") == request.get("commit_sha")
                and evidence.get("platform") == platform,
            )
        )
    if not all(valid and linked for valid, linked in digest_pairs):
        return ["EVIDENCE_BINDING_MISMATCH", "HANDOFF_REQUIRED"]
    return []
