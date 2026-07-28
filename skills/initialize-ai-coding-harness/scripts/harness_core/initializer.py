"""Repo-first projection planning and plan-bound single-writer initialization."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .action_graph import build_action_graph
from .artifacts import (
    GOVERNANCE_SCHEMA_VERSION,
    attach_digest,
    canonical_json,
    path_digest,
)
from .contracts import DEFAULT_SCHEMA_DIR, validate_governance_bundle
from .discovery import discover_repository
from .facts import extract_source_facts
from .projection import compile_governance_projection
from .snapshot import create_repository_snapshot
from .templates import HARNESS_MARKER_END, HARNESS_MARKER_START, replace_marked_block


_AGENT_ROLES = {
    "repo-mapper": (
        "repo_mapper",
        "Map source-backed repository facts.",
        "read-only",
        """Accept one repository snapshot. Call deterministic discovery only.
Return source-backed facts with exact source references.
Do not generate rules, infer permission, or write.""",
    ),
    "governance-projector": (
        "governance_projector",
        "Project one audience and one governance subdomain.",
        "read-only",
        """Accept exactly one audience and one subdomain.
Use only source-backed facts and return Rule Candidates.
Record missing facts as blocker codes. Do not decide final readiness.""",
    ),
    "projection-reconciler": (
        "projection_reconciler",
        "Reconcile candidates without hiding conflicts.",
        "read-only",
        """Merge candidate artifacts deterministically.
Preserve every conflict and gap. Never choose silently between conflicting rules.
Do not publish or modify the repository.""",
    ),
    "governance-validator": (
        "governance_validator",
        "Validate governance artifacts and cross-file bindings.",
        "read-only",
        """Run Schema and cross-file validation.
Return stable blocker codes and stop on invalid input.
Do not repair inputs or replace validation with natural-language judgment.""",
    ),
    "governed-worker": (
        "governed_worker",
        "Execute one resolved Action within explicit ownership.",
        "workspace-write",
        """Accept only projection_id, Work Grant, action_id, typed parameters, and owned scope.
Use the resolved binding without overriding argv, cwd, environment, or postconditions.
Do not change governance control-plane files or another worker's scope.""",
    ),
    "evidence-verifier": (
        "evidence_verifier",
        "Verify postconditions and digest-bound Action Evidence.",
        "read-only",
        """Validate actual diff, exit facts, postconditions, projection drift, and Evidence digests.
Do not accept an Agent summary as execution evidence.
Return stable blocker codes and never repair the execution result.""",
    ),
}
_TOML_MARKER_START = "# ai-coding-harness:start"
_TOML_MARKER_END = "# ai-coding-harness:end"


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _agent_toml(
    name: str, description: str, sandbox: str, instructions: str
) -> str:
    escaped_description = json.dumps(description, ensure_ascii=False)
    return (
        "# managed-by: sdd-harness\n"
        f'name = "{name}"\n'
        f"description = {escaped_description}\n"
        f'sandbox_mode = "{sandbox}"\n'
        'developer_instructions = """\n'
        f"{instructions.strip()}\n"
        '"""\n'
    )


def _agents_block(projection_id: str) -> str:
    return f"""# AI Coding Harness

- Treat this block as the Harness orchestration entrypoint.
- Current governance projection: `{projection_id}`.
- Read `.harness/governance/projection.lock.json` before governed work.
- Use `$harness` for generation, update, action routing, or Evidence verification.
- Spawn only the six project roles declared in `.codex/agents/`; do not fall back to a generic agent.
- Projection lanes are read-only. Publish and code writes use a single writer or non-overlapping ownership.
- Submit only `projection_id`, Work Grant, `action_id`, scope, and typed parameters.
- Stop on any stable blocker code. Agent summaries, Memory, and Transcript are not authorization or Evidence.
"""


def _replace_toml_block(current: str, block: str) -> str:
    managed = (
        f"{_TOML_MARKER_START}\n"
        f"{block.rstrip()}\n"
        f"{_TOML_MARKER_END}\n"
    )
    start = current.find(_TOML_MARKER_START)
    if start < 0:
        separator = "" if not current or current.endswith("\n\n") else "\n"
        return f"{current}{separator}{managed}"
    end = current.find(_TOML_MARKER_END, start + len(_TOML_MARKER_START))
    if end < 0:
        raise ValueError("GOVERNANCE_INHERITANCE_INVALID")
    end += len(_TOML_MARKER_END)
    if end < len(current) and current[end] == "\n":
        end += 1
    return f"{current[:start]}{managed}{current[end:]}"


def _skill_text() -> str:
    return """---
name: harness
description: Generate or enforce the repository's deterministic Agent governance projection.
---

# Harness

## Contract

Input: repository snapshot, source-backed facts, audience/subdomain lane, Work Grant, and action_id.

Output: validated projection artifacts, Gate Decision, or digest-bound Action Evidence.

Boundary: never infer permission from tool availability; never accept arbitrary command, cwd, environment, or binding overrides.

Failure: return canonical blocker codes and `HANDOFF_REQUIRED`; keep preflight failures at zero writes.

## Workflow

1. Read `AGENTS.md` and `.harness/governance/projection.lock.json`.
2. For generation, use `repo_mapper`, then the complete audience/subdomain projector matrix, reconciler, and validator.
3. Confirm one unchanged Plan digest before publishing control-plane files.
4. For enforcement, resolve `action_id`, run G0-G7, delegate one owned scope to `governed_worker`, then use `evidence_verifier`.
5. Report only conclusions accepted by deterministic Evidence validation.
"""


def _hook_config() -> str:
    command = "sdd-harness hook"
    return _json_text(
        {
            "description": "Harness lifecycle enforcement for trusted projects.",
            "hooks": {
                "SessionStart": [
                    {
                        "matcher": "startup|resume|clear|compact",
                        "hooks": [
                            {
                                "type": "command",
                                "command": command,
                                "commandWindows": command,
                                "timeout": 10,
                            }
                        ],
                    }
                ],
                "PreToolUse": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": command,
                                "commandWindows": command,
                                "timeout": 10,
                            }
                        ],
                    }
                ],
                "PermissionRequest": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": command,
                                "commandWindows": command,
                                "timeout": 10,
                            }
                        ],
                    }
                ],
                "PostToolUse": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": command,
                                "commandWindows": command,
                                "timeout": 10,
                            }
                        ],
                    }
                ],
                "Stop": [
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": command,
                                "commandWindows": command,
                                "timeout": 10,
                            }
                        ]
                    }
                ],
            },
        }
    )


def _merged_hook_config(current: str | None) -> str:
    generated = json.loads(_hook_config())
    if not current:
        return _json_text(generated)
    try:
        document = json.loads(current)
    except json.JSONDecodeError as exc:
        raise ValueError("GOVERNANCE_INHERITANCE_INVALID") from exc
    if not isinstance(document, dict):
        raise ValueError("GOVERNANCE_INHERITANCE_INVALID")
    hooks = document.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError("GOVERNANCE_INHERITANCE_INVALID")
    for event, groups in generated["hooks"].items():
        existing = hooks.setdefault(event, [])
        if not isinstance(existing, list):
            raise ValueError("GOVERNANCE_INHERITANCE_INVALID")
        existing[:] = [
            group
            for group in existing
            if "sdd-harness hook" not in json.dumps(group, sort_keys=True)
        ]
        existing.extend(groups)
    document.setdefault("description", generated["description"])
    return _json_text(document)


def compile_repository_projection(repository: Path) -> dict[str, Any]:
    """Compile one repository without writing to it."""

    repository = repository.resolve()
    snapshot = create_repository_snapshot(repository)
    discovery = discover_repository(repository)
    facts = extract_source_facts(discovery, snapshot)
    graph = build_action_graph(facts)
    declarations_path = repository / ".harness" / "governance" / "declarations.json"
    declarations = (
        json.loads(declarations_path.read_text(encoding="utf-8"))
        if declarations_path.is_file()
        else {}
    )
    bundle = compile_governance_projection(
        snapshot,
        facts,
        graph,
        maintainer_declarations=declarations,
    )
    return {"snapshot": snapshot, "discovery": discovery, "bundle": bundle}


def build_initialization_plan(repository: Path) -> dict[str, Any]:
    """Build an exact, digest-bound initialization plan without writes."""

    repository = repository.resolve()
    compiled = compile_repository_projection(repository)
    snapshot = compiled["snapshot"]
    bundle = compiled["bundle"]
    validation = validate_governance_bundle(bundle)
    blockers = sorted({issue.code for issue in validation})
    if bundle["projection_lock"].get("blockers"):
        blockers.extend(
            item["code"] for item in bundle["projection_lock"]["blockers"]
        )
    blockers = sorted(set(blockers))
    projection_id = bundle["projection_lock"]["projection_id"]

    governance = repository / ".harness" / "governance"
    mode = (
        "update"
        if governance.is_dir()
        else "adopt"
        if any(
            (repository / name).exists()
            for name in ("AGENTS.md", "pyproject.toml", "package.json", ".github")
        )
        else "bootstrap"
    )
    current_agents = (
        (repository / "AGENTS.md").read_text(encoding="utf-8")
        if (repository / "AGENTS.md").is_file()
        else ""
    )
    managed_agents_block = (
        f"{HARNESS_MARKER_START}\n"
        f"{_agents_block(projection_id).rstrip()}\n"
        f"{HARNESS_MARKER_END}\n"
    )
    agents_content = replace_marked_block(current_agents, managed_agents_block)
    config_block = (
        "[agents]\n"
        "enabled = true\n"
        "max_concurrent_threads_per_session = 6\n\n"
        "[features]\n"
        "hooks = true\n"
    )
    config_path = repository / ".codex" / "config.toml"
    config_current = (
        config_path.read_text(encoding="utf-8") if config_path.is_file() else ""
    )
    try:
        config = _replace_toml_block(config_current, config_block)
        hooks_path = repository / ".codex" / "hooks.json"
        hooks = _merged_hook_config(
            hooks_path.read_text(encoding="utf-8") if hooks_path.is_file() else None
        )
    except ValueError:
        blockers.append("GOVERNANCE_INHERITANCE_INVALID")
        config = config_current
        hooks = (
            hooks_path.read_text(encoding="utf-8")
            if "hooks_path" in locals() and hooks_path.is_file()
            else ""
        )
    files: dict[str, str] = {
        ".harness/governance/sources.lock.json": _json_text(bundle["sources"]),
        ".harness/governance/action-graph.json": _json_text(bundle["action_graph"]),
        ".harness/governance/rules.json": _json_text(bundle["rules"]),
        ".harness/governance/projection.lock.json": _json_text(bundle["projection_lock"]),
        "AGENTS.md": agents_content,
        ".codex/config.toml": config,
        ".codex/hooks.json": hooks,
        ".agents/skills/harness/SKILL.md": _skill_text(),
        ".agents/skills/harness/scripts/dispatch.py": (
            "# managed-by: sdd-harness\n"
            "from harness_core.cli import main\n\n"
            "if __name__ == '__main__':\n"
            "    raise SystemExit(main())\n"
        ),
        ".agents/skills/harness/schemas/governance.schema.json": (
            DEFAULT_SCHEMA_DIR / "governance.schema.json"
        ).read_text(encoding="utf-8"),
        ".agents/skills/harness/references/governance-contract.md": (
            "# Governance contract\n\n"
            "The structured projection in `.harness/governance/` is the SSOT. "
            "`AGENTS.md` is its runtime entrypoint. G0-G7 and accepted Action Evidence "
            "determine whether a governed conclusion is valid.\n"
        ),
    }
    for filename, role in _AGENT_ROLES.items():
        files[f".codex/agents/{filename}.toml"] = _agent_toml(*role)

    actions = []
    for relative, content in sorted(files.items()):
        target = repository / relative
        actions.append(
            {
                "path": relative,
                "expected_digest": path_digest(target),
                "content": content,
                "operation": (
                    "unchanged"
                    if target.is_file()
                    and target.read_text(encoding="utf-8") == content
                    else "update"
                    if target.is_file()
                    else "create"
                ),
            }
        )
        if (
            target.is_file()
            and relative.startswith(".codex/agents/")
            and "# managed-by: sdd-harness" not in target.read_text(encoding="utf-8")
        ):
            blockers.append("GOVERNANCE_CONFLICT")

    plan = {
        "artifact_type": "initialization-plan",
        "schema_version": GOVERNANCE_SCHEMA_VERSION,
        "mode": mode,
        "snapshot_digest": snapshot["snapshot_digest"],
        "projection_id": projection_id,
        "actions": actions,
        "write_scope": [item["path"] for item in actions],
        "blocker_codes": sorted(set(blockers)),
    }
    return attach_digest(plan, "plan_digest")


def apply_initialization_plan(repository: Path, plan: dict[str, Any]) -> dict[str, Any]:
    """Apply one unchanged plan with rollback on any write failure."""

    repository = repository.resolve()
    if plan.get("plan_digest") != attach_digest(plan, "plan_digest")["plan_digest"]:
        return {"status": "blocked", "blocker_codes": ["GOVERNANCE_PROJECTION_STALE"]}
    if plan.get("blocker_codes"):
        return {"status": "blocked", "blocker_codes": plan["blocker_codes"]}
    current = create_repository_snapshot(repository)
    if current["snapshot_digest"] != plan.get("snapshot_digest"):
        return {"status": "blocked", "blocker_codes": ["GOVERNANCE_PROJECTION_STALE"]}

    resolved: list[tuple[Path, str, bool, str]] = []
    for action in plan.get("actions", []):
        target = (repository / action["path"]).resolve()
        if not target.is_relative_to(repository):
            return {
                "status": "blocked",
                "blocker_codes": ["GOVERNANCE_SCOPE_UNRESOLVED", "HANDOFF_REQUIRED"],
            }
        if path_digest(target) != action["expected_digest"]:
            return {"status": "blocked", "blocker_codes": ["GOVERNANCE_PROJECTION_STALE"]}
        resolved.append(
            (target, action["content"], target.exists(), action.get("operation", "update"))
        )

    backup_root = Path(tempfile.mkdtemp(prefix="sdd-harness-rollback-"))
    written: list[tuple[Path, bool, Path | None]] = []
    created_directories: set[Path] = set()
    temporary: Path | None = None
    try:
        for index, (target, content, existed, operation) in enumerate(resolved):
            if operation == "unchanged":
                continue
            backup = backup_root / str(index) if existed else None
            if backup is not None:
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
            parent = target.parent
            while parent != repository and not parent.exists():
                created_directories.add(parent)
                parent = parent.parent
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(f".{target.name}.sdd-harness.tmp")
            temporary.write_text(content, encoding="utf-8", newline="\n")
            os.replace(temporary, target)
            temporary = None
            written.append((target, existed, backup))
    except Exception:
        if temporary is not None and temporary.exists():
            temporary.unlink()
        for target, existed, backup in reversed(written):
            if existed and backup is not None:
                shutil.copy2(backup, target)
            elif target.exists():
                target.unlink()
        for directory in sorted(
            created_directories,
            key=lambda path: len(path.parts),
            reverse=True,
        ):
            try:
                directory.rmdir()
            except OSError:
                pass
        return {
            "status": "blocked",
            "blocker_codes": ["GOVERNANCE_SCOPE_UNRESOLVED", "HANDOFF_REQUIRED"],
        }
    finally:
        shutil.rmtree(backup_root, ignore_errors=True)

    return {
        "status": "applied",
        "mode": plan["mode"],
        "projection_id": plan["projection_id"],
        "plan_digest": plan["plan_digest"],
        "changed_paths": [
            item["path"]
            for item in plan["actions"]
            if item.get("operation") != "unchanged"
        ],
        "unchanged_paths": [
            item["path"]
            for item in plan["actions"]
            if item.get("operation") == "unchanged"
        ],
        "blocker_codes": [],
    }
