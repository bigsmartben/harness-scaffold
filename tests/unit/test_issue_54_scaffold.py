from __future__ import annotations

import copy
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

import harness_core


SOURCE = {
    "source_type": "repository_fact",
    "reference": "snapshot:test-fixture",
    "digest": "sha256:" + ("4" * 64),
}


def payload(domain: str) -> dict:
    return {
        "domain": domain,
        "directive": f"Require typed {domain} evidence.",
        "scope": [f"{domain}/**"],
        "sources": [copy.deepcopy(SOURCE)],
    }


def add_rule(
    state: dict,
    domain: str,
    *,
    operation_id: str | None = None,
) -> dict:
    rule_id = f"{domain}-evidence"
    operation_id = operation_id or f"op-add-{domain}-evidence"
    request = harness_core.build_operation_request(
        operation_id,
        "add",
        rule_id,
        base_revision=0,
        payload=payload(domain),
    )
    registered = harness_core.register_operation(state, request)
    return harness_core.apply_operation(
        registered["state"], operation_id
    )["state"]


def four_domain_state() -> dict:
    state = harness_core.empty_governance_state()
    for domain in harness_core.DOMAINS:
        state = add_rule(state, domain)
    return state


def operation(
    state: dict,
    operation_id: str,
    operation_type: str,
    rule_id: str,
    *,
    base_revision: int,
    value: dict | None = None,
) -> dict:
    request = harness_core.build_operation_request(
        operation_id,
        operation_type,
        rule_id,
        base_revision=base_revision,
        payload=value,
    )
    registered = harness_core.register_operation(state, request)
    return harness_core.apply_operation(
        registered["state"], operation_id
    )["state"]


def event(domain: str, *, target: str | None = None) -> dict:
    return {
        "event_id": f"event-{domain}",
        "domain": domain,
        "target": target or f"{domain}/change.json",
        "event_type": "governed_change",
    }


def evidence(
    obligation: dict,
    *,
    status: str = "passed",
    producer_type: str = "worker",
) -> dict:
    return {
        "evidence_id": f"evidence-{obligation['domain']}",
        "enforcement_id": obligation["enforcement_id"],
        "projection_id": obligation["projection_id"],
        "rule_id": obligation["rule_id"],
        "revision": obligation["revision"],
        "evidence_type": obligation["evidence_type"],
        "producer": {
            "type": producer_type,
            "identity": f"{obligation['domain']}-worker",
        },
        "artifact_digest": "sha256:" + ("5" * 64),
        "postcondition": {
            "status": status,
            "observed": {"repeatable": status == "passed"},
        },
    }


def test_enforcement_evidence_schema_matches_runtime_contract() -> None:
    schema = json.loads(
        (
            Path(__file__).parents[2]
            / "src/harness_core/resources/schemas/enforcement.schema.json"
        ).read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)
    state = add_rule(
        harness_core.empty_governance_state(), "specification"
    )
    obligation = harness_core.create_enforcement_obligations(
        state, event("specification")
    )["obligations"][0]
    assert not list(
        Draft202012Validator(schema).iter_errors(evidence(obligation))
    )


def test_state_and_projection_match_their_standalone_schemas() -> None:
    schema_root = (
        Path(__file__).parents[2]
        / "src/harness_core/resources/schemas"
    )
    state_schema = json.loads(
        (schema_root / "state.schema.json").read_text(encoding="utf-8")
    )
    projection_schema = json.loads(
        (schema_root / "projection.schema.json").read_text(encoding="utf-8")
    )
    state = four_domain_state()
    projection = harness_core.compile_governance_projection(state)

    assert not list(
        Draft202012Validator(state_schema).iter_errors(state)
    )
    assert not list(
        Draft202012Validator(projection_schema).iter_errors(projection)
    )


def test_projection_binds_enabled_rules_to_two_consumer_views() -> None:
    state = four_domain_state()
    first = harness_core.compile_governance_projection(state)
    second = harness_core.compile_governance_projection(copy.deepcopy(state))

    assert first == second
    assert len(first["fixed_cells"]) == 16
    assert len(first["rules"]) == 4
    assert first["disabled_rules"] == []
    for rule in first["rules"]:
        assert rule["cell_bindings"] == [
            f"consumer.generate.{rule['domain']}",
            f"consumer.enforce.{rule['domain']}",
        ]
        assert rule["status"] == "enabled"


def test_disable_restore_delete_and_cancel_have_distinct_projection_effects() -> None:
    state = add_rule(
        harness_core.empty_governance_state(), "verification"
    )
    baseline = harness_core.compile_governance_projection(state)
    disabled = operation(
        state,
        "op-disable-verification-evidence",
        "disable",
        "verification-evidence",
        base_revision=1,
    )
    disabled_projection = harness_core.compile_governance_projection(
        disabled
    )
    assert disabled_projection["rules"] == []
    assert disabled_projection["disabled_rules"][0]["revision"] == 2

    restored = operation(
        disabled,
        "op-enable-verification-evidence",
        "enable",
        "verification-evidence",
        base_revision=2,
    )
    restored_projection = harness_core.compile_governance_projection(
        restored
    )
    assert restored_projection["rules"][0]["revision"] == 3

    pending_request = harness_core.build_operation_request(
        "op-delete-verification-evidence",
        "delete",
        "verification-evidence",
        base_revision=3,
    )
    pending = harness_core.register_operation(restored, pending_request)[
        "state"
    ]
    cancelled = harness_core.cancel_operation(
        pending, "op-delete-verification-evidence"
    )["state"]
    assert harness_core.compile_governance_projection(cancelled) == (
        restored_projection
    )

    deleted = operation(
        restored,
        "op-delete-verification-evidence",
        "delete",
        "verification-evidence",
        base_revision=3,
    )
    deleted_projection = harness_core.compile_governance_projection(deleted)
    assert deleted_projection["rules"] == []
    assert deleted_projection["disabled_rules"] == []
    assert baseline["projection_id"] != disabled_projection["projection_id"]
    assert len({baseline["projection_id"],
                disabled_projection["projection_id"],
                restored_projection["projection_id"],
                deleted_projection["projection_id"]}) == 4


@pytest.mark.parametrize("domain", harness_core.DOMAINS)
def test_each_domain_has_satisfied_blocked_and_not_applicable(
    domain: str,
) -> None:
    state = four_domain_state()
    created = harness_core.create_enforcement_obligations(
        state, event(domain)
    )
    assert created["decision"] == "applicable"
    assert len(created["obligations"]) == 1
    obligation = created["obligations"][0]
    assert obligation["evidence_type"] == harness_core.EVIDENCE_TYPES[domain]

    satisfied = harness_core.evaluate_enforcement(
        state, obligation, evidence(obligation)
    )
    blocked = harness_core.evaluate_enforcement(
        state, obligation, evidence(obligation, status="failed")
    )
    missing = harness_core.evaluate_enforcement(state, obligation, None)
    not_applicable = harness_core.create_enforcement_obligations(
        state, event(domain, target="unmatched/file.txt")
    )

    assert satisfied["decision"] == "satisfied"
    assert blocked["decision"] == "blocked"
    assert blocked["diagnostics"][0]["code"] == (
        "GOVERNANCE_POSTCONDITION_FAILED"
    )
    assert missing["diagnostics"][0]["code"] == "EVIDENCE_MISSING"
    assert not_applicable["decision"] == "not_applicable"
    assert not_applicable["obligations"] == []

    disabled = operation(
        state,
        f"op-disable-{domain}-evidence",
        "disable",
        f"{domain}-evidence",
        base_revision=1,
    )
    assert harness_core.create_enforcement_obligations(
        disabled, event(domain)
    )["decision"] == "not_applicable"
    assert harness_core.evaluate_enforcement(
        disabled, obligation, evidence(obligation)
    )["decision"] == "stale"


def test_obligations_and_evidence_decisions_are_exactly_recomputable() -> None:
    state = four_domain_state()
    governed_event = event("verification")
    first_created = harness_core.create_enforcement_obligations(
        state, governed_event
    )
    second_created = harness_core.create_enforcement_obligations(
        copy.deepcopy(state), copy.deepcopy(governed_event)
    )
    obligation = first_created["obligations"][0]
    proof = evidence(obligation)

    assert first_created == second_created
    assert harness_core.evaluate_enforcement(
        state, obligation, proof
    ) == harness_core.evaluate_enforcement(
        copy.deepcopy(state),
        copy.deepcopy(obligation),
        copy.deepcopy(proof),
    )


def test_disabled_deleted_and_updated_rules_make_old_enforcement_stale() -> None:
    state = add_rule(
        harness_core.empty_governance_state(), "implementation"
    )
    obligation = harness_core.create_enforcement_obligations(
        state, event("implementation")
    )["obligations"][0]

    disabled = operation(
        state,
        "op-disable-implementation-evidence",
        "disable",
        "implementation-evidence",
        base_revision=1,
    )
    assert harness_core.create_enforcement_obligations(
        disabled, event("implementation")
    )["decision"] == "not_applicable"
    assert harness_core.evaluate_enforcement(
        disabled, obligation, evidence(obligation)
    )["decision"] == "stale"

    deleted = operation(
        state,
        "op-delete-implementation-evidence",
        "delete",
        "implementation-evidence",
        base_revision=1,
    )
    assert harness_core.evaluate_enforcement(
        deleted, obligation, evidence(obligation)
    )["decision"] == "stale"

    updated = operation(
        state,
        "op-update-implementation-evidence",
        "update",
        "implementation-evidence",
        base_revision=1,
        value={
            **payload("implementation"),
            "directive": "Require new implementation evidence.",
        },
    )
    assert harness_core.evaluate_enforcement(
        updated, obligation, evidence(obligation)
    )["decision"] == "stale"


@pytest.mark.parametrize(
    "producer_type",
    ["agent_summary", "memory", "transcript", "chat"],
)
def test_agent_memory_and_transcript_are_rejected_as_evidence(
    producer_type: str,
) -> None:
    state = add_rule(
        harness_core.empty_governance_state(), "verification"
    )
    obligation = harness_core.create_enforcement_obligations(
        state, event("verification")
    )["obligations"][0]

    result = harness_core.evaluate_enforcement(
        state,
        obligation,
        evidence(obligation, producer_type=producer_type),
    )

    assert result["decision"] == "blocked"
    assert result["diagnostics"][0]["code"] == (
        "EVIDENCE_PRODUCER_FORBIDDEN"
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("evidence_id", ""),
        ("artifact_digest", "sha256:" + ("z" * 64)),
        ("producer", {"type": "worker", "identity": ""}),
    ],
)
def test_malformed_typed_evidence_fails_closed(
    field: str,
    value: object,
) -> None:
    state = add_rule(
        harness_core.empty_governance_state(), "verification"
    )
    obligation = harness_core.create_enforcement_obligations(
        state, event("verification")
    )["obligations"][0]
    malformed = evidence(obligation)
    malformed[field] = value

    result = harness_core.evaluate_enforcement(
        state, obligation, malformed
    )

    assert result["decision"] == "blocked"
    assert result["diagnostics"][0]["code"] == "EVIDENCE_INVALID"


def test_load_result_ingestion_is_atomic_and_idempotent(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src/main.py").write_text("VALUE = 1\n", encoding="utf-8")
    loaded = harness_core.load_repository(
        harness_core.build_load_request(tmp_path)
    )
    repository = harness_core.GovernanceRepository(tmp_path)

    first = repository.ingest(loaded)
    state_bytes = repository.path.read_bytes()
    second = harness_core.GovernanceRepository(tmp_path).ingest(loaded)

    assert first["status"] == "loaded"
    assert len(first["state"]["rules"]) == 4
    assert second["changed"] is False
    assert repository.path.read_bytes() == state_bytes

    blocked_load = {**loaded, "status": "blocked", "diagnostics": [
        {"code": "RULE_CANDIDATE_CONFLICT", "message": "conflict"}
    ]}
    blocked = repository.ingest(blocked_load)
    assert blocked["status"] == "blocked"
    assert repository.path.read_bytes() == state_bytes


def test_repository_persists_pending_operations_across_restart(
    tmp_path: Path,
) -> None:
    repository = harness_core.GovernanceRepository(tmp_path)
    request = harness_core.build_operation_request(
        "op-add-delivery-evidence",
        "add",
        "delivery-evidence",
        base_revision=0,
        payload=payload("delivery"),
    )
    repository.register(request)

    restarted = harness_core.GovernanceRepository(tmp_path)
    assert restarted.read()["operations"][
        "op-add-delivery-evidence"
    ]["status"] == "pending"
    cancelled = restarted.cancel("op-add-delivery-evidence")
    assert cancelled["status"] == "cancelled"
    assert cancelled["state"]["rules"] == {}


def test_repository_apply_cancel_race_has_one_authoritative_terminal_state(
    tmp_path: Path,
) -> None:
    repository = harness_core.GovernanceRepository(tmp_path)
    request = harness_core.build_operation_request(
        "op-add-delivery-evidence",
        "add",
        "delivery-evidence",
        base_revision=0,
        payload=payload("delivery"),
    )
    repository.register(request)

    with ThreadPoolExecutor(max_workers=2) as executor:
        apply_future = executor.submit(
            harness_core.GovernanceRepository(tmp_path).apply,
            "op-add-delivery-evidence",
        )
        cancel_future = executor.submit(
            harness_core.GovernanceRepository(tmp_path).cancel,
            "op-add-delivery-evidence",
        )
        results = [apply_future.result(), cancel_future.result()]

    final = harness_core.GovernanceRepository(tmp_path).read()
    terminal = final["operations"]["op-add-delivery-evidence"]["status"]
    assert terminal in {"applied", "cancelled"}
    assert sum(result["status"] == terminal for result in results) >= 1
    if terminal == "applied":
        assert "delivery-evidence" in final["rules"]
        assert any(
            result["diagnostics"]
            and result["diagnostics"][0]["code"]
            == "OPERATION_ALREADY_COMMITTED"
            for result in results
        )
    else:
        assert final["rules"] == {}
        assert any(
            result["diagnostics"]
            and result["diagnostics"][0]["code"] == "OPERATION_CANCELLED"
            for result in results
        )
