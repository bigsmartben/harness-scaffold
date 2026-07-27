"""Validation for Codex custom-agent role contracts."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any


ROLE_CONTRACTS = {
    "repo_mapper": {
        "sandbox_mode": "read-only",
        "responsibility": "map source-backed repository facts",
    },
    "governance_projector": {
        "sandbox_mode": "read-only",
        "responsibility": "project one audience and one subdomain",
    },
    "projection_reconciler": {
        "sandbox_mode": "read-only",
        "responsibility": "reconcile candidates without hiding conflicts",
    },
    "governance_validator": {
        "sandbox_mode": "read-only",
        "responsibility": "validate governance artifacts",
    },
    "governed_worker": {
        "sandbox_mode": "workspace-write",
        "responsibility": "execute one resolved Action in owned scope",
    },
    "evidence_verifier": {
        "sandbox_mode": "read-only",
        "responsibility": "verify postconditions and Evidence",
    },
}
_SANDBOX_LEVEL = {
    "read-only": 0,
    "workspace-write": 1,
    "danger-full-access": 2,
}


def validate_agent_contract(document: dict[str, Any]) -> list[str]:
    """Return stable blocker codes for one agent contract."""

    role = document.get("name")
    expected = ROLE_CONTRACTS.get(role)
    if expected is None:
        return ["AGENT_ROLE_CONTRACT_INVALID", "HANDOFF_REQUIRED"]
    required = ("name", "description", "developer_instructions", "sandbox_mode")
    if any(not isinstance(document.get(field), str) or not document[field] for field in required):
        return ["AGENT_ROLE_CONTRACT_INVALID", "HANDOFF_REQUIRED"]
    if document["sandbox_mode"] != expected["sandbox_mode"]:
        return ["AGENT_CONFIGURATION_UNTRUSTED", "HANDOFF_REQUIRED"]
    instructions = document["developer_instructions"].lower()
    if role != "governed_worker" and any(
        phrase in instructions for phrase in ("write files", "modify files", "workspace-write")
    ):
        return ["AGENT_ROLE_CONTRACT_INVALID", "HANDOFF_REQUIRED"]
    return []


def validate_agent_directory(agent_dir: Path) -> list[dict[str, Any]]:
    """Validate all required project agents and reject silent fallback."""

    issues = []
    for role in ROLE_CONTRACTS:
        path = agent_dir / f"{role.replace('_', '-')}.toml"
        if not path.is_file():
            issues.append(
                {
                    "role": role,
                    "path": path.as_posix(),
                    "blocker_codes": ["AGENT_BINDING_UNAVAILABLE", "HANDOFF_REQUIRED"],
                }
            )
            continue
        try:
            text = path.read_text(encoding="utf-8")
            document = tomllib.loads(text)
        except (OSError, tomllib.TOMLDecodeError):
            text = ""
            document = {}
        blockers = (
            ["AGENT_CONFIGURATION_UNTRUSTED", "HANDOFF_REQUIRED"]
            if not text.startswith("# managed-by: sdd-harness")
            else validate_agent_contract(document)
        )
        if blockers:
            issues.append(
                {
                    "role": role,
                    "path": path.as_posix(),
                    "blocker_codes": blockers,
                }
            )
    return issues


def validate_parent_permissions(role: str, parent_sandbox_mode: str) -> list[str]:
    """Reject a role whose default write level exceeds the parent session."""

    contract = ROLE_CONTRACTS.get(role)
    parent_level = _SANDBOX_LEVEL.get(parent_sandbox_mode)
    if contract is None or parent_level is None:
        return ["AGENT_ROLE_CONTRACT_INVALID", "HANDOFF_REQUIRED"]
    role_level = _SANDBOX_LEVEL[contract["sandbox_mode"]]
    return (
        []
        if role_level <= parent_level
        else ["AGENT_CONFIGURATION_UNTRUSTED", "HANDOFF_REQUIRED"]
    )
