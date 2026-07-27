"""Normalize legacy discovery output into source-backed governance facts."""

from __future__ import annotations

import re
from typing import Any

from .artifacts import GOVERNANCE_SCHEMA_VERSION, attach_digest


_SUBDOMAINS = (
    "agent-runtime",
    "engineering-runtime",
    "poc",
    "source-code",
    "test-code",
    "other-tools",
)


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "root"


def _fact(
    fact_id: str,
    fact_type: str,
    binding_state: str,
    source_refs: list[str],
    value: dict[str, Any],
) -> dict[str, Any]:
    return {
        "fact_id": fact_id,
        "fact_type": fact_type,
        "binding_state": binding_state,
        "source_refs": sorted(set(source_refs)),
        "value": value,
    }


def extract_source_facts(
    discovery: dict[str, Any],
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    """Create deterministic SourceFacts without inferring authorization."""

    facts: list[dict[str, Any]] = [
        _fact(
            f"governance:subdomain:{subdomain}",
            "governance-source",
            "declared",
            [f"harness://specification/1.0.0/subdomains/{subdomain}"],
            {
                "kind": "subdomain-specification",
                "subdomain": subdomain,
                "version": GOVERNANCE_SCHEMA_VERSION,
            },
        )
        for subdomain in _SUBDOMAINS
    ]
    for unit in sorted(discovery.get("project_units", []), key=lambda item: item["id"]):
        manifest = str(unit["manifest"])
        facts.append(
            _fact(
                f"manifest:{_slug(unit['id'])}",
                "manifest",
                "declared",
                [manifest],
                {
                    "unit_id": unit["id"],
                    "runtime": unit["type"],
                    "root": unit["root"],
                },
            )
        )
        for command in sorted(
            unit.get("commands", []),
            key=lambda item: (item["category"], item["name"], item["source"]),
        ):
            action_id = f"{command['category']}:{_slug(unit['id'])}:{_slug(command['name'])}"
            facts.append(
                _fact(
                    f"binding:{action_id}",
                    "action-binding",
                    "bound",
                    [command["source"]],
                    {
                        "action_id": action_id,
                        "semantics": command["category"],
                        "argv": list(command["argv"]),
                        "cwd": unit["root"],
                        "environment": {},
                        **(
                            {"required_reports": list(command["required_reports"])}
                            if command.get("required_reports")
                            else {}
                        ),
                    },
                )
            )

    for workflow in sorted(
        discovery.get("workflows", []), key=lambda item: item["path"]
    ):
        for job in sorted(workflow.get("jobs", []), key=lambda item: item["id"]):
            action_id = (
                f"{job['category']}:github:"
                f"{_slug(workflow['path'])}:{_slug(job['id'])}"
            )
            facts.append(
                _fact(
                    f"binding:{action_id}",
                    "action-binding",
                    "declared",
                    [job["source"]],
                    {
                        "action_id": action_id,
                        "semantics": job["category"],
                        "adapter": "github-actions",
                        "workflow": workflow["path"],
                        "job": job["id"],
                        "cwd": ".",
                    },
                )
            )

    agents = discovery.get("agents", {})
    snapshot_paths = {
        item.get("path")
        for item in snapshot.get("files", [])
        if isinstance(item, dict)
    }
    if agents.get("exists") and agents.get("path", "AGENTS.md") in snapshot_paths:
        facts.append(
            _fact(
                "governance:agents-entry",
                "governance-source",
                "declared",
                [str(agents.get("path", "AGENTS.md"))],
                {"kind": "agents-entry"},
            )
        )

    for index, gap in enumerate(
        sorted(
            discovery.get("gaps", []),
            key=lambda item: (item.get("code", ""), item.get("source", "")),
        )
    ):
        source = str(gap.get("source", "."))
        raw_code = str(gap.get("code", "GOVERNANCE_COVERAGE_INCOMPLETE"))
        code = {
            "ACTION_CLASSIFICATION_UNRESOLVED": "TOOL_ACTION_UNCLASSIFIED",
            "TOOL_NOT_REGISTERED": "TOOL_ACTION_UNCLASSIFIED",
            "PLAN_STALE": "GOVERNANCE_PROJECTION_STALE",
        }.get(raw_code, raw_code)
        reason = str(gap.get("reason", "unresolved repository fact"))
        empty_repository = (
            raw_code == "CONFIG_INVALID"
            and "no supported project manifest" in reason
        )
        facts.append(
            _fact(
                f"gap:{_slug(str(gap.get('code', 'unknown')))}:{index}",
                "governance-gap",
                "detected",
                [source],
                {
                    "blocker_code": code,
                    "reason": reason,
                    "blocking": False if empty_repository else bool(gap.get("blocks_plan", True)),
                },
            )
        )

    document = {
        "artifact_type": "source-facts",
        "schema_version": GOVERNANCE_SCHEMA_VERSION,
        "snapshot_digest": snapshot["snapshot_digest"],
        "facts": facts,
    }
    return attach_digest(document, "facts_digest")
