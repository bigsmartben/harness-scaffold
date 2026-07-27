"""Deterministic Governance Projection compiler."""

from __future__ import annotations

from itertools import product
from typing import Any

from .artifacts import (
    GOVERNANCE_SCHEMA_VERSION,
    PROJECTION_COMPILER_VERSION,
    attach_digest,
    canonical_digest,
)


AUDIENCES = ("maintainer", "consumer")
SUBDOMAINS = (
    "agent-runtime",
    "engineering-runtime",
    "poc",
    "source-code",
    "test-code",
    "other-tools",
)
RESPONSIBILITIES = ("generate", "enforce")


def _confirmation_policy(semantics: str) -> str:
    if semantics in {"push", "pull-request", "merge", "publish", "release", "deploy"}:
        return "once_per_delivery"
    return "none"


def _enforcement_level(action: dict[str, Any]) -> str:
    return "verified" if action.get("binding_state") == "bound" else "documented"


def compile_governance_projection(
    snapshot: dict[str, Any],
    source_facts: dict[str, Any],
    action_graph: dict[str, Any],
    *,
    maintainer_declarations: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """Compile rules and a lock from explicit facts only."""

    declarations = maintainer_declarations or {}
    declarations_digest = canonical_digest(declarations)
    projection_inputs = {
        "snapshot_digest": snapshot["snapshot_digest"],
        "facts_digest": source_facts["facts_digest"],
        "action_graph_digest": action_graph["action_graph_digest"],
        "governance_schema_version": GOVERNANCE_SCHEMA_VERSION,
        "projection_compiler_version": PROJECTION_COMPILER_VERSION,
        "maintainer_declarations_digest": declarations_digest,
    }
    projection_id = canonical_digest(projection_inputs)

    rules = [
        {
            "rule_id": f"rule:{audience}:{subdomain}:inheritance",
            "action_id": None,
            "audience": audience,
            "subdomains": [subdomain],
            "responsibility": "generate",
            "projection_id": projection_id,
            "source_refs": [
                f"harness://specification/1.0.0/subdomains/{subdomain}"
            ],
            "directive": (
                "MUST inherit source-backed governance for this audience and subdomain."
            ),
            "scope": ["."],
            "inheritance": {"mode": "inherit", "conflict": "fail"},
            "invocation": None,
            "preconditions": ["governance-source-present"],
            "postconditions": ["projection-bound"],
            "enforcement_level": "documented",
            "confirmation_policy": "none",
            "evidence": ["source-facts", "projection-lock"],
            "failure": {
                "blocker_codes": [
                    "GOVERNANCE_SOURCE_MISSING",
                    "HANDOFF_REQUIRED",
                ]
            },
        }
        for audience, subdomain in product(AUDIENCES, SUBDOMAINS)
    ]
    for audience, action in product(AUDIENCES, action_graph.get("actions", [])):
        semantics = action["semantics"]
        policy = _confirmation_policy(semantics)
        rules.append(
            {
                "rule_id": f"rule:{audience}:{action['action_id']}",
                "action_id": action["action_id"],
                "audience": audience,
                "subdomains": action["subdomains"],
                "responsibility": "enforce",
                "projection_id": projection_id,
                "source_refs": action["source_refs"],
                "directive": "MUST use the resolved Harness action binding.",
                "scope": ["."],
                "inheritance": {
                    "mode": "inherit",
                    "conflict": "fail",
                },
                "invocation": action["invocation"],
                "preconditions": ["projection-current", "work-grant-current"],
                "postconditions": ["binding-unchanged", "evidence-complete"],
                "enforcement_level": _enforcement_level(action),
                "confirmation_policy": policy,
                "evidence": ["action-request", "gate-decision", "action-evidence"],
                "failure": {
                    "blocker_codes": [
                        "GOVERNANCE_PRECONDITION_FAILED",
                        "HANDOFF_REQUIRED",
                    ]
                },
            }
        )

    matrix = [
        {"audience": audience, "subdomain": subdomain}
        for audience, subdomain in product(AUDIENCES, SUBDOMAINS)
    ]
    rules_document = attach_digest(
        {
            "artifact_type": "governance-rules",
            "schema_version": GOVERNANCE_SCHEMA_VERSION,
            "projection_id": projection_id,
            "matrix": matrix,
            "rules": sorted(rules, key=lambda item: item["rule_id"]),
        },
        "rules_digest",
    )
    lock = attach_digest(
        {
            "artifact_type": "projection-lock",
            "schema_version": GOVERNANCE_SCHEMA_VERSION,
            "projection_id": projection_id,
            **projection_inputs,
            "rules_digest": rules_document["rules_digest"],
            "blockers": action_graph.get("blockers", []),
            "ready": not action_graph.get("blockers"),
        },
        "projection_lock_digest",
    )
    return {
        "sources": source_facts,
        "action_graph": action_graph,
        "rules": rules_document,
        "projection_lock": lock,
    }
