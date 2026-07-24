"""Route representative user intent to the single Harness skill workflow."""

from __future__ import annotations


ROUTE_TERMS = {
    "publish": ("publish", "release", "deploy", "发布", "部署"),
    "merge": ("merge", "merge ready", "合并", "合入"),
    "verify": ("verify", "validate", "test", "验证", "测试"),
    "work": ("implement", "modify", "fix", "work", "修改", "实现", "修复"),
    "audit": ("audit", "inspect harness", "审查", "检查 harness"),
    "update": ("update harness", "repair harness", "更新 harness", "修复 harness"),
    "adopt": ("adopt", "existing ci", "接管", "已有 ci"),
    "bootstrap": ("bootstrap", "initialize", "初始化", "建立 harness"),
}


def route_intent(text: str) -> str:
    normalized = text.casefold()
    for route, terms in ROUTE_TERMS.items():
        if any(term in normalized for term in terms):
            return route
    return "unknown"

