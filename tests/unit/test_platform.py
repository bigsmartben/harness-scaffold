from __future__ import annotations

from pathlib import Path

import yaml

from harness_core import (
    assess_github_platform,
    normalize_github_platform_evidence,
    platform_evidence_complete,
)

FIXTURES = Path(__file__).parents[1] / "fixtures" / "github-platform"
ROOT = Path(__file__).parents[2]


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
    request = {
        "task_id": "publish:package",
        "automation_level": "critical",
        "target": "production",
    }
    confirmation = {
        "confirmed": True,
        "request_digest": "sha256:request",
    }
    run = {
        "workflow": ".github/workflows/publish.yml",
        "run_id": "12345",
        "commit_sha": "abc123",
        "approval_status": "approved",
        "approver": "maintainer",
        "protected_environment": "production",
        "artifact_digest": "sha256:artifact",
    }

    evidence = normalize_github_platform_evidence(
        run, request, confirmation
    )

    assert platform_evidence_complete(evidence, "publish") is True
    assert evidence["run_id"] == "12345"
    assert evidence["approver"] == "maintainer"


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
    evidence = {
        "platform": "github-actions",
        "workflow": ".github/workflows/merge.yml",
        "run_id": "12345",
        "commit_sha": "abc123",
        "request_digest": "sha256:request",
        "confirmation_status": "confirmed",
        "automation_level": "critical",
        "approval_status": "approved",
    }

    assert platform_evidence_complete(evidence, "merge") is False
    evidence["required_checks"] = "passed"
    assert platform_evidence_complete(evidence, "merge") is True


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
    assert "test:contracts-ci)" not in workflows["harness.yml"]
    assert (
        "uv run pytest tests/unit/test_contracts.py tests/unit/test_platform.py"
        in workflows["routine-contracts.yml"]
    )
    assert (
        "environment:\n      name: production"
        in workflows["delivery-gate-evidence.yml"]
    )
    assert (
        "- Side effects: none"
        in workflows["delivery-gate-evidence.yml"]
    )
