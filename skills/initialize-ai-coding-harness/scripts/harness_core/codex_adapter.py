"""Codex lifecycle adapter with bootstrap-only and bypass detection."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .agent_contracts import validate_agent_directory
from .artifacts import CORE_VERSION, GOVERNANCE_SCHEMA_VERSION
from .contracts import validate_governance_bundle
from .snapshot import create_repository_snapshot

_REQUIRED_HOOK_EVENTS = {
    "SessionStart",
    "PreToolUse",
    "PermissionRequest",
    "PostToolUse",
    "Stop",
    "SessionEnd",
}


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def load_projection_bundle(repository: Path) -> dict[str, Any] | None:
    root = repository / ".harness" / "governance"
    mapping = {
        "sources": "sources.lock.json",
        "action_graph": "action-graph.json",
        "rules": "rules.json",
        "projection_lock": "projection.lock.json",
    }
    bundle = {key: _load_json(root / filename) for key, filename in mapping.items()}
    return bundle if all(isinstance(value, dict) for value in bundle.values()) else None


def _hook_configuration_is_trusted(repository: Path) -> bool:
    document = _load_json(repository / ".codex" / "hooks.json")
    hooks = document.get("hooks") if document else None
    if not isinstance(hooks, dict) or set(hooks) < _REQUIRED_HOOK_EVENTS:
        return False
    for event in _REQUIRED_HOOK_EVENTS:
        groups = hooks.get(event)
        if not isinstance(groups, list) or not groups:
            return False
        serialized = json.dumps(groups, sort_keys=True)
        if "sdd-harness hook" not in serialized:
            return False
    return True


def runtime_state(repository: Path) -> dict[str, Any]:
    """Return enforced or bootstrap-only without relying on session state."""

    bundle = load_projection_bundle(repository)
    blockers: list[str] = []
    if bundle is None:
        blockers = ["GOVERNANCE_SOURCE_MISSING", "HANDOFF_REQUIRED"]
    else:
        blockers = sorted({issue.code for issue in validate_governance_bundle(bundle)})
        lock = bundle["projection_lock"]
        current = create_repository_snapshot(repository)
        if current["snapshot_digest"] != lock.get("snapshot_digest"):
            blockers.append("GOVERNANCE_PROJECTION_STALE")
        compatibility = repository / ".harness" / "governance" / "compatibility.json"
        handshake = _load_json(compatibility)
        if not handshake or handshake.get("core_version") != CORE_VERSION:
            blockers.append("CONFIG_INVALID")
        if not handshake or handshake.get("schema_version") != GOVERNANCE_SCHEMA_VERSION:
            blockers.append("CONFIG_INVALID")
        for issue in validate_agent_directory(repository / ".codex" / "agents"):
            blockers.extend(issue["blocker_codes"])
        if not _hook_configuration_is_trusted(repository):
            blockers.extend(["AGENT_CONFIGURATION_UNTRUSTED", "HANDOFF_REQUIRED"])
    return {
        "mode": "bootstrap-only" if blockers else "active",
        "blocker_codes": sorted(set(blockers)),
        "projection_id": (
            bundle["projection_lock"].get("projection_id") if bundle else None
        ),
    }


def _tool_name(payload: dict[str, Any]) -> str:
    return str(payload.get("tool_name") or payload.get("tool") or "")


def _tool_input(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("tool_input") or payload.get("tool_args") or {}
    return value if isinstance(value, dict) else {}


def _bypass_action(
    payload: dict[str, Any], graph: dict[str, Any], repository: Path
) -> str | None:
    name = _tool_name(payload)
    arguments = _tool_input(payload)
    if name in {"Bash", "shell_command", "exec_command"}:
        command = str(arguments.get("command") or arguments.get("cmd") or "")
        normalized = re.sub(r"\s+", " ", command).strip()
        for action in graph.get("actions", []):
            argv = action.get("invocation", {}).get("argv")
            if isinstance(argv, list) and normalized.startswith(" ".join(argv)):
                return action["action_id"]
        if re.search(r"\b(push|publish|release|deploy|pytest|npm test|pnpm test)\b", normalized):
            return "unresolved-governed-action"
    if name in {"apply_patch", "Edit", "Write"}:
        candidate_paths = [
            arguments.get(key)
            for key in ("path", "file_path", "target", "filename")
            if arguments.get(key)
        ]
        patch_text = str(arguments.get("patch") or arguments.get("input") or "")
        candidate_paths.extend(
            match.strip()
            for match in re.findall(
                r"^\*\*\* (?:Add|Update|Delete) File: (.+)$",
                patch_text,
                flags=re.MULTILINE,
            )
        )
        for candidate in candidate_paths:
            path = Path(str(candidate))
            resolved = path.resolve() if path.is_absolute() else (repository / path).resolve()
            if not resolved.is_relative_to(repository):
                return "unresolved-governed-action"
        if any(
            (repository / str(candidate)).resolve().is_relative_to(
                repository / ".harness"
            )
            or (repository / str(candidate)).resolve().is_relative_to(
                repository / ".codex"
            )
            for candidate in candidate_paths
        ):
            return "governance-control-plane-write"
        return None
    if name.startswith("mcp__") and not name.startswith("mcp__harness__"):
        for action in graph.get("actions", []):
            if action.get("invocation", {}).get("adapter") == "mcp":
                return action["action_id"]
        if any(key in arguments for key in ("command", "cmd", "argv", "shell")):
            return "unresolved-governed-action"
    return None


def _deny(reason: str) -> dict[str, Any]:
    return {
        "systemMessage": reason,
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        },
    }


def handle_hook(payload: dict[str, Any], repository: Path) -> dict[str, Any]:
    """Handle documented Codex lifecycle events with deterministic outputs."""

    repository = repository.resolve()
    event = str(payload.get("hook_event_name") or payload.get("event") or "")
    state = runtime_state(repository)
    bundle = load_projection_bundle(repository)

    if event == "SessionStart":
        message = (
            f"Harness projection {state['projection_id']} is active."
            if state["mode"] == "active"
            else "Harness is bootstrap-only: " + ", ".join(state["blocker_codes"])
        )
        return {"continue": True, "systemMessage": message}

    if event == "PreToolUse":
        name = _tool_name(payload)
        if state["mode"] == "bootstrap-only":
            read_only = {
                "Read",
                "Glob",
                "Grep",
                "WebSearch",
                "update_plan",
            }
            if name not in read_only and not name.startswith("mcp__harness__"):
                return _deny(
                    "GOVERNANCE_PROJECTION_STALE: bootstrap-only permits projection repair and read-only inspection."
                )
        if bundle:
            action_id = _bypass_action(payload, bundle["action_graph"], repository)
            if action_id:
                return _deny(
                    f"INVOCATION_BYPASS_ATTEMPT: use Harness action_id {action_id}."
                )
        return {}

    if event == "PermissionRequest":
        return {
            "systemMessage": (
                "Harness confirmation is valid only for a projection-bound "
                "change set or delivery package."
            )
        }

    if event == "PostToolUse":
        after = runtime_state(repository)
        if after["mode"] != "active":
            return {
                "continue": False,
                "stopReason": "GOVERNANCE_DRIFT_DETECTED",
                "systemMessage": ", ".join(after["blocker_codes"]),
            }
        return {}

    if event == "Stop":
        evidence_dir = repository / ".harness" / "evidence"
        has_evidence = evidence_dir.is_dir() and any(evidence_dir.glob("*.json"))
        if state["mode"] == "active" and not has_evidence:
            return {
                "continue": False,
                "stopReason": "GOVERNANCE_EVIDENCE_INCOMPLETE",
                "systemMessage": "No accepted Action Evidence closes this governed run.",
            }
        return {"continue": True}

    if event == "SessionEnd":
        return {
            "continue": True,
            "systemMessage": (
                f"Harness session closed for projection {state['projection_id']}."
                if state["mode"] == "active"
                else "Harness session closed in bootstrap-only mode: "
                + ", ".join(state["blocker_codes"])
            ),
        }

    return {}
