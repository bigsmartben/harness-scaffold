"""Deterministically compile the sixteen Harness SDD governance cells."""

from __future__ import annotations

from itertools import product
from typing import Any

from .artifacts import (
    PROJECTION_COMPILER_VERSION,
    SCHEMA_VERSION,
    attach_digest,
    canonical_digest,
)
from .contracts import AUDIENCES, DOMAINS, RESPONSIBILITIES


COVERAGE_STATUSES = (
    "missing",
    "documented",
    "verified",
    "enforced",
    "not_applicable",
)
COVERAGE_DISPLAY_ALIASES = {
    "missing": "C0",
    "documented": "C1",
    "verified": "C2",
    "enforced": "C3",
    "not_applicable": "C4",
}


def _coverage_cell(
    audience: str,
    responsibility: str,
    domain: str,
    action_graph: dict[str, Any],
) -> dict[str, Any]:
    domain_actions = [
        action
        for action in action_graph.get("actions", [])
        if action["domain"] == domain
    ]
    action_ids = [action["action_id"] for action in domain_actions]
    source_refs = {
        f"harness://specification/2.0.0/domains/{domain}",
        *(
            source
            for action in domain_actions
            for source in action["source_refs"]
        ),
    }
    if responsibility == "generate":
        status = "verified"
        directive = (
            f"Generate {domain} governance only from the bound snapshot, policy, and sources."
        )
        preconditions = ["snapshot-bound", "sources-present"]
        postconditions = ["coverage-record-valid", "projection-bound"]
        evidence = ["source-facts", "projection-lock"]
        bindings: list[str] = []
    else:
        status = "enforced" if domain == "delivery" else "verified"
        directive = (
            f"Enforce {domain} actions through exact scope, binding, decision, and evidence."
        )
        preconditions = [
            "projection-current",
            "scope-current",
            "project-policy-current",
        ]
        if domain == "delivery":
            preconditions.extend(["exact-action-decision", "branch-policy-satisfied"])
        postconditions = ["binding-unchanged", "minimum-validation-complete"]
        if domain == "delivery":
            postconditions.append("platform-evidence-complete")
        evidence = ["workspace-snapshot", "action-result"]
        bindings = action_ids

    return {
        "cell_id": f"{audience}.{responsibility}.{domain}",
        "audience": audience,
        "responsibility": responsibility,
        "domain": domain,
        "source_refs": sorted(source_refs),
        "directive": directive,
        "scope": ["."],
        "action_bindings": sorted(bindings),
        "preconditions": preconditions,
        "postconditions": postconditions,
        "evidence": evidence,
        "failure": {
            "blocker_codes": [
                "GOVERNANCE_COVERAGE_INCOMPLETE",
                "HANDOFF_REQUIRED",
            ]
        },
        "coverage_status": status,
        "not_applicable_reason": None,
    }


def compile_governance_projection(
    snapshot: dict[str, Any],
    source_facts: dict[str, Any],
    action_graph: dict[str, Any],
    *,
    project_policy: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    policy = project_policy or {}
    policy_digest = canonical_digest(policy)
    inputs = {
        "snapshot_digest": snapshot["snapshot_digest"],
        "facts_digest": source_facts["facts_digest"],
        "action_graph_digest": action_graph["action_graph_digest"],
        "policy_digest": policy_digest,
        "governance_schema_version": SCHEMA_VERSION,
        "projection_compiler_version": PROJECTION_COMPILER_VERSION,
    }
    projection_id = canonical_digest(inputs)
    cells = [
        _coverage_cell(audience, responsibility, domain, action_graph)
        for audience, responsibility, domain in product(
            AUDIENCES, RESPONSIBILITIES, DOMAINS
        )
    ]
    rules = attach_digest(
        {
            "artifact_type": "governance-rules",
            "schema_version": SCHEMA_VERSION,
            "projection_id": projection_id,
            "cells": sorted(cells, key=lambda item: item["cell_id"]),
        },
        "rules_digest",
    )
    blockers = sorted(
        {item["code"] for item in action_graph.get("blockers", [])}
    )
    lock = attach_digest(
        {
            "artifact_type": "projection-lock",
            "schema_version": SCHEMA_VERSION,
            "projection_id": projection_id,
            **inputs,
            "rules_digest": rules["rules_digest"],
            "blockers": blockers,
            "ready": not blockers,
        },
        "projection_lock_digest",
    )
    return {
        "sources": source_facts,
        "action_graph": action_graph,
        "rules": rules,
        "projection_lock": lock,
    }
