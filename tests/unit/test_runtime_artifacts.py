from __future__ import annotations

from pathlib import Path

import pytest

from harness_core import (
    attach_digest,
    canonical_json,
    create_change_manifest,
    create_confirmation_artifact,
    create_evidence_artifact,
    create_platform_evidence_artifact,
    create_selection_artifact,
    create_task_request_artifact,
    create_work_grant,
    validate_binding_chain,
    validate_runtime_artifact,
)


ROOT = Path(__file__).parents[2]
SCHEMAS = (
    ROOT
    / "skills"
    / "initialize-ai-coding-harness"
    / "assets"
    / "schemas"
)


def _runtime_chain() -> dict[str, dict]:
    task = {
        "id": "test:unit",
        "category": "test",
        "automation_level": "routine",
    }
    grant = create_work_grant(
        grant_id="grant:runtime",
        goal="validate canonical runtime artifacts",
        write_scope=["src/**", "tests/**"],
        merge_target="main",
        delivery_target=None,
        risk_level="low",
    )
    manifest = create_change_manifest(
        grant,
        manifest_id="manifest:runtime",
        base_commit="abc123",
        changed_paths=["src/example.py"],
        affected_modules=["example"],
        recommended_tasks=["test:unit"],
    )
    selection = create_selection_artifact(
        manifest,
        ["src/example.py"],
        {
            "status": "selected",
            "validation_level": "affected",
            "selected_tasks": [
                {
                    "task_id": "test:unit",
                    "automation_level": "routine",
                    "decision": "automatic",
                    "reason": "selected for affected",
                }
            ],
            "skipped_tasks": [],
            "reasons": ["matched source impact rule"],
            "blocker_codes": [],
        },
        selection_id="selection:runtime",
    )
    request = create_task_request_artifact(
        task,
        grant,
        manifest,
        selection,
        request_id="request:runtime",
        target="local",
        commit_sha="abc123",
    )
    confirmation = create_confirmation_artifact(
        request, confirmed_at="2026-07-24T00:00:00Z"
    )
    platform = create_platform_evidence_artifact(
        request,
        workflow="routine-contracts.yml",
        run_id="123",
        commit_sha="abc123",
        confirmation_status="confirmed",
        approval_status="not-required",
        required_checks="passed",
        protected_environment=None,
        artifact_digest=None,
        source_ref="github://actions/runs/123",
    )
    evidence = create_evidence_artifact(
        task=task,
        grant=grant,
        manifest=manifest,
        selection=selection,
        request=request,
        run_id="run-runtime",
        status="passed",
        validation_level="affected",
        duration="0.100s",
        summary="test:unit passed via local",
        primary_error=None,
        artifacts=[],
        full_log=".harness/runs/runtime/full.log",
        blocker_codes=[],
        backend="local",
        confirmation_status="not-required-by-explicit-policy",
        backend_calls=1,
        formal_authority=False,
        platform=None,
    )
    return {
        "grant": grant,
        "manifest": manifest,
        "selection": selection,
        "request": request,
        "confirmation": confirmation,
        "platform": platform,
        "evidence": evidence,
    }


def test_runtime_artifacts_validate_against_0_3_contract() -> None:
    chain = _runtime_chain()

    for artifact in chain.values():
        assert validate_runtime_artifact(artifact, SCHEMAS) == []


def test_runtime_chain_detects_grant_staleness() -> None:
    chain = _runtime_chain()
    chain["grant"]["status"] = "expired"
    chain["grant"] = attach_digest(chain["grant"], "grant_digest")

    assert validate_binding_chain(
        grant=chain["grant"],
        manifest=chain["manifest"],
        selection=chain["selection"],
        request=chain["request"],
        evidence=chain["evidence"],
    ) == ["GRANT_STALE", "HANDOFF_REQUIRED"]


def test_runtime_chain_detects_cross_artifact_mismatch() -> None:
    chain = _runtime_chain()
    chain["manifest"]["base_commit"] = "different"
    chain["manifest"] = attach_digest(chain["manifest"], "manifest_digest")

    assert validate_binding_chain(
        grant=chain["grant"],
        manifest=chain["manifest"],
        selection=chain["selection"],
        request=chain["request"],
        evidence=chain["evidence"],
    ) == ["EVIDENCE_BINDING_MISMATCH", "HANDOFF_REQUIRED"]


def test_evidence_from_a_different_task_request_is_rejected() -> None:
    chain = _runtime_chain()
    alternate_request = create_task_request_artifact(
        {
            "id": "test:unit",
            "category": "test",
            "automation_level": "routine",
        },
        chain["grant"],
        chain["manifest"],
        chain["selection"],
        request_id="request:alternate",
        target="local",
        commit_sha="abc123",
    )

    assert validate_binding_chain(
        grant=chain["grant"],
        manifest=chain["manifest"],
        selection=chain["selection"],
        request=alternate_request,
        evidence=chain["evidence"],
    ) == ["EVIDENCE_BINDING_MISMATCH", "HANDOFF_REQUIRED"]


def test_canonical_json_is_recursive_utf8_and_order_independent() -> None:
    left = {"z": [{"β": 2, "a": 1}], "a": "中文"}
    right = {"a": "中文", "z": [{"a": 1, "β": 2}]}

    assert canonical_json(left) == canonical_json(right)
    assert "\\u4e2d" not in canonical_json(left)


def test_canonical_json_rejects_non_json_nan() -> None:
    with pytest.raises(ValueError):
        canonical_json({"value": float("nan")})
