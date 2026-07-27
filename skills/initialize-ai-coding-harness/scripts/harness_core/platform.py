"""Validate GitHub CI/CD authority and normalize platform Evidence."""

from __future__ import annotations

from typing import Any

from .artifacts import SCHEMA_VERSION, attach_digest, digest_matches
from .contracts import runtime_artifact_is_valid


PROTECTED_CATEGORIES = {
    "push",
    "pull-request",
    "merge",
    "publish",
    "release",
    "deploy",
}
EXTERNAL_TRIGGERS = {"push", "pull_request", "schedule", "repository_dispatch"}


def assess_github_platform(
    facts: dict[str, Any],
    *,
    required_checks: list[str] | None = None,
    protected_environment: str | None = None,
) -> dict[str, Any]:
    """Assess P4 facts without treating configuration presence as proof."""

    missing: list[str] = []
    blockers: set[str] = set()
    credentials = facts.get("credentials", {})
    if credentials.get("agent_has_delivery_credentials") is not False:
        missing.append("delivery credentials must be isolated from Agent / Skill")
        blockers.add("HANDOFF_REQUIRED")
    if credentials.get("default_token_permissions") != "read-only":
        missing.append("default workflow token permissions must be read-only")
        blockers.add("HANDOFF_REQUIRED")

    protection = facts.get("branch_protection", {})
    configured_checks = set(protection.get("required_checks", []))
    requested_checks = set(required_checks or [])
    if not protection.get("enabled"):
        missing.append("branch protection")
        blockers.add("EVIDENCE_INCOMPLETE")
    if not requested_checks.issubset(configured_checks):
        missing.append(
            "required checks: " + ", ".join(sorted(requested_checks - configured_checks))
        )
        blockers.add("EVIDENCE_INCOMPLETE")

    for workflow in facts.get("workflows", []):
        if workflow.get("automation_level") not in {"expensive", "critical"}:
            continue
        uncontrolled = sorted(
            set(workflow.get("triggers", [])) & EXTERNAL_TRIGGERS
        )
        if uncontrolled and not workflow.get("platform_gate_enforced"):
            missing.append(
                f"controlled trigger for {workflow.get('path', 'workflow')}: "
                + ", ".join(uncontrolled)
            )
            blockers.add("PROTECTED_TRIGGER_UNCONTROLLED")

    if protected_environment:
        environment = facts.get("environments", {}).get(protected_environment, {})
        if (
            not environment.get("protected")
            or environment.get("required_reviewers", 0) < 1
        ):
            missing.append(
                f"protected environment approval: {protected_environment}"
            )
            blockers.update(
                {"PUBLISH_CONFIRMATION_REQUIRED", "HANDOFF_REQUIRED"}
            )

    return {
        "status": "blocked" if missing else "ready",
        "missing": missing,
        "blocker_codes": sorted(blockers),
    }


def normalize_github_platform_evidence(
    run: dict[str, Any],
    request: dict[str, Any],
    confirmation: dict[str, Any] | None,
) -> dict[str, Any]:
    """Normalize a polled GitHub run into the 0.3 Platform Evidence contract."""

    confirmation_matches = (
        isinstance(confirmation, dict)
        and runtime_artifact_is_valid(confirmation)
        and confirmation.get("artifact_type") == "confirmation"
        and confirmation.get("schema_version") == SCHEMA_VERSION
        and confirmation.get("confirmation_status") == "confirmed"
        and confirmation.get("request_digest") == request.get("request_digest")
    )
    workflow = run.get("workflow")
    run_id = run.get("run_id")
    evidence = {
        "artifact_type": "platform-evidence",
        "schema_version": SCHEMA_VERSION,
        "platform": "github-actions",
        "workflow": str(workflow or ""),
        "run_id": str(run_id or ""),
        "commit_sha": str(run.get("commit_sha") or ""),
        "request_digest": request.get("request_digest"),
        "confirmation_status": (
            "confirmed"
            if confirmation_matches
            else "not-required"
        ),
        "approval_status": run.get("approval_status", "not-required"),
        "required_checks": run.get("required_checks", "not-applicable"),
        "protected_ref": run.get("protected_ref"),
        "protected_environment": run.get("protected_environment"),
        # Platform Evidence must report the artifact it actually observed.
        # The requested digest is a binding expectation, not proof of delivery.
        "artifact_digest": run.get("artifact_digest"),
        "source_ref": str(
            run.get("source_ref") or f"{workflow or 'missing'}#{run_id or 'missing'}"
        ),
    }
    return attach_digest(evidence, "platform_evidence_digest")


def normalize_git_remote_evidence(
    *,
    remote: str,
    target_ref: str,
    commit_sha: str,
    request: dict[str, Any],
    confirmation: dict[str, Any] | None,
    operation_id: str,
) -> dict[str, Any]:
    """Normalize a successful, exact-ref Git push response as platform Evidence."""

    confirmation_matches = (
        isinstance(confirmation, dict)
        and runtime_artifact_is_valid(confirmation)
        and confirmation.get("artifact_type") == "confirmation"
        and confirmation.get("schema_version") == SCHEMA_VERSION
        and confirmation.get("confirmation_status") == "confirmed"
        and confirmation.get("request_digest") == request.get("request_digest")
    )
    evidence = {
        "artifact_type": "platform-evidence",
        "schema_version": SCHEMA_VERSION,
        "platform": "git-remote",
        "workflow": "git-push",
        "run_id": operation_id,
        "commit_sha": commit_sha,
        "request_digest": request.get("request_digest"),
        "confirmation_status": "confirmed" if confirmation_matches else "not-required",
        "approval_status": "approved" if confirmation_matches else "not-required",
        "required_checks": "not-applicable",
        "protected_ref": target_ref,
        "protected_environment": None,
        "artifact_digest": None,
        "source_ref": f"git+{remote}#{target_ref}",
    }
    return attach_digest(evidence, "platform_evidence_digest")


def platform_evidence_complete(
    evidence: dict[str, Any],
    category: str,
    request: dict[str, Any] | None = None,
) -> bool:
    """Return whether Platform Evidence is complete and belongs to the Request."""

    required_keys = {
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
    required_values = {
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
    if not required_keys.issubset(evidence) or not all(
        evidence.get(field) for field in required_values
    ):
        return False
    if (
        not runtime_artifact_is_valid(evidence)
        or evidence.get("artifact_type") != "platform-evidence"
        or evidence.get("schema_version") != SCHEMA_VERSION
        or evidence.get("platform") not in {"github-actions", "git-remote"}
        or not digest_matches(evidence, "platform_evidence_digest")
    ):
        return False
    if evidence.get("platform") == "git-remote" and category != "push":
        return False
    if request is not None:
        if (
            not runtime_artifact_is_valid(request)
            or request.get("artifact_type") != "task-request"
            or request.get("schema_version") != SCHEMA_VERSION
            or not digest_matches(request, "request_digest")
            or request.get("action_semantics") != category
            or evidence.get("request_digest") != request.get("request_digest")
            or evidence.get("commit_sha") != request.get("commit_sha")
            or (
                request.get("artifact_digest") is not None
                and evidence.get("artifact_digest")
                != request.get("artifact_digest")
            )
        ):
            return False
    if category in PROTECTED_CATEGORIES and evidence.get("approval_status") != "approved":
        return False
    if category in {"push", "pull-request", "merge"}:
        if (
            not request
            or not request.get("target")
            or evidence.get("protected_ref") != request.get("target")
        ):
            return False
        if category == "merge" and evidence.get("required_checks") != "passed":
            return False
    if category in {"publish", "release", "deploy"}:
        return bool(
            request
            and request.get("target")
            and request.get("version")
            and request.get("environment")
            and evidence.get("protected_environment")
            == request.get("environment")
            and evidence.get("artifact_digest")
            == request.get("artifact_digest")
        )
    return True
