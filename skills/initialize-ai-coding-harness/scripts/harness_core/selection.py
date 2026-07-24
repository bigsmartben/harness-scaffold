"""Select the lowest sufficient validation set from repository facts."""

from __future__ import annotations

from fnmatch import fnmatch
from typing import Any

from .automation import effective_automation


LEVELS = ("inspect", "affected", "contract", "integration", "full")
FULL_FACTS = {
    "harness_or_ci_semantics_changed",
    "build_or_lockfile_wide_change",
    "public_foundation_or_architecture_changed",
    "user_requested_full",
    "merge_policy_requires_full",
}


def _matches(path: str, pattern: str) -> bool:
    normalized = path.replace("\\", "/")
    return fnmatch(normalized, pattern) or (
        pattern.startswith("**/") and fnmatch(normalized, pattern[3:])
    )


def select_validation(
    change_manifest: dict[str, Any],
    actual_diff: list[str],
    impact: dict[str, Any],
    tasks: dict[str, Any],
    facts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a deterministic selection; never silently fall back to full."""

    facts = facts or {}
    declared = {
        str(path).replace("\\", "/")
        for path in change_manifest.get("paths", [])
    }
    actual = {str(path).replace("\\", "/") for path in actual_diff}
    reasons: list[str] = []
    blockers: list[str] = []
    if declared != actual:
        blockers.append("IMPACT_UNRESOLVED")
        reasons.append(
            f"Change Manifest mismatch: declared={sorted(declared)}, actual={sorted(actual)}"
        )

    matched_rules: list[dict[str, Any]] = []
    unmatched: list[str] = []
    for path in sorted(actual):
        matches = [
            rule
            for rule in impact.get("rules", [])
            if any(_matches(path, pattern) for pattern in rule.get("paths", []))
        ]
        if not matches:
            unmatched.append(path)
        matched_rules.extend(matches)
    if unmatched:
        blockers.append("IMPACT_UNRESOLVED")
        reasons.append(f"No impact rule for: {', '.join(unmatched)}")

    levels = [rule["validation_level"] for rule in matched_rules]
    public_contract_paths = facts.get("public_contract_paths", [])
    if any(
        _matches(path, pattern)
        for path in actual
        for pattern in public_contract_paths
    ):
        levels.append("contract")
        reasons.append("Public contract fact requires contract validation")

    requested_full_facts = sorted(
        key for key in FULL_FACTS if facts.get(key) is True
    )
    if "full" in levels and not requested_full_facts:
        blockers.append("IMPACT_UNRESOLVED")
        reasons.append("Full validation rule lacks a DM-004 fact")
        levels = [level for level in levels if level != "full"]
    if requested_full_facts:
        levels.append("full")
        reasons.append(f"DM-004 full fact: {requested_full_facts[0]}")

    level = max(levels, key=LEVELS.index) if levels else "inspect"
    selected_ids = {
        task_ref
        for rule in matched_rules
        for task_ref in rule.get("tasks", [])
    }
    catalog = {
        item["id"]: item
        for item in tasks.get("tasks", [])
        if isinstance(item, dict) and "id" in item
    }
    if level == "full":
        selected_ids.update(
            task_id
            for task_id, task in catalog.items()
            if task.get("supports_scope") != "publish"
            and task.get("category") not in {"merge", "publish", "deploy"}
        )
    missing_tasks = sorted(selected_ids - catalog.keys())
    if missing_tasks:
        blockers.append("IMPACT_UNRESOLVED")
        reasons.append(f"Unknown task references: {', '.join(missing_tasks)}")

    selected = []
    automatic = []
    confirmation_required = []
    for task_id in sorted(selected_ids & catalog.keys()):
        automation = effective_automation(catalog[task_id], level)
        item = {
            "task_id": task_id,
            "reason": f"selected for {level}",
            "automation_level": automation["automation_level"],
            "auto_allowed": automation["auto_allowed"],
            "decision": (
                "automatic"
                if automation["auto_allowed"]
                else "confirmation-required"
            ),
        }
        selected.append(item)
        if automation["auto_allowed"]:
            automatic.append(item)
        else:
            confirmation_required.append(item)
    skipped = [
        {"task_id": task_id, "reason": f"not required for {level}"}
        for task_id in sorted(catalog.keys() - selected_ids)
    ]
    recommendations = change_manifest.get("recommended_tasks", [])
    ignored = sorted(set(recommendations) - selected_ids)
    if ignored:
        reasons.append(f"Agent recommendations not selected: {', '.join(ignored)}")

    if confirmation_required and not blockers:
        blockers.append("HANDOFF_REQUIRED")
        reasons.append(
            "Confirmation required for: "
            + ", ".join(item["task_id"] for item in confirmation_required)
        )

    return {
        "status": (
            "blocked"
            if blockers and set(blockers) != {"HANDOFF_REQUIRED"}
            else "confirmation-required"
            if confirmation_required
            else "selected"
        ),
        "validation_level": level,
        "selected_tasks": selected,
        "automatic_tasks": automatic,
        "confirmation_required_tasks": confirmation_required,
        "skipped_tasks": skipped,
        "reasons": reasons
        or [f"Matched {len(matched_rules)} impact rule(s) at {level}"],
        "blocker_codes": sorted(set(blockers)),
        "manifest_matches_diff": declared == actual,
        "backend_calls": 0,
    }
