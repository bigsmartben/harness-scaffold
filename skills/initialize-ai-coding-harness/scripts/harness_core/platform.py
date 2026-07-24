"""Validate GitHub CI/CD authority and normalize platform Evidence."""

from __future__ import annotations

from typing import Any


PROTECTED_CATEGORIES = {"push", "merge", "publish", "release", "deploy"}
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
    confirmation: dict[str, Any],
) -> dict[str, Any]:
    """Return the platform fields required for formal delivery Evidence."""

    return {
        "platform": "github-actions",
        "workflow": run.get("workflow"),
        "run_id": run.get("run_id"),
        "commit_sha": run.get("commit_sha"),
        "request_digest": confirmation.get("request_digest"),
        "confirmation_status": (
            "confirmed" if confirmation.get("confirmed") is True else "missing"
        ),
        "approval_status": run.get("approval_status"),
        "approver": run.get("approver"),
        "required_checks": run.get("required_checks"),
        "protected_environment": run.get("protected_environment"),
        "artifact_digest": run.get("artifact_digest"),
        "target": request.get("target") or request.get("context", {}).get("target"),
        "automation_level": request.get("automation_level"),
    }


def platform_evidence_complete(
    evidence: dict[str, Any], category: str
) -> bool:
    required = {
        "platform",
        "workflow",
        "run_id",
        "commit_sha",
        "request_digest",
        "confirmation_status",
        "automation_level",
    }
    if not all(evidence.get(field) for field in required):
        return False
    if evidence.get("confirmation_status") != "confirmed":
        return False
    if category in PROTECTED_CATEGORIES and evidence.get("approval_status") != "approved":
        return False
    if category == "merge" and evidence.get("required_checks") != "passed":
        return False
    if category in {"publish", "release", "deploy"}:
        return bool(
            evidence.get("protected_environment")
            and evidence.get("artifact_digest")
        )
    return True
