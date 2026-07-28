"""Skill-first Codex runtime state plus optional Hook defense-in-depth."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .artifacts import CORE_VERSION, SCHEMA_VERSION
from .contracts import validate_governance_bundle, validate_project_config
from .package_resources import iter_resource_files, repo_skill_root
from .policy import load_project_config
from .snapshot import create_repository_snapshot


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
    bundle = {key: _load_json(root / value) for key, value in mapping.items()}
    return bundle if all(isinstance(item, dict) for item in bundle.values()) else None


def _skill_matches(repository: Path) -> bool:
    root = repository / ".agents" / "skills" / "harness"
    for relative, expected in iter_resource_files(repo_skill_root()):
        path = root / relative
        if not path.is_file() or path.read_bytes() != expected:
            return False
    return True


def _hook_status(repository: Path, config: dict[str, Any] | None) -> str:
    expected = (config or {}).get("project_policy", {}).get("hooks") == "enabled"
    document = _load_json(repository / ".codex" / "hooks.json")
    serialized = json.dumps(document, sort_keys=True) if document else ""
    present = "sdd-harness hook" in serialized
    if present:
        return "configured"
    return "missing" if expected else "disabled"


def runtime_state(repository: Path) -> dict[str, Any]:
    root = repository.resolve()
    blockers: set[str] = set()
    config = load_project_config(root)
    config_path = root / ".harness" / "harness.yaml"
    if config is None:
        blockers.add("CONFIG_INVALID")
        if config_path.is_file():
            blockers.update(
                issue.code
                for issue in validate_project_config(config_path)
            )
    bundle = load_projection_bundle(root)
    if bundle is None:
        blockers.add("GOVERNANCE_SOURCE_MISSING")
    else:
        blockers.update(
            issue.code for issue in validate_governance_bundle(bundle)
        )
        current = create_repository_snapshot(root)
        if (
            current["snapshot_digest"]
            != bundle["projection_lock"].get("snapshot_digest")
        ):
            blockers.add("GOVERNANCE_PROJECTION_STALE")

    compatibility = _load_json(
        root / ".harness" / "governance" / "compatibility.json"
    )
    if (
        not compatibility
        or compatibility.get("core_version") != CORE_VERSION
        or compatibility.get("schema_version") != SCHEMA_VERSION
        or compatibility.get("skill_version") != SCHEMA_VERSION
    ):
        blockers.add("HARNESS_RUNTIME_INCOMPATIBLE")
    if not _skill_matches(root):
        blockers.add("HARNESS_RUNTIME_INCOMPATIBLE")

    projection_id = (
        bundle["projection_lock"].get("projection_id") if bundle else None
    )
    return {
        "status": "active" if not blockers else "blocked",
        "mode": "active" if not blockers else "bootstrap-only",
        "core_version": CORE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "projection_id": projection_id,
        "hook_defense": _hook_status(root, config),
        "blocker_codes": sorted(blockers),
        "summary": (
            "Harness is ready for repository work."
            if not blockers
            else "Harness needs repair before governed work."
        ),
    }


def _tool_name(payload: dict[str, Any]) -> str:
    return str(payload.get("tool_name") or payload.get("tool") or "")


def _tool_input(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("tool_input") or payload.get("tool_args") or {}
    return value if isinstance(value, dict) else {}


def _raw_bypass(payload: dict[str, Any], repository: Path) -> str | None:
    name = _tool_name(payload)
    arguments = _tool_input(payload)
    if name in {"Bash", "shell_command", "exec_command"}:
        command = str(arguments.get("command") or arguments.get("cmd") or "")
        if re.search(
            r"\b(git\s+(?:commit|push|merge)|pytest|npm\s+(?:test|publish)|"
            r"pnpm\s+test|release|deploy)\b",
            command,
            flags=re.IGNORECASE,
        ):
            return "use the source-backed Harness action instead of a raw command"
    if name in {"apply_patch", "Edit", "Write"}:
        values = [
            arguments.get(key)
            for key in ("path", "file_path", "target", "filename")
            if arguments.get(key)
        ]
        patch = str(arguments.get("patch") or arguments.get("input") or "")
        values.extend(
            match.strip()
            for match in re.findall(
                r"^\*\*\* (?:Add|Update|Delete) File: (.+)$",
                patch,
                flags=re.MULTILINE,
            )
        )
        for value in values:
            path = Path(str(value))
            target = path.resolve() if path.is_absolute() else (
                repository / path
            ).resolve()
            if not target.is_relative_to(repository):
                return "write target escapes the repository"
            if target.is_relative_to(repository / ".harness" / "governance"):
                return "governance artifacts require a plan-bound publisher"
    return None


def _deny(reason: str) -> dict[str, Any]:
    message = f"INVOCATION_BYPASS_ATTEMPT: {reason}."
    return {
        "systemMessage": message,
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": message,
        },
    }


def handle_hook(payload: dict[str, Any], repository: Path) -> dict[str, Any]:
    root = repository.resolve()
    event = str(payload.get("hook_event_name") or payload.get("event") or "")
    state = runtime_state(root)
    if event == "SessionStart":
        return {
            "continue": True,
            "systemMessage": state["summary"],
        }
    if event == "PreToolUse":
        reason = _raw_bypass(payload, root)
        return _deny(reason) if reason else {"continue": True}
    if event in {
        "PermissionRequest",
        "PostToolUse",
        "Stop",
        "SessionEnd",
    }:
        return {"continue": True}
    return {"continue": True}
