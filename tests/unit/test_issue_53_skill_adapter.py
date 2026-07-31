from __future__ import annotations

from pathlib import Path

import harness_core
from harness_core.artifacts import canonical_digest


SOURCE = {
    "source_type": "user_intent",
    "reference": "user:current-request",
    "digest": "sha256:" + ("2" * 64),
}


def context(repository: Path) -> dict:
    return {
        "repository": str(repository),
        "repository_digest": "sha256:" + ("3" * 64),
        "rules": [
            {
                "rule_id": "contract-tests",
                "revision": 4,
                "status": "enabled",
            },
            {
                "rule_id": "release-notes",
                "revision": 2,
                "status": "disabled",
            },
        ],
        "pending_operations": [],
    }


def test_bare_harness_shows_governance_capabilities_only(tmp_path: Path) -> None:
    result = harness_core.adapt_governance_intent(
        "$harness", context(tmp_path)
    )
    assert result == {
        "status": "capabilities",
        "code": "GOVERNANCE_INTENT_REQUIRED",
        "message": (
            "请指定 load、add、update、delete、disable、enable 或 cancel 治理操作。"
        ),
        "details": {
            "capabilities": [
                "load",
                "add",
                "update",
                "delete",
                "disable",
                "enable",
                "cancel",
            ]
        },
    }


def test_load_produces_only_the_typed_load_request(tmp_path: Path) -> None:
    result = harness_core.adapt_governance_intent(
        "$harness load", context(tmp_path)
    )
    assert result["status"] == "ready"
    envelope = result["envelope"]
    assert envelope["request_kind"] == "load"
    assert envelope["repository"] == {
        "identity": str(tmp_path.resolve()),
        "digest": "sha256:" + ("3" * 64),
    }
    assert envelope["request"] == harness_core.build_load_request(tmp_path)
    assert "candidates" not in envelope
    assert "projection" not in envelope


def test_add_and_update_produce_p1_operation_requests(tmp_path: Path) -> None:
    add_context = {
        **context(tmp_path),
        "operation_id": "op-add-api-contracts",
        "target_rule_id": "api-contracts",
        "domain": "verification",
        "directive": "API changes require contract test evidence.",
        "scope": ["src/api/**", "tests/contract/**"],
        "sources": [SOURCE],
    }
    added = harness_core.adapt_governance_intent(
        "$harness 新增治理规则 api-contracts", add_context
    )
    assert added["status"] == "ready"
    add_request = added["envelope"]["request"]
    assert add_request["operation_type"] == "add"
    assert add_request["base_revision"] == 0
    assert add_request["payload"]["domain"] == "verification"
    assert harness_core.validate_operation_request(add_request) == []

    update_context = {
        **context(tmp_path),
        "operation_id": "op-update-contract-tests",
        "domain": "verification",
        "directive": "Contract tests must be repeatable.",
        "scope": ["tests/contract/**"],
        "sources": [SOURCE],
    }
    updated = harness_core.adapt_governance_intent(
        "$harness 更新 contract-tests 规则", update_context
    )
    update_request = updated["envelope"]["request"]
    assert update_request["operation_type"] == "update"
    assert update_request["target_rule_id"] == "contract-tests"
    assert update_request["base_revision"] == 4
    assert harness_core.validate_operation_request(update_request) == []


def test_delete_disable_enable_are_not_conflated(tmp_path: Path) -> None:
    cases = [
        ("删除 contract-tests 规则", "delete", "contract-tests", 4),
        ("停用 contract-tests 规则", "disable", "contract-tests", 4),
        ("恢复 release-notes 规则", "enable", "release-notes", 2),
    ]
    for text, operation_type, rule_id, revision in cases:
        result = harness_core.adapt_governance_intent(text, context(tmp_path))
        request = result["envelope"]["request"]
        assert request["operation_type"] == operation_type
        assert request["target_rule_id"] == rule_id
        assert request["base_revision"] == revision
        assert request["payload"] is None


def test_cancel_uses_authoritative_pending_operation_not_chat_recency(
    tmp_path: Path,
) -> None:
    value = context(tmp_path)
    value["pending_operations"] = [
        {"operation_id": "op-disable-contract-tests", "status": "pending"}
    ]
    unique = harness_core.adapt_governance_intent(
        "$harness 取消当前操作", value
    )
    assert unique["envelope"]["request_kind"] == "cancel"
    assert unique["envelope"]["request"]["operation_id"] == (
        "op-disable-contract-tests"
    )

    value["pending_operations"].append(
        {"operation_id": "op-delete-release-notes", "status": "pending"}
    )
    ambiguous = harness_core.adapt_governance_intent(
        "$harness 取消当前操作", value
    )
    assert ambiguous["status"] == "clarification_required"
    assert ambiguous["code"] == "CANCEL_TARGET_AMBIGUOUS"

    explicit = harness_core.adapt_governance_intent(
        "$harness cancel op-delete-release-notes", value
    )
    assert explicit["envelope"]["request"]["operation_id"] == (
        "op-delete-release-notes"
    )


def test_ambiguous_target_and_missing_rule_content_require_clarification(
    tmp_path: Path,
) -> None:
    ambiguous = harness_core.adapt_governance_intent(
        "$harness 停用规则", context(tmp_path)
    )
    assert ambiguous["status"] == "clarification_required"
    assert ambiguous["code"] == "TARGET_RULE_AMBIGUOUS"

    missing = {
        **context(tmp_path),
        "target_rule_id": "new-rule",
    }
    incomplete = harness_core.adapt_governance_intent(
        "$harness 新增规则 new-rule", missing
    )
    assert incomplete["status"] == "clarification_required"
    assert incomplete["code"] == "RULE_CONTENT_REQUIRED"


def test_vertical_work_is_stably_out_of_scope_and_writes_nothing(
    tmp_path: Path,
) -> None:
    before = list(tmp_path.iterdir())
    for text in (
        "$harness 实现登录接口",
        "$harness 运行测试",
        "$harness git commit 当前修改",
        "$harness 发布新版本",
        "$harness 部署到生产",
    ):
        result = harness_core.adapt_governance_intent(text, context(tmp_path))
        assert result["status"] == "out_of_scope"
        assert result["code"] == "VERTICAL_WORK_OUT_OF_SCOPE"
        assert "envelope" not in result
    assert list(tmp_path.iterdir()) == before


def test_directive_is_data_even_when_it_mentions_vertical_work(
    tmp_path: Path,
) -> None:
    value = {
        **context(tmp_path),
        "target_rule_id": "run-tests",
        "domain": "verification",
        "directive": "修改公共 API 后运行测试。",
        "scope": ["src/**", "tests/**"],
        "sources": [SOURCE],
    }
    result = harness_core.adapt_governance_intent(
        "$harness 新增规则 run-tests", value
    )
    assert result["status"] == "ready"
    assert result["envelope"]["request"]["payload"]["directive"] == (
        "修改公共 API 后运行测试。"
    )
    assert result["message"].endswith("尚未投影、执行保障或执行垂直业务动作。")


def test_app_and_cli_adapters_are_byte_equivalent(tmp_path: Path) -> None:
    value = context(tmp_path)
    text = "$harness 停用 contract-tests 规则"
    app = harness_core.adapt_app_intent(text, value)
    cli = harness_core.adapt_cli_intent(text, value)

    assert app == cli
    assert app["confirmation_digest"] == canonical_digest(app["envelope"])
    assert app["envelope"]["request"]["operation_type"] == "disable"
    assert app["envelope"]["request"]["target_rule_id"] == "contract-tests"
