from __future__ import annotations

import copy
import json
from pathlib import Path

from jsonschema import Draft202012Validator

import harness_core
from harness_core.artifacts import canonical_digest, canonical_json_bytes


ROOT = Path(__file__).parents[2]
SOURCE = {
    "source_type": "user_intent",
    "reference": "request:add-contract-tests",
    "digest": "sha256:" + ("1" * 64),
}


def payload(
    *,
    domain: str = "verification",
    directive: str = "Public API changes require contract test evidence.",
    scope: list[str] | None = None,
) -> dict:
    return {
        "domain": domain,
        "directive": directive,
        "scope": scope or ["src/**", "tests/**"],
        "sources": [copy.deepcopy(SOURCE)],
    }


def register_and_apply(
    state: dict,
    operation_id: str,
    operation_type: str,
    *,
    base_revision: int,
    rule_id: str = "contract-tests",
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
    assert registered["status"] == "pending"
    return harness_core.apply_operation(registered["state"], operation_id)


def added_state() -> dict:
    result = register_and_apply(
        harness_core.empty_governance_state(),
        "op-add-contract-tests",
        "add",
        base_revision=0,
        value=payload(),
    )
    assert result["status"] == "applied"
    return result["state"]


def test_operation_and_rule_schemas_are_closed_and_independently_valid() -> None:
    schema_root = (
        ROOT / "src" / "harness_core" / "resources" / "schemas"
    )
    operation_schema = json.loads(
        (schema_root / "operation.schema.json").read_text(encoding="utf-8")
    )
    rule_schema = json.loads(
        (schema_root / "rule.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(operation_schema)
    Draft202012Validator.check_schema(rule_schema)

    request = harness_core.build_operation_request(
        "op-add-contract-tests",
        "add",
        "contract-tests",
        base_revision=0,
        payload=payload(),
    )
    assert not list(
        Draft202012Validator(operation_schema).iter_errors(request)
    )
    state = added_state()
    assert not list(
        Draft202012Validator(rule_schema).iter_errors(
            state["rules"]["contract-tests"]
        )
    )


def test_runtime_rejects_the_same_invalid_source_digest_as_schema() -> None:
    invalid_payload = payload()
    invalid_payload["sources"][0]["digest"] = "sha256:" + ("z" * 64)
    request = harness_core.build_operation_request(
        "op-add-invalid-source",
        "add",
        "invalid-source",
        base_revision=0,
        payload=invalid_payload,
    )

    diagnostics = harness_core.validate_operation_request(request)
    operation_schema = json.loads(
        (
            ROOT
            / "src/harness_core/resources/schemas/operation.schema.json"
        ).read_text(encoding="utf-8")
    )

    assert diagnostics[0]["code"] == "RULE_SOURCES_INVALID"
    assert list(
        Draft202012Validator(operation_schema).iter_errors(request)
    )


def test_operation_schema_binds_payload_shape_to_operation_type() -> None:
    schema = json.loads(
        (
            ROOT
            / "src/harness_core/resources/schemas/operation.schema.json"
        ).read_text(encoding="utf-8")
    )
    validator = Draft202012Validator(schema)
    invalid_add = harness_core.build_operation_request(
        "op-add-without-payload",
        "add",
        "missing-payload",
        base_revision=0,
    )
    invalid_disable = harness_core.build_operation_request(
        "op-disable-with-payload",
        "disable",
        "contract-tests",
        base_revision=1,
        payload=payload(),
    )

    assert list(validator.iter_errors(invalid_add))
    assert list(validator.iter_errors(invalid_disable))
    assert harness_core.validate_operation_request(invalid_add)
    assert harness_core.validate_operation_request(invalid_disable)


def test_add_creates_one_enabled_rule_with_stable_identity_and_history() -> None:
    state = added_state()
    rule = state["rules"]["contract-tests"]
    assert rule == {
        "rule_id": "contract-tests",
        **payload(),
        "status": "enabled",
        "revision": 1,
        "history": [
            {
                "operation_id": "op-add-contract-tests",
                "operation_type": "add",
                "revision": 1,
                "status": "enabled",
                **payload(),
            }
        ],
    }
    assert state["deleted_rules"] == {}
    assert state["state_revision"] == 1


def test_update_preserves_identity_and_history_and_requires_base_revision() -> None:
    state = added_state()
    updated_payload = payload(
        directive="API changes require repeatable contract tests.",
        scope=["src/api/**", "tests/contract/**"],
    )
    result = register_and_apply(
        state,
        "op-update-contract-tests",
        "update",
        base_revision=1,
        value=updated_payload,
    )
    rule = result["state"]["rules"]["contract-tests"]
    assert rule["rule_id"] == "contract-tests"
    assert rule["revision"] == 2
    assert rule["directive"] == updated_payload["directive"]
    assert [item["revision"] for item in rule["history"]] == [1, 2]

    stale = register_and_apply(
        result["state"],
        "op-stale-update",
        "update",
        base_revision=1,
        value=payload(directive="Stale overwrite."),
    )
    assert stale["status"] == "rejected"
    assert stale["diagnostics"][0]["code"] == "BASE_REVISION_CONFLICT"
    assert stale["state"]["rules"] == result["state"]["rules"]


def test_disable_enable_and_delete_are_machine_distinct() -> None:
    state = added_state()
    disabled = register_and_apply(
        state,
        "op-disable-contract-tests",
        "disable",
        base_revision=1,
    )
    disabled_rule = disabled["state"]["rules"]["contract-tests"]
    assert disabled_rule["status"] == "disabled"
    assert disabled_rule["revision"] == 2
    assert "contract-tests" not in disabled["state"]["deleted_rules"]

    enabled = register_and_apply(
        disabled["state"],
        "op-enable-contract-tests",
        "enable",
        base_revision=2,
    )
    enabled_rule = enabled["state"]["rules"]["contract-tests"]
    assert enabled_rule["status"] == "enabled"
    assert enabled_rule["revision"] == 3
    assert enabled_rule["rule_id"] == disabled_rule["rule_id"]

    deleted = register_and_apply(
        enabled["state"],
        "op-delete-contract-tests",
        "delete",
        base_revision=3,
    )
    assert "contract-tests" not in deleted["state"]["rules"]
    tombstone = deleted["state"]["deleted_rules"]["contract-tests"]
    assert tombstone["deleted_by"] == "op-delete-contract-tests"
    assert tombstone["deleted_revision"] == 4
    assert tombstone["history"][-1]["operation_type"] == "delete"


def test_cancel_changes_only_operation_state_and_preserves_rules_bytewise() -> None:
    state = added_state()
    request = harness_core.build_operation_request(
        "op-disable-contract-tests",
        "disable",
        "contract-tests",
        base_revision=1,
    )
    pending = harness_core.register_operation(state, request)["state"]
    rules_before = canonical_json_bytes(pending["rules"])
    revision_before = pending["state_revision"]
    digest_before = harness_core.governance_rule_digest(pending)

    cancelled = harness_core.cancel_operation(
        pending, "op-disable-contract-tests"
    )

    assert cancelled["status"] == "cancelled"
    assert canonical_json_bytes(cancelled["state"]["rules"]) == rules_before
    assert cancelled["state"]["state_revision"] == revision_before
    assert cancelled["rule_digest"] == digest_before
    assert (
        cancelled["state"]["operations"]["op-disable-contract-tests"]["status"]
        == "cancelled"
    )
    rejected_apply = harness_core.apply_operation(
        cancelled["state"], "op-disable-contract-tests"
    )
    assert rejected_apply["diagnostics"][0]["code"] == "OPERATION_CANCELLED"


def test_pending_operation_survives_serialization_and_can_be_cancelled() -> None:
    state = added_state()
    pending = harness_core.register_operation(
        state,
        harness_core.build_operation_request(
            "op-disable-contract-tests",
            "disable",
            "contract-tests",
            base_revision=1,
        ),
    )["state"]
    restarted = json.loads(json.dumps(pending))

    cancelled = harness_core.cancel_operation(
        restarted, "op-disable-contract-tests"
    )

    assert cancelled["status"] == "cancelled"
    assert cancelled["state"]["rules"] == pending["rules"]


def test_cancel_current_requires_exactly_one_pending_operation() -> None:
    state = added_state()
    none = harness_core.cancel_operation(state)
    assert none["diagnostics"][0] == {
        "code": "CANCEL_TARGET_AMBIGUOUS",
        "message": "cancel current requires exactly one pending operation",
        "expected": 1,
        "actual": 0,
    }
    assert none["state"] is state

    first = harness_core.register_operation(
        state,
        harness_core.build_operation_request(
            "op-disable-contract-tests",
            "disable",
            "contract-tests",
            base_revision=1,
        ),
    )["state"]
    unique = harness_core.cancel_operation(first)
    assert unique["status"] == "cancelled"

    second = harness_core.register_operation(
        first,
        harness_core.build_operation_request(
            "op-update-contract-tests",
            "update",
            "contract-tests",
            base_revision=1,
            payload=payload(directive="Updated."),
        ),
    )["state"]
    ambiguous = harness_core.cancel_operation(second)
    assert ambiguous["diagnostics"][0]["code"] == "CANCEL_TARGET_AMBIGUOUS"
    assert ambiguous["diagnostics"][0]["actual"] == 2
    assert ambiguous["state"] is second


def test_apply_cancel_race_has_exactly_one_terminal_winner() -> None:
    state = added_state()
    request = harness_core.build_operation_request(
        "op-disable-contract-tests",
        "disable",
        "contract-tests",
        base_revision=1,
    )
    pending = harness_core.register_operation(state, request)["state"]

    applied = harness_core.apply_operation(
        copy.deepcopy(pending), "op-disable-contract-tests"
    )
    cancel_after_apply = harness_core.cancel_operation(
        applied["state"], "op-disable-contract-tests"
    )
    assert applied["status"] == "applied"
    assert (
        cancel_after_apply["diagnostics"][0]["code"]
        == "OPERATION_ALREADY_COMMITTED"
    )

    cancelled = harness_core.cancel_operation(
        copy.deepcopy(pending), "op-disable-contract-tests"
    )
    repeated_cancel = harness_core.cancel_operation(
        cancelled["state"], "op-disable-contract-tests"
    )
    apply_after_cancel = harness_core.apply_operation(
        cancelled["state"], "op-disable-contract-tests"
    )
    assert cancelled["status"] == "cancelled"
    assert repeated_cancel["status"] == "cancelled"
    assert repeated_cancel["changed"] is False
    assert repeated_cancel["state"] is cancelled["state"]
    assert apply_after_cancel["diagnostics"][0]["code"] == "OPERATION_CANCELLED"


def test_idempotency_conflicts_and_failures_have_stable_zero_rule_writes() -> None:
    state = added_state()
    request = harness_core.build_operation_request(
        "op-disable-contract-tests",
        "disable",
        "contract-tests",
        base_revision=1,
    )
    first = harness_core.register_operation(state, request)
    repeated = harness_core.register_operation(first["state"], request)
    assert repeated["status"] == "pending"
    assert repeated["changed"] is False

    conflicting_request = copy.deepcopy(request)
    conflicting_request["base_revision"] = 2
    conflict = harness_core.register_operation(
        first["state"], conflicting_request
    )
    assert conflict["diagnostics"][0]["code"] == "OPERATION_ID_CONFLICT"
    assert conflict["state"] is first["state"]

    rules_before = canonical_digest(first["state"]["rules"])
    applied = harness_core.apply_operation(
        first["state"], "op-disable-contract-tests"
    )
    repeated_apply = harness_core.apply_operation(
        applied["state"], "op-disable-contract-tests"
    )
    assert repeated_apply["status"] == "applied"
    assert repeated_apply["changed"] is False
    assert canonical_digest(first["state"]["rules"]) == rules_before


def test_deleted_rule_is_not_disabled_and_identity_cannot_be_reused() -> None:
    state = added_state()
    deleted = register_and_apply(
        state,
        "op-delete-contract-tests",
        "delete",
        base_revision=1,
    )
    readd = register_and_apply(
        deleted["state"],
        "op-readd-contract-tests",
        "add",
        base_revision=0,
        value=payload(),
    )
    assert readd["diagnostics"][0]["code"] == "RULE_ID_RETIRED"
    assert "contract-tests" not in readd["state"]["rules"]
    assert (
        readd["state"]["deleted_rules"]["contract-tests"]["status"]
        == "enabled"
    )
