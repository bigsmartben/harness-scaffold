"""Deterministic checks for structured subagent orchestration results."""

from __future__ import annotations

from itertools import product
import re
from typing import Any

from .projection import AUDIENCES, SUBDOMAINS


def expected_projection_lanes() -> tuple[tuple[str, str], ...]:
    return tuple(product(AUDIENCES, SUBDOMAINS))


def validate_projection_results(results: list[dict[str, Any]]) -> list[str]:
    """Require one valid result for every audience/subdomain lane."""

    valid = [
        item
        for item in results
        if item.get("status") in {"completed", "blocked"}
        and isinstance(item.get("candidate_digest"), str)
        and re.fullmatch(r"sha256:[a-f0-9]{64}", item["candidate_digest"])
    ]
    observed = {
        (item.get("audience"), item.get("subdomain"))
        for item in valid
    }
    expected = set(expected_projection_lanes())
    return (
        []
        if observed == expected and len(valid) == len(expected) == len(results)
        else ["AGENT_BINDING_UNAVAILABLE", "GOVERNANCE_COVERAGE_INCOMPLETE", "HANDOFF_REQUIRED"]
    )


def validate_single_writer(assignments: list[dict[str, Any]]) -> list[str]:
    """Reject overlapping writer ownership; read-only lanes never conflict."""

    owners: dict[str, str] = {}
    for assignment in assignments:
        if assignment.get("sandbox_mode") != "workspace-write":
            continue
        owner = str(assignment.get("owner", ""))
        for path in assignment.get("scope", []):
            normalized = str(path).replace("\\", "/").rstrip("/")
            for existing, existing_owner in owners.items():
                overlaps = (
                    normalized == existing
                    or normalized.startswith(f"{existing}/")
                    or existing.startswith(f"{normalized}/")
                )
                if overlaps and owner != existing_owner:
                    return ["GOVERNANCE_SCOPE_UNRESOLVED", "HANDOFF_REQUIRED"]
            owners[normalized] = owner
    return []
