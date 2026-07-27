"""Route representative user intent to the single Harness skill workflow."""

from __future__ import annotations


# Match Harness-specific intents before generic delivery verbs. For example,
# ``修复 Harness`` is Update, while ``修复订单模块`` is Work.
ROUTE_TERMS = {
    "update": ("update harness", "repair harness", "更新 harness", "修复 harness"),
    "adopt": ("adopt", "existing ci", "接管", "已有 ci"),
    "bootstrap": ("bootstrap", "initialize", "初始化", "建立 harness"),
    "audit": ("audit", "inspect harness", "审查", "检查 harness"),
    "registry": (
        "tool registry",
        "register tool",
        "registry entry",
        "工具登记",
        "工具注册表",
        "登记工具",
        "注册工具",
    ),
    "platform": (
        "platform evidence",
        "github authority",
        "platform gate",
        "平台 evidence",
        "平台门禁",
        "github 权限",
    ),
    "publish": ("publish", "release", "deploy", "发布", "部署"),
    "merge": ("merge", "merge ready", "合并", "合入"),
    "verify": ("verify", "validate", "test", "验证", "测试"),
    "work": ("implement", "modify", "fix", "work", "修改", "实现", "修复"),
}


def route_intent(text: str) -> str:
    normalized = text.casefold()
    for route, terms in ROUTE_TERMS.items():
        if any(term in normalized for term in terms):
            return route
    return "unknown"
