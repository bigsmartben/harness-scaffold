"""Compile source-backed actions into the four-domain Action Graph."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .artifacts import SCHEMA_VERSION, attach_digest


_SEMANTICS: dict[str, tuple[str, str, str]] = {
    "ordinary": ("implementation", "local", "T0"),
    "specification": ("specification", "local", "T0"),
    "issue-plan": ("specification", "local", "T0"),
    "lint": ("verification", "local", "T1"),
    "validation": ("verification", "local", "T1"),
    "test": ("verification", "local", "T1"),
    "build": ("implementation", "local", "T2"),
    "codegen": ("implementation", "local", "T2"),
    "package": ("implementation", "local", "T2"),
    "ci": ("verification", "controlled", "T3"),
    "commit": ("delivery", "local", "T0"),
    "issue-write": ("delivery", "controlled", "T0"),
    "push": ("delivery", "controlled", "T3"),
    "pull-request": ("delivery", "controlled", "T3"),
    "merge": ("delivery", "controlled", "T3"),
    "publish": ("delivery", "controlled", "T3"),
    "release": ("delivery", "controlled", "T3"),
    "deploy": ("delivery", "controlled", "T3"),
}

_BUILT_INS = (
    {
        "action_id": "specification:issue-plan",
        "semantics": "issue-plan",
        "source_refs": ["harness://specification/2.0.0/actions/issue-plan"],
        "binding": {"adapter": "harness-core", "operation": "issue-plan"},
    },
    {
        "action_id": "delivery:commit",
        "semantics": "commit",
        "source_refs": ["harness://specification/2.0.0/actions/commit"],
        "binding": {"adapter": "harness-core", "operation": "commit"},
    },
    {
        "action_id": "delivery:remote-issue",
        "semantics": "issue-write",
        "source_refs": ["harness://specification/2.0.0/actions/remote-issue"],
        "binding": {"adapter": "provider", "operation": "issue-write"},
    },
    {
        "action_id": "delivery:push",
        "semantics": "push",
        "source_refs": ["harness://specification/2.0.0/actions/push"],
        "binding": {"adapter": "harness-core", "operation": "push"},
    },
    *(
        {
            "action_id": f"delivery:{semantics}",
            "semantics": semantics,
            "source_refs": [
                f"harness://specification/2.0.0/actions/{semantics}"
            ],
            "binding": {"adapter": "provider", "operation": semantics},
        }
        for semantics in (
            "pull-request",
            "merge",
            "publish",
            "release",
            "deploy",
        )
    ),
)


def _action(
    *,
    action_id: str,
    semantics: str,
    source_refs: list[str],
    binding: dict[str, Any],
) -> dict[str, Any]:
    domain, boundary, validation = _SEMANTICS[semantics]
    controls = ["runtime-context", "action-binding"]
    if boundary == "controlled":
        controls.extend(["platform-control", "evidence"])
    return {
        "action_id": action_id,
        "semantics": semantics,
        "domain": domain,
        "boundary": boundary,
        "source_refs": sorted(set(source_refs)),
        "binding": binding,
        "binding_state": "bound" if binding else "unavailable",
        "validation_floor": validation,
        "cross_controls": controls,
    }


def build_action_graph(source_facts: dict[str, Any]) -> dict[str, Any]:
    binding_facts = [
        fact
        for fact in source_facts.get("facts", [])
        if fact.get("fact_type") == "action-binding"
    ]
    counts = Counter(
        fact.get("value", {}).get("action_id") for fact in binding_facts
    )
    actions = [_action(**item) for item in _BUILT_INS]
    blockers: list[dict[str, Any]] = []

    for fact in sorted(binding_facts, key=lambda item: item["fact_id"]):
        value = fact["value"]
        action_id = str(value.get("action_id") or "")
        semantics = str(value.get("semantics") or "")
        if semantics not in _SEMANTICS:
            blockers.append(
                {
                    "code": "TOOL_ACTION_UNCLASSIFIED",
                    "action_id": action_id or None,
                    "source_refs": fact["source_refs"],
                }
            )
            continue
        if counts[action_id] != 1:
            blockers.append(
                {
                    "code": "TOOL_BINDING_AMBIGUOUS",
                    "action_id": action_id or None,
                    "source_refs": fact["source_refs"],
                }
            )
            continue
        binding = {
            key: value[key]
            for key in (
                "argv",
                "cwd",
                "environment",
                "adapter",
                "workflow",
                "job",
                "required_reports",
            )
            if key in value
        }
        actions.append(
            _action(
                action_id=action_id,
                semantics=semantics,
                source_refs=fact["source_refs"],
                binding=binding,
            )
        )

    for fact in source_facts.get("facts", []):
        if (
            fact.get("fact_type") == "governance-gap"
            and fact.get("value", {}).get("blocking")
        ):
            blockers.append(
                {
                    "code": fact["value"]["blocker_code"],
                    "action_id": None,
                    "source_refs": fact["source_refs"],
                }
            )

    document = {
        "artifact_type": "action-graph",
        "schema_version": SCHEMA_VERSION,
        "snapshot_digest": source_facts["snapshot_digest"],
        "facts_digest": source_facts["facts_digest"],
        "actions": sorted(actions, key=lambda item: item["action_id"]),
        "blockers": sorted(
            blockers,
            key=lambda item: (
                item["code"],
                item.get("action_id") or "",
                item["source_refs"],
            ),
        ),
    }
    return attach_digest(document, "action_graph_digest")
