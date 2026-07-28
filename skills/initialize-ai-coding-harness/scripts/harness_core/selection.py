"""Select the lowest sufficient, capability-checked validation set."""

from __future__ import annotations

from fnmatch import fnmatch
from typing import Any

from .artifacts import SCHEMA_VERSION, attach_digest, canonical_digest, digest_matches
from .automation import effective_automation
from .contracts import runtime_artifact_is_valid


LEVELS = ("inspect", "affected", "contract", "integration", "full")
DELIVERY_CATEGORIES = {"push", "merge", "publish", "release", "deploy"}
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


def _capable(task: dict[str, Any], level: str) -> bool:
    scope = task.get("supports_scope")
    return scope in LEVELS and LEVELS.index(scope) >= LEVELS.index(level)


def select_validation(
    change_manifest: dict[str, Any],
    actual_diff: list[str],
    impact: dict[str, Any],
    tasks: dict[str, Any],
    facts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a digest-bound Selection; never silently fall back to full."""

    facts = facts or {}
    declared = {
        str(path).replace("\\", "/")
        for path in change_manifest.get("changed_paths", [])
    }
    actual = {str(path).replace("\\", "/") for path in actual_diff}
    reasons: list[str] = []
    blockers: set[str] = set()
    if not runtime_artifact_is_valid(change_manifest):
        blockers.update({"EVIDENCE_BINDING_MISMATCH", "HANDOFF_REQUIRED"})
        reasons.append("Change Manifest does not satisfy the 1.0 runtime schema")
    if not digest_matches(change_manifest, "manifest_digest"):
        blockers.update({"EVIDENCE_BINDING_MISMATCH", "HANDOFF_REQUIRED"})
        reasons.append("Change Manifest digest is invalid")
    if declared != actual:
        blockers.add("IMPACT_UNRESOLVED")
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
        blockers.add("IMPACT_UNRESOLVED")
        reasons.append(f"No impact rule for: {', '.join(unmatched)}")

    levels = [rule["validation_level"] for rule in matched_rules]
    public_contract_paths = facts.get("public_contract_paths", [])
    if change_manifest.get("public_contract_changed") is True or any(
        _matches(path, pattern)
        for path in actual
        for pattern in public_contract_paths
    ):
        levels.append("contract")
        reasons.append("Public contract change requires contract validation")

    requested_full_facts = sorted(
        key for key in FULL_FACTS if facts.get(key) is True
    )
    if "full" in levels and not requested_full_facts:
        blockers.add("IMPACT_UNRESOLVED")
        reasons.append("Full validation rule lacks a DM-004 fact")
        levels = [level for level in levels if level != "full"]
    if requested_full_facts:
        levels.append("full")
        reasons.append(f"DM-004 full fact: {requested_full_facts[0]}")
    level = max(levels, key=LEVELS.index) if levels else "inspect"

    catalog = {
        item["id"]: item
        for item in tasks.get("tasks", [])
        if isinstance(item, dict) and "id" in item
    }
    selected_ids = {
        task_ref
        for rule in matched_rules
        for task_ref in rule.get("tasks", [])
    }
    missing_tasks = sorted(selected_ids - catalog.keys())
    if missing_tasks:
        blockers.add("IMPACT_UNRESOLVED")
        reasons.append(f"Unknown task references: {', '.join(missing_tasks)}")

    if level == "full":
        selected_ids.update(
            task_id
            for task_id, task in catalog.items()
            if task.get("category") not in DELIVERY_CATEGORIES
            and task.get("supports_scope") != "publish"
        )
    elif level in {"affected", "contract", "integration"}:
        current_capable = any(
            _capable(catalog[task_id], level)
            for task_id in selected_ids & catalog.keys()
            if catalog[task_id].get("category") not in DELIVERY_CATEGORIES
        )
        if not current_capable:
            candidates = [
                task
                for task in catalog.values()
                if task.get("category") not in DELIVERY_CATEGORIES
                and _capable(task, level)
            ]
            if candidates:
                minimum_scope = min(
                    LEVELS.index(task["supports_scope"]) for task in candidates
                )
                selected_ids.update(
                    task["id"]
                    for task in candidates
                    if LEVELS.index(task["supports_scope"]) == minimum_scope
                )

    if level != "inspect" and not any(
        _capable(catalog[task_id], level)
        for task_id in selected_ids & catalog.keys()
        if catalog[task_id].get("category") not in DELIVERY_CATEGORIES
    ):
        blockers.add("IMPACT_UNRESOLVED")
        reasons.append(f"No registered Task can cover {level} validation")

    selected: list[dict[str, str]] = []
    confirmation_ids: list[str] = []
    for task_id in sorted(selected_ids & catalog.keys()):
        task = catalog[task_id]
        if level == "full" and task.get("category") in DELIVERY_CATEGORIES:
            continue
        automation = effective_automation(task, level)
        decision = (
            "automatic" if automation["auto_allowed"] else "confirmation-required"
        )
        selected.append(
            {
                "task_id": task_id,
                "automation_level": automation["automation_level"],
                "decision": decision,
                "reason": f"selected for {level}",
            }
        )
        if decision == "confirmation-required":
            confirmation_ids.append(task_id)

    skipped = [
        {"task_id": task_id, "reason": f"not required for {level}"}
        for task_id in sorted(catalog.keys() - {item["task_id"] for item in selected})
    ]
    ignored = sorted(
        set(change_manifest.get("recommended_tasks", []))
        - {item["task_id"] for item in selected}
    )
    if ignored:
        reasons.append(f"Agent recommendations not selected: {', '.join(ignored)}")
    if confirmation_ids and not blockers:
        blockers.add("HANDOFF_REQUIRED")
        reasons.append("Confirmation required for: " + ", ".join(confirmation_ids))

    result = {
        "artifact_type": "selection",
        "schema_version": SCHEMA_VERSION,
        "selection_id": "selection:default",
        "manifest_digest": change_manifest.get(
            "manifest_digest", canonical_digest({"missing": "manifest"})
        ),
        "diff_digest": canonical_digest(sorted(actual)),
        "status": (
            "blocked"
            if blockers - {"HANDOFF_REQUIRED"}
            else "confirmation-required"
            if confirmation_ids
            else "selected"
        ),
        "validation_level": level,
        "selected_tasks": selected,
        "skipped_tasks": skipped,
        "reasons": reasons
        or [f"Matched {len(matched_rules)} impact rule(s) at {level}"],
        "blocker_codes": sorted(blockers),
    }
    return attach_digest(result, "selection_digest")
