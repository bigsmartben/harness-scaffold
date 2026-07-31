from __future__ import annotations

import copy
import json
from pathlib import Path

import yaml

import harness_core
from harness_core.cli import main as cli_main


SOURCE = {
    "source_type": "user_intent",
    "reference": "user:e2e-rule",
    "digest": "sha256:" + ("7" * 64),
}


def test_new_repository_load_rule_operation_and_enforce_e2e(
    tmp_path: Path,
) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src/api.py").write_text(
        "def api(): return 1\n", encoding="utf-8"
    )
    loaded = harness_core.load_and_bootstrap(tmp_path)
    assert loaded["status"] == "loaded"

    state = harness_core.GovernanceRepository(tmp_path).read()
    adapter_context = {
        "repository": str(tmp_path),
        "repository_digest": loaded["snapshot_digest"],
        "rules": list(state["rules"].values()),
        "pending_operations": [],
        "operation_id": "op-add-contract-tests",
        "target_rule_id": "contract-tests",
        "domain": "verification",
        "directive": "API changes require contract test evidence.",
        "scope": ["src/**"],
        "sources": [SOURCE],
    }
    adapted = harness_core.adapt_app_intent(
        "$harness 新增规则 contract-tests", adapter_context
    )
    request = adapted["envelope"]["request"]
    repository = harness_core.GovernanceRepository(tmp_path)
    repository.register(request)
    applied = repository.apply(request["operation_id"])
    assert applied["status"] == "applied"

    event = {
        "event_id": "event-api-change",
        "domain": "verification",
        "target": "src/api.py",
        "event_type": "governed_change",
    }
    obligation = harness_core.create_enforcement_obligations(
        applied["state"], event
    )["obligations"][0]
    evidence = {
        "evidence_id": "evidence-contract-tests",
        "enforcement_id": obligation["enforcement_id"],
        "projection_id": obligation["projection_id"],
        "rule_id": obligation["rule_id"],
        "revision": obligation["revision"],
        "evidence_type": obligation["evidence_type"],
        "producer": {
            "type": "test_worker",
            "identity": "contract-test-worker",
        },
        "artifact_digest": "sha256:" + ("8" * 64),
        "postcondition": {
            "status": "passed",
            "observed": {"tests": 12, "failures": 0},
        },
    }
    decision = harness_core.evaluate_enforcement(
        applied["state"], obligation, evidence
    )
    assert decision["decision"] == "satisfied"


def test_old_repository_conflict_is_zero_write_e2e(tmp_path: Path) -> None:
    config = tmp_path / ".harness/harness.yaml"
    config.parent.mkdir()
    config.write_text(
        yaml.safe_dump(
            {
                "schema_version": "3.0.1",
                "rule_instances": {
                    "specification": [
                        {
                            "rule_id": "repo-specification-baseline",
                            "directive": "Conflicting rule.",
                            "scope": ["other/**"],
                        }
                    ],
                    "implementation": [],
                    "verification": [],
                    "delivery": [],
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    before = {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }

    result = harness_core.load_and_bootstrap(tmp_path)

    after = {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    assert result["status"] == "blocked"
    assert result["diagnostics"][0]["code"] == "RULE_CANDIDATE_CONFLICT"
    assert after == before


def test_full_lifecycle_matrix_is_observable_in_projection_e2e(
    tmp_path: Path,
) -> None:
    harness_core.load_and_bootstrap(tmp_path)
    repository = harness_core.GovernanceRepository(tmp_path)
    add = harness_core.build_operation_request(
        "op-add-api-rule",
        "add",
        "api-rule",
        base_revision=0,
        payload={
            "domain": "implementation",
            "directive": "Use explicit API types.",
            "scope": ["src/**"],
            "sources": [SOURCE],
        },
    )
    repository.register(add)
    added = repository.apply("op-add-api-rule")
    assert any(
        rule["rule_id"] == "api-rule"
        for rule in added["projection"]["rules"]
    )

    disable = harness_core.build_operation_request(
        "op-disable-api-rule",
        "disable",
        "api-rule",
        base_revision=1,
    )
    repository.register(disable)
    disabled = repository.apply("op-disable-api-rule")
    assert not any(
        rule["rule_id"] == "api-rule"
        for rule in disabled["projection"]["rules"]
    )
    assert any(
        rule["rule_id"] == "api-rule"
        for rule in disabled["projection"]["disabled_rules"]
    )

    enable = harness_core.build_operation_request(
        "op-enable-api-rule",
        "enable",
        "api-rule",
        base_revision=2,
    )
    repository.register(enable)
    enabled = repository.apply("op-enable-api-rule")
    assert next(
        rule
        for rule in enabled["projection"]["rules"]
        if rule["rule_id"] == "api-rule"
    )["revision"] == 3

    delete = harness_core.build_operation_request(
        "op-delete-api-rule",
        "delete",
        "api-rule",
        base_revision=3,
    )
    pending = repository.register(delete)
    rules_before_cancel = json.dumps(
        pending["state"]["rules"], sort_keys=True
    )
    cancelled = repository.cancel("op-delete-api-rule")
    assert json.dumps(
        cancelled["state"]["rules"], sort_keys=True
    ) == rules_before_cancel

    replacement = copy.deepcopy(delete)
    replacement["operation_id"] = "op-delete-api-rule-final"
    repository.register(replacement)
    deleted = repository.apply("op-delete-api-rule-final")
    assert "api-rule" not in deleted["state"]["rules"]
    assert "api-rule" in deleted["state"]["deleted_rules"]


def test_app_operation_can_be_applied_by_cli(
    tmp_path: Path,
    capsys,
) -> None:
    loaded = harness_core.load_and_bootstrap(tmp_path)
    state = harness_core.GovernanceRepository(tmp_path).read()
    adapted = harness_core.adapt_app_intent(
        "$harness 新增规则 app-contract",
        {
            "repository": str(tmp_path),
            "repository_digest": loaded["snapshot_digest"],
            "rules": list(state["rules"].values()),
            "pending_operations": [],
            "operation_id": "op-add-app-contract",
            "target_rule_id": "app-contract",
            "domain": "verification",
            "directive": "App-created rules require CLI-compatible evidence.",
            "scope": ["tests/**"],
            "sources": [SOURCE],
        },
    )

    exit_code = cli_main(
        [
            "operate",
            str(tmp_path),
            "--request-json",
            json.dumps(adapted["envelope"]["request"]),
            "--json",
        ]
    )
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output["status"] == "applied"
    assert "app-contract" in output["state"]["rules"]


def test_cli_pending_operation_can_be_cancelled_by_app_adapter(
    tmp_path: Path,
) -> None:
    loaded = harness_core.load_and_bootstrap(tmp_path)
    repository = harness_core.GovernanceRepository(tmp_path)
    request = harness_core.build_operation_request(
        "op-add-cli-contract",
        "add",
        "cli-contract",
        base_revision=0,
        payload={
            "domain": "delivery",
            "directive": "CLI-created changes require release evidence.",
            "scope": ["dist/**"],
            "sources": [SOURCE],
        },
    )
    pending = repository.register(request)
    state = pending["state"]
    adapted = harness_core.adapt_app_intent(
        "$harness 取消当前操作",
        {
            "repository": str(tmp_path),
            "repository_digest": loaded["snapshot_digest"],
            "rules": list(state["rules"].values()),
            "pending_operations": [
                {"operation_id": operation_id, **operation}
                for operation_id, operation in state["operations"].items()
            ],
        },
    )

    cancelled = repository.cancel(
        adapted["envelope"]["request"]["operation_id"]
    )

    assert cancelled["status"] == "cancelled"
    assert "cli-contract" not in cancelled["state"]["rules"]


def test_app_pending_operation_can_be_cancelled_by_cli(
    tmp_path: Path,
    capsys,
) -> None:
    loaded = harness_core.load_and_bootstrap(tmp_path)
    state = harness_core.GovernanceRepository(tmp_path).read()
    adapted = harness_core.adapt_app_intent(
        "$harness 新增规则 app-pending",
        {
            "repository": str(tmp_path),
            "repository_digest": loaded["snapshot_digest"],
            "rules": list(state["rules"].values()),
            "pending_operations": [],
            "operation_id": "op-add-app-pending",
            "target_rule_id": "app-pending",
            "domain": "specification",
            "directive": "App pending changes require acceptance evidence.",
            "scope": ["docs/**"],
            "sources": [SOURCE],
        },
    )
    request = adapted["envelope"]["request"]
    harness_core.GovernanceRepository(tmp_path).register(request)

    exit_code = cli_main(
        [
            "cancel",
            str(tmp_path),
            request["operation_id"],
            "--json",
        ]
    )
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output["status"] == "cancelled"
    assert "app-pending" not in output["state"]["rules"]
