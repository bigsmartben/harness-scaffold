from __future__ import annotations

from pathlib import Path

import yaml

from harness_core import (
    assess_github_platform,
    attach_digest,
    create_confirmation_artifact,
    normalize_github_platform_evidence,
    platform_evidence_complete,
)

FIXTURES = Path(__file__).parents[1] / "fixtures" / "github-platform"
ROOT = Path(__file__).parents[2]


def _request(
    category: str,
    *,
    target: str,
    artifact_digest: str | None = None,
    environment: str | None = None,
) -> dict:
    return attach_digest(
        {
            "artifact_type": "task-request",
            "schema_version": "1.0.0",
            "request_id": f"request:{category}",
            "task_id": f"{category}:default",
            "action_semantics": category,
            "validation_level": "affected",
            "target": target,
            "commit_sha": "abc123",
            "version": "1.2.3" if category == "publish" else None,
            "artifact_digest": artifact_digest,
            "environment": environment,
            "automation_level": "critical",
            "policy_version": "1.0.0",
            "grant_digest": "sha256:" + "1" * 64,
            "manifest_digest": "sha256:" + "2" * 64,
            "selection_digest": "sha256:" + "3" * 64,
        },
        "request_digest",
    )


def _ready_facts() -> dict:
    return {
        "credentials": {
            "agent_has_delivery_credentials": False,
            "default_token_permissions": "read-only",
            "oidc": "short-lived",
        },
        "branch_protection": {
            "enabled": True,
            "required_checks": ["unit", "integration"],
        },
        "environments": {
            "production": {
                "protected": True,
                "required_reviewers": 1,
            }
        },
        "workflows": [
            {
                "path": ".github/workflows/publish.yml",
                "automation_level": "critical",
                "triggers": ["workflow_dispatch"],
                "platform_gate_enforced": True,
            }
        ],
    }


def test_ready_github_platform_facts_pass_p4_contract() -> None:
    result = assess_github_platform(
        _ready_facts(),
        required_checks=["unit", "integration"],
        protected_environment="production",
    )

    assert result == {"status": "ready", "missing": [], "blocker_codes": []}


def test_captured_platform_fact_fixtures_fail_closed() -> None:
    ready = yaml.safe_load((FIXTURES / "ready.yaml").read_text("utf-8"))
    blocked = yaml.safe_load(
        (FIXTURES / "blocked.yaml").read_text("utf-8")
    )

    assert assess_github_platform(
        ready,
        required_checks=["unit", "integration"],
        protected_environment="production",
    )["status"] == "ready"
    result = assess_github_platform(
        blocked,
        required_checks=["unit", "integration"],
        protected_environment="production",
    )
    assert result["status"] == "blocked"
    assert set(result["blocker_codes"]) == {
        "EVIDENCE_INCOMPLETE",
        "HANDOFF_REQUIRED",
        "PROTECTED_TRIGGER_UNCONTROLLED",
        "PUBLISH_CONFIRMATION_REQUIRED",
    }


def test_agent_visible_delivery_credentials_block_platform_readiness() -> None:
    facts = _ready_facts()
    facts["credentials"]["agent_has_delivery_credentials"] = True

    result = assess_github_platform(facts, required_checks=["unit"])

    assert result["status"] == "blocked"
    assert "HANDOFF_REQUIRED" in result["blocker_codes"]


def test_missing_required_check_blocks_merge_readiness() -> None:
    result = assess_github_platform(
        _ready_facts(), required_checks=["unit", "security"]
    )

    assert result["status"] == "blocked"
    assert result["blocker_codes"] == ["EVIDENCE_INCOMPLETE"]
    assert any("security" in item for item in result["missing"])


def test_uncontrolled_protected_trigger_has_stable_blocker() -> None:
    facts = _ready_facts()
    facts["workflows"][0]["triggers"] = ["push", "workflow_dispatch"]
    facts["workflows"][0]["platform_gate_enforced"] = False

    result = assess_github_platform(facts)

    assert result["blocker_codes"] == ["PROTECTED_TRIGGER_UNCONTROLLED"]


def test_missing_protected_environment_approval_blocks_publish() -> None:
    facts = _ready_facts()
    facts["environments"]["production"]["required_reviewers"] = 0

    result = assess_github_platform(
        facts, protected_environment="production"
    )

    assert result["status"] == "blocked"
    assert result["blocker_codes"] == [
        "HANDOFF_REQUIRED",
        "PUBLISH_CONFIRMATION_REQUIRED",
    ]


def test_formal_publish_evidence_contains_platform_trace() -> None:
    artifact_digest = "sha256:" + "a" * 64
    request = _request(
        "publish",
        target="production",
        artifact_digest=artifact_digest,
        environment="production",
    )
    confirmation = create_confirmation_artifact(
        request, confirmed_at="2026-07-24T11:00:00Z"
    )
    run = {
        "workflow": ".github/workflows/publish.yml",
        "run_id": "12345",
        "commit_sha": "abc123",
        "approval_status": "approved",
        "approver": "maintainer",
        "protected_environment": "production",
        "artifact_digest": artifact_digest,
    }

    evidence = normalize_github_platform_evidence(
        run, request, confirmation
    )

    assert platform_evidence_complete(evidence, "publish", request) is True
    assert evidence["run_id"] == "12345"
    assert evidence["source_ref"].endswith("#12345")


def test_local_or_partial_evidence_cannot_claim_formal_delivery() -> None:
    evidence = {
        "workflow": None,
        "run_id": "local-1",
        "commit_sha": "abc123",
        "request_digest": "sha256:request",
        "confirmation_status": "confirmed",
        "automation_level": "critical",
        "approval_status": "approved",
        "protected_environment": "production",
        "artifact_digest": "sha256:artifact",
    }

    assert platform_evidence_complete(evidence, "publish") is False


def test_merge_evidence_requires_required_checks() -> None:
    request = _request("merge", target="main")
    confirmation = create_confirmation_artifact(
        request, confirmed_at="2026-07-24T11:00:00Z"
    )
    run = {
        "workflow": ".github/workflows/merge.yml",
        "run_id": "12345",
        "commit_sha": "abc123",
        "approval_status": "approved",
        "protected_ref": "main",
    }
    evidence = normalize_github_platform_evidence(run, request, confirmation)

    assert platform_evidence_complete(evidence, "merge", request) is False
    run["required_checks"] = "passed"
    evidence = normalize_github_platform_evidence(run, request, confirmation)
    assert platform_evidence_complete(evidence, "merge", request) is True


def test_publish_platform_environment_must_match_request() -> None:
    artifact_digest = "sha256:" + "a" * 64
    request = _request(
        "publish",
        target="registry",
        artifact_digest=artifact_digest,
        environment="production",
    )
    confirmation = create_confirmation_artifact(
        request, confirmed_at="2026-07-24T11:00:00Z"
    )
    evidence = normalize_github_platform_evidence(
        {
            "workflow": ".github/workflows/publish.yml",
            "run_id": "12345",
            "commit_sha": "abc123",
            "approval_status": "approved",
            "protected_environment": "staging",
            "artifact_digest": artifact_digest,
        },
        request,
        confirmation,
    )

    assert platform_evidence_complete(evidence, "publish", request) is False


def test_repository_workflow_has_controlled_triggers_and_read_only_token() -> None:
    workflow_dir = ROOT / ".github" / "workflows"
    workflows = {
        path.name: path.read_text("utf-8")
        for path in workflow_dir.glob("*.yml")
    }

    assert set(workflows) == {
        "delivery-gate-evidence.yml",
        "harness.yml",
        "routine-contracts.yml",
    }
    for name, workflow in workflows.items():
        assert "workflow_dispatch:" in workflow
        assert "\n  push:" not in workflow
        assert "\n  schedule:" not in workflow
        assert "permissions:\n  contents: read" in workflow
        if name == "routine-contracts.yml":
            assert "\n  pull_request:" in workflow
        else:
            assert "\n  pull_request:" not in workflow
    assert "test \"$CONFIRMED\" = \"true\"" in workflows["harness.yml"]
    assert "ci:full)" in workflows["harness.yml"]
    assert "package:wheel)" in workflows["harness.yml"]
    assert "branch:delete)" in workflows["harness.yml"]
    assert "release:github)" in workflows["harness.yml"]
    assert "Delete exact merged private branch" in workflows["harness.yml"]
    assert "refs/heads/(codex|agent)/" in workflows["harness.yml"]
    assert "git/matching-refs/heads/${branch}" in workflows["harness.yml"]
    assert 'result="already-absent"' in workflows["harness.yml"]
    assert "test:contracts-ci)" not in workflows["harness.yml"]
    assert "actions: read\n      contents: write" in workflows["harness.yml"]
    assert "environment:\n      name: production" in workflows["harness.yml"]
    assert "refs/tags/v1.0.0" in workflows["harness.yml"]
    assert "actions-run:[1-9][0-9]*" in workflows["harness.yml"]
    assert "sha256:[0-9a-f]{64}" in workflows["harness.yml"]
    assert "gh release create" in workflows["harness.yml"]
    assert "gh release upload" in workflows["harness.yml"]
    assert "--draft=false" in workflows["harness.yml"]
    assert "--allow-network" in workflows["harness.yml"]
    assert (
        "uv run pytest tests/unit/test_contracts.py tests/unit/test_platform.py"
        in workflows["routine-contracts.yml"]
    )
    assert (
        "environment:\n      name: production\n      deployment: false"
        in workflows["delivery-gate-evidence.yml"]
    )
    assert (
        "- Side effects: none"
        in workflows["delivery-gate-evidence.yml"]
    )


def test_harness_workflow_exposes_bound_package_and_release_inputs() -> None:
    workflow = yaml.load(
        (ROOT / ".github" / "workflows" / "harness.yml").read_text("utf-8"),
        Loader=yaml.BaseLoader,
    )

    inputs = workflow["on"]["workflow_dispatch"]["inputs"]
    assert set(inputs) == {
        "task_id",
        "request_digest",
        "confirmed",
        "target",
        "source_ref",
        "commit_sha",
        "pull_request_number",
        "merge_method",
        "version",
        "artifact_digest",
        "environment",
    }
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["jobs"]["package-wheel"]["if"] == (
        "inputs.task_id == 'package:wheel'"
    )
    release = workflow["jobs"]["release"]
    assert release["if"] == "inputs.task_id == 'release:github'"
    assert release["environment"] == {"name": "production"}
    assert release["permissions"] == {
        "actions": "read",
        "contents": "write",
    }
