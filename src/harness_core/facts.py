"""Convert repository discovery into source-backed Harness 2.0 facts."""

from __future__ import annotations

import re
from typing import Any

from .artifacts import SCHEMA_VERSION, attach_digest, canonical_digest


DOMAINS = ("specification", "implementation", "verification", "delivery")


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "root"


def _fact(
    fact_type: str,
    stable_key: str,
    value: dict[str, Any],
    source_refs: list[str],
) -> dict[str, Any]:
    return {
        "fact_id": f"fact:{fact_type}:{_slug(stable_key)}",
        "fact_type": fact_type,
        "value": value,
        "source_refs": sorted(set(source_refs)),
    }


def extract_source_facts(
    discovery: dict[str, Any],
    snapshot: dict[str, Any],
    *,
    project_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    facts: list[dict[str, Any]] = []
    for domain in DOMAINS:
        facts.append(
            _fact(
                "governance-source",
                domain,
                {
                    "domain": domain,
                    "directive": (
                        f"Apply the Harness SDD {domain} contract from source-backed facts."
                    ),
                },
                [f"harness://specification/2.0.0/domains/{domain}"],
            )
        )

    policy = project_policy or {}
    facts.append(
        _fact(
            "project-policy",
            "project",
            {"policy_digest": canonical_digest(policy), "policy": policy},
            [".harness/harness.yaml#project_policy"],
        )
    )

    for unit in discovery.get("project_units", []):
        cwd = str(unit.get("root") or ".")
        for command in unit.get("commands", []):
            action_id = (
                f"{command['category']}:{_slug(str(unit['id']))}:"
                f"{_slug(str(command['name']))}"
            )
            value: dict[str, Any] = {
                "action_id": action_id,
                "semantics": command["category"],
                "argv": [str(item) for item in command.get("argv", [])],
                "cwd": cwd,
                "adapter": "local",
            }
            if command.get("required_reports"):
                value["required_reports"] = command["required_reports"]
            facts.append(
                _fact(
                    "action-binding",
                    action_id,
                    value,
                    [str(command["source"])],
                )
            )

    for workflow in discovery.get("workflows", []):
        for job in workflow.get("jobs", []):
            action_id = f"{job['category']}:workflow:{_slug(job['id'])}"
            facts.append(
                _fact(
                    "action-binding",
                    action_id,
                    {
                        "action_id": action_id,
                        "semantics": job["category"],
                        "adapter": "github-actions",
                        "workflow": workflow["path"],
                        "job": job["id"],
                    },
                    [job["source"]],
                )
            )

    for gap in discovery.get("gaps", []):
        if not gap.get("blocks_plan"):
            continue
        raw_code = str(gap.get("code") or "")
        code = (
            raw_code
            if raw_code in {"CONFIG_INVALID", "TOOL_ACTION_UNCLASSIFIED"}
            else "TOOL_ACTION_UNCLASSIFIED"
        )
        facts.append(
            _fact(
                "governance-gap",
                str(gap.get("source") or code),
                {
                    "blocking": True,
                    "blocker_code": code,
                    "reason": str(gap.get("reason") or code),
                },
                [str(gap.get("source") or ".")],
            )
        )

    document = {
        "artifact_type": "source-facts",
        "schema_version": SCHEMA_VERSION,
        "snapshot_digest": snapshot["snapshot_digest"],
        "facts": sorted(facts, key=lambda item: item["fact_id"]),
    }
    return attach_digest(document, "facts_digest")
