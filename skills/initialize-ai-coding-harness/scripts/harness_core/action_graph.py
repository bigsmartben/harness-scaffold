"""Compile source-backed action bindings into a deterministic Action Graph."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .artifacts import GOVERNANCE_SCHEMA_VERSION, attach_digest


_SUBDOMAINS = {
    "ordinary": ["agent-runtime", "other-tools"],
    "lint": ["engineering-runtime", "source-code"],
    "validation": ["engineering-runtime", "test-code"],
    "test": ["engineering-runtime", "test-code"],
    "build": ["engineering-runtime", "source-code"],
    "codegen": ["engineering-runtime", "source-code"],
    "ci": ["engineering-runtime", "test-code"],
    "package": ["engineering-runtime", "source-code"],
    "push": ["engineering-runtime", "source-code"],
    "pull-request": ["engineering-runtime", "source-code"],
    "merge": ["engineering-runtime", "source-code"],
    "publish": ["engineering-runtime"],
    "release": ["engineering-runtime"],
    "deploy": ["engineering-runtime"],
}
_MUTATING = {
    "lint",
    "build",
    "codegen",
    "package",
    "push",
    "pull-request",
    "merge",
    "publish",
    "release",
    "deploy",
}


def build_action_graph(source_facts: dict[str, Any]) -> dict[str, Any]:
    """Build Actions, retaining ambiguous and unclassified states as blockers."""

    binding_facts = [
        fact
        for fact in source_facts.get("facts", [])
        if fact.get("fact_type") == "action-binding"
    ]
    counts = Counter(
        fact.get("value", {}).get("action_id") for fact in binding_facts
    )
    actions: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []

    for fact in sorted(binding_facts, key=lambda item: item["fact_id"]):
        value = fact["value"]
        action_id = value.get("action_id")
        semantics = value.get("semantics")
        if semantics not in _SUBDOMAINS:
            blockers.append(
                {
                    "code": "TOOL_ACTION_UNCLASSIFIED",
                    "action_id": action_id,
                    "source_refs": fact["source_refs"],
                }
            )
            continue
        if counts[action_id] != 1:
            blockers.append(
                {
                    "code": "TOOL_BINDING_AMBIGUOUS",
                    "action_id": action_id,
                    "source_refs": fact["source_refs"],
                }
            )
            continue
        invocation = {
            key: value[key]
            for key in (
                "argv",
                "cwd",
                "environment",
                "adapter",
                "workflow",
                "job",
                "required_reports",
                "expected_files",
            )
            if key in value
        }
        actions.append(
            {
                "action_id": action_id,
                "semantics": semantics,
                "subdomains": _SUBDOMAINS[semantics],
                "source_refs": fact["source_refs"],
                "invocation": invocation,
                "binding_state": fact["binding_state"],
                "mutates_repository": semantics in _MUTATING,
            }
        )

    for fact in source_facts.get("facts", []):
        if (
            fact.get("fact_type") == "governance-gap"
            and fact.get("value", {}).get("blocking")
        ):
            blockers.append(
                {
                    "code": fact["value"]["blocker_code"],
                    "source_refs": fact["source_refs"],
                }
            )

    document = {
        "artifact_type": "action-graph",
        "schema_version": GOVERNANCE_SCHEMA_VERSION,
        "snapshot_digest": source_facts["snapshot_digest"],
        "facts_digest": source_facts["facts_digest"],
        "actions": actions,
        "blockers": sorted(
            blockers,
            key=lambda item: (
                item.get("code", ""),
                item.get("action_id", ""),
                item.get("source_refs", []),
            ),
        ),
    }
    return attach_digest(document, "action_graph_digest")
