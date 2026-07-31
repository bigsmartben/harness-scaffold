"""Natural-language governance intent adapter for the Harness Skill."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .artifacts import canonical_digest
from .lifecycle import build_operation_request, validate_operation_request
from .load_core import build_load_request
from .model import CONTRACT_VERSION, DOMAINS


_CAPABILITIES = (
    "load",
    "add",
    "update",
    "delete",
    "disable",
    "enable",
    "cancel",
)
_OPERATION_TERMS = {
    "add": ("新增", "添加", "生成规则", "add", "create rule"),
    "update": ("更新", "修改规则", "update"),
    "delete": ("删除", "delete", "remove rule"),
    "disable": ("停用", "禁用", "disable"),
    "enable": ("启用", "恢复", "enable", "restore"),
    "cancel": ("取消", "cancel"),
}
_LOAD_TERMS = ("load", "加载", "接入仓库", "载入仓库")
_VERTICAL_TERMS = (
    "实现",
    "写代码",
    "运行测试",
    "执行测试",
    "git ",
    "提交代码",
    "发布",
    "部署",
    "implement",
    "run test",
    "commit ",
    "release ",
    "deploy ",
)


def _strip_prefix(text: str) -> str:
    return re.sub(r"^\s*\$?harness\b", "", text, flags=re.IGNORECASE).strip()


def _response(
    status: str,
    *,
    code: str,
    message: str,
    envelope: dict[str, Any] | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": status,
        "code": code,
        "message": message,
    }
    if envelope is not None:
        result["envelope"] = envelope
        result["confirmation_digest"] = canonical_digest(envelope)
    if details is not None:
        result["details"] = details
    return result


def _repository_envelope(
    context: dict[str, Any],
    request_kind: str,
    request: dict[str, Any],
) -> dict[str, Any]:
    repository = Path(context["repository"]).resolve()
    return {
        "contract_version": CONTRACT_VERSION,
        "repository": {
            "identity": str(repository),
            "digest": context["repository_digest"],
        },
        "request_kind": request_kind,
        "request": request,
    }


def _operation_type(intent: str) -> str | None:
    lowered = intent.lower()
    if lowered.startswith(("取消", "cancel")):
        return "cancel"
    matches = [
        operation_type
        for operation_type, terms in _OPERATION_TERMS.items()
        if any(term in lowered for term in terms)
    ]
    return matches[0] if len(matches) == 1 else None


def _mentioned_rule_ids(
    intent: str,
    rules: list[dict[str, Any]],
) -> list[str]:
    return sorted(
        rule["rule_id"]
        for rule in rules
        if re.search(
            rf"(?<![a-z0-9-]){re.escape(rule['rule_id'])}(?![a-z0-9-])",
            intent,
            flags=re.IGNORECASE,
        )
    )


def _target_rule(
    intent: str,
    context: dict[str, Any],
) -> tuple[str | None, dict[str, Any] | None]:
    rules = context.get("rules", [])
    explicit = context.get("target_rule_id")
    if explicit is not None:
        matches = [rule for rule in rules if rule["rule_id"] == explicit]
    else:
        mentioned = _mentioned_rule_ids(intent, rules)
        matches = [
            rule for rule in rules if rule["rule_id"] in mentioned
        ]
    if len(matches) != 1:
        return None, _response(
            "clarification_required",
            code="TARGET_RULE_AMBIGUOUS",
            message="治理操作必须明确指向一条当前规则。",
            details={
                "matches": [rule["rule_id"] for rule in matches],
            },
        )
    return matches[0]["rule_id"], matches[0]


def _cancel_envelope(
    intent: str,
    context: dict[str, Any],
) -> dict[str, Any]:
    explicit = re.search(
        r"(?<![a-z0-9-])(op-[a-z0-9]+(?:-[a-z0-9]+)*)(?![a-z0-9-])",
        intent,
        flags=re.IGNORECASE,
    )
    pending = [
        operation
        for operation in context.get("pending_operations", [])
        if operation.get("status") == "pending"
    ]
    if explicit is not None:
        operation_id = explicit.group(1).lower()
    elif len(pending) == 1:
        operation_id = pending[0]["operation_id"]
    else:
        return _response(
            "clarification_required",
            code="CANCEL_TARGET_AMBIGUOUS",
            message="取消操作必须明确 operation_id，或当前恰好只有一个 pending 操作。",
            details={"pending_count": len(pending)},
        )
    request = {
        "contract_version": CONTRACT_VERSION,
        "operation_id": operation_id,
    }
    return _response(
        "ready",
        code="CANCEL_REQUEST_READY",
        message="已形成类型化取消请求；尚未提交任何规则变更。",
        envelope=_repository_envelope(context, "cancel", request),
    )


def adapt_governance_intent(
    text: str,
    context: dict[str, Any],
) -> dict[str, Any]:
    """Translate user governance language into an upstream typed request."""

    intent = _strip_prefix(text)
    if not intent:
        return _response(
            "capabilities",
            code="GOVERNANCE_INTENT_REQUIRED",
            message="请指定 load、add、update、delete、disable、enable 或 cancel 治理操作。",
            details={"capabilities": list(_CAPABILITIES)},
        )
    if "repository" not in context or "repository_digest" not in context:
        return _response(
            "clarification_required",
            code="REPOSITORY_IDENTITY_REQUIRED",
            message="治理请求必须绑定目标仓库身份与摘要。",
        )

    lowered = intent.lower()
    is_rule_intent = "规则" in intent or "rule" in lowered
    if any(term in lowered for term in _LOAD_TERMS):
        request = build_load_request(Path(context["repository"]))
        return _response(
            "ready",
            code="LOAD_REQUEST_READY",
            message="已形成 LoadRequest；仓库发现与校准由 Load Core 执行。",
            envelope=_repository_envelope(context, "load", request),
        )

    operation_type = _operation_type(intent)
    if operation_type == "cancel":
        return _cancel_envelope(intent, context)
    if operation_type is None and any(
        term in lowered for term in _VERTICAL_TERMS
    ):
        return _response(
            "out_of_scope",
            code="VERTICAL_WORK_OUT_OF_SCOPE",
            message="Harness 只处理治理规则；实现、测试、Git、发布和部署由垂直业务执行者完成。",
        )
    if operation_type is None or not is_rule_intent:
        return _response(
            "clarification_required",
            code="GOVERNANCE_OPERATION_AMBIGUOUS",
            message="无法唯一识别治理规则操作，请明确操作类型和目标规则。",
        )

    if operation_type == "add":
        rule_id = context.get("target_rule_id")
        base_revision = 0
        if not isinstance(rule_id, str):
            return _response(
                "clarification_required",
                code="TARGET_RULE_ID_REQUIRED",
                message="新增规则必须提供稳定 rule_id。",
            )
    else:
        rule_id, rule = _target_rule(intent, context)
        if rule is None or rule_id is None:
            assert isinstance(rule, dict)
            return rule
        base_revision = rule["revision"]

    payload = None
    if operation_type in {"add", "update"}:
        domain = context.get("domain")
        directive = context.get("directive")
        scope = context.get("scope")
        sources = context.get("sources")
        if (
            domain not in DOMAINS
            or not isinstance(directive, str)
            or not directive.strip()
            or not isinstance(scope, list)
            or not scope
            or not isinstance(sources, list)
            or not sources
        ):
            return _response(
                "clarification_required",
                code="RULE_CONTENT_REQUIRED",
                message="add/update 必须明确 domain、directive、scope 和 sources。",
            )
        payload = {
            "domain": domain,
            "directive": directive,
            "scope": scope,
            "sources": sources,
        }
    operation_id = context.get("operation_id")
    if not isinstance(operation_id, str):
        suffix = canonical_digest(
            {
                "repository": str(Path(context["repository"]).resolve()),
                "intent": intent,
                "operation_type": operation_type,
                "target_rule_id": rule_id,
            }
        ).split(":", maxsplit=1)[1][:16]
        operation_id = f"op-{suffix}"
    request = build_operation_request(
        operation_id,
        operation_type,
        rule_id,
        base_revision=base_revision,
        payload=payload,
    )
    issues = validate_operation_request(request)
    if issues:
        return _response(
            "clarification_required",
            code=issues[0]["code"],
            message=issues[0]["message"],
            details=issues[0],
        )
    return _response(
        "ready",
        code="OPERATION_REQUEST_READY",
        message="已形成类型化治理 Operation；尚未投影、执行保障或执行垂直业务动作。",
        envelope=_repository_envelope(context, "operation", request),
    )


def adapt_app_intent(text: str, context: dict[str, Any]) -> dict[str, Any]:
    """Codex App adapter using the shared intent contract."""

    return adapt_governance_intent(text, context)


def adapt_cli_intent(text: str, context: dict[str, Any]) -> dict[str, Any]:
    """CLI adapter using the same intent contract without independent state."""

    return adapt_governance_intent(text, context)
