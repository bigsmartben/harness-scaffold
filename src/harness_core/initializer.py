"""Plan-bound Harness 2.0 initialization."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import tomllib
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

import yaml

from .action_graph import build_action_graph
from .artifacts import (
    CORE_VERSION,
    SCHEMA_VERSION,
    attach_digest,
    path_digest,
)
from .contracts import validate_governance_bundle, validate_project_config
from .discovery import classify_repository_model, discover_repository
from .facts import extract_source_facts
from .package_resources import (
    iter_resource_files,
    repo_documentation_skill_root,
    repo_skill_root,
)
from .policy import (
    default_project_config,
    load_project_config,
    render_project_config,
)
from .projection import compile_governance_projection
from .snapshot import create_repository_snapshot
from .templates import (
    HARNESS_MARKER_END,
    HARNESS_MARKER_START,
    replace_marked_block,
)


_TOML_MARKER_START = "# ai-coding-harness:start"
_TOML_MARKER_END = "# ai-coding-harness:end"
_DOCUMENTATION_SKILL_NAME = "repo-documentation-maker"
_DOCUMENTATION_SKILL_VERSION = "1.0.0"
_DOCUMENTATION_SKILL_MANIFEST = ".scaffold-manifest.json"
_HOOK_EVENTS = (
    "SessionStart",
    "PreToolUse",
    "PermissionRequest",
    "PostToolUse",
    "Stop",
    "SessionEnd",
)


def _managed_text_digest(value: str | bytes | Path) -> str | None:
    try:
        if isinstance(value, Path):
            text = value.read_text(encoding="utf-8")
        elif isinstance(value, bytes):
            text = value.decode("utf-8")
        else:
            text = value
    except (OSError, UnicodeDecodeError):
        return None
    normalized = text.replace("\r\n", "\n")
    return f"sha256:{hashlib.sha256(normalized.encode('utf-8')).hexdigest()}"


def _documentation_skill_manifest(
    managed_files: dict[str, str],
    *,
    preserved_customizations: list[str],
) -> str:
    return _json_text(
        {
            "schema_version": 1,
            "skill_name": _DOCUMENTATION_SKILL_NAME,
            "skill_version": _DOCUMENTATION_SKILL_VERSION,
            "managed_files": managed_files,
            "preserved_customizations": preserved_customizations,
        }
    )


def _valid_managed_relative_path(value: Any) -> bool:
    if (
        not isinstance(value, str)
        or not value
        or not value.isascii()
        or "\\" in value
    ):
        return False
    posix_path = PurePosixPath(value)
    windows_path = PureWindowsPath(value)
    return (
        not posix_path.is_absolute()
        and not windows_path.is_absolute()
        and not windows_path.drive
        and all(part not in {"", ".", ".."} for part in value.split("/"))
    )


def _valid_documentation_skill_manifest(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    managed = value.get("managed_files")
    version = value.get("skill_version")
    return (
        value.get("schema_version") == 1
        and value.get("skill_name") == _DOCUMENTATION_SKILL_NAME
        and isinstance(version, str)
        and re.fullmatch(r"\d+\.\d+\.\d+", version) is not None
        and isinstance(managed, dict)
        and all(
            _valid_managed_relative_path(path)
            and isinstance(digest, str)
            and digest.startswith("sha256:")
            for path, digest in managed.items()
        )
    )


def _planned_documentation_skill(
    repository: Path,
) -> tuple[dict[str, str | None], list[str], list[str]]:
    source = {
        relative: payload.decode("utf-8")
        for relative, payload in iter_resource_files(
            repo_documentation_skill_root()
        )
    }
    source_digests = {
        relative: str(_managed_text_digest(content))
        for relative, content in source.items()
    }
    target_root = (
        repository / ".agents" / "skills" / _DOCUMENTATION_SKILL_NAME
    )
    manifest_path = target_root / _DOCUMENTATION_SKILL_MANIFEST
    prefix = f".agents/skills/{_DOCUMENTATION_SKILL_NAME}"
    files: dict[str, str | None] = {}
    blockers: list[str] = []
    preserved: list[str] = []

    if not target_root.exists():
        files.update(
            {f"{prefix}/{relative}": content for relative, content in source.items()}
        )
        files[f"{prefix}/{_DOCUMENTATION_SKILL_MANIFEST}"] = (
            _documentation_skill_manifest(
                source_digests,
                preserved_customizations=[],
            )
        )
        return files, blockers, preserved

    try:
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return files, ["REPO_SKILL_OWNERSHIP_UNRESOLVED"], preserved
    if not _valid_documentation_skill_manifest(previous):
        return files, ["REPO_SKILL_MANIFEST_INVALID"], preserved

    previous_version = tuple(
        int(part) for part in previous["skill_version"].split(".")
    )
    current_version = tuple(
        int(part) for part in _DOCUMENTATION_SKILL_VERSION.split(".")
    )
    if previous_version[0] > current_version[0]:
        return files, ["REPO_SKILL_VERSION_INCOMPATIBLE"], preserved

    previous_managed = previous["managed_files"]
    for relative, content in sorted(source.items()):
        target = target_root / relative
        planned = f"{prefix}/{relative}"
        if not target.is_file():
            files[planned] = content
            continue
        current_digest = _managed_text_digest(target)
        if current_digest in {
            source_digests[relative],
            previous_managed.get(relative),
        }:
            files[planned] = content
        else:
            preserved.append(planned)

    for relative, previous_digest in sorted(previous_managed.items()):
        if relative in source:
            continue
        target = target_root / relative
        if not target.is_file():
            continue
        planned = f"{prefix}/{relative}"
        if _managed_text_digest(target) == previous_digest:
            files[planned] = None
        else:
            preserved.append(planned)

    known = {*source, *previous_managed, _DOCUMENTATION_SKILL_MANIFEST}
    for target in target_root.rglob("*"):
        if not target.is_file():
            continue
        relative = target.relative_to(target_root).as_posix()
        if relative not in known:
            preserved.append(f"{prefix}/{relative}")

    preserved = sorted(set(preserved))
    files[f"{prefix}/{_DOCUMENTATION_SKILL_MANIFEST}"] = (
        _documentation_skill_manifest(
            source_digests,
            preserved_customizations=preserved,
        )
    )
    return files, blockers, preserved


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _agents_block() -> str:
    return """# AI Coding Harness 2.0

- Treat this marked block as the repository Harness entrypoint.
- Use `$harness` for governed local work, explicit `git commit`, Issue operations, Test, Build, CI, and controlled delivery.
- Read `.harness/harness.yaml` and run `sdd-harness inspect --json` before a governed action.
- Keep ordinary local work continuous and use only the minimum sufficient T0-T3 validation.
- Call actions by their source-backed `action_id`; do not invent or override an invocation.
- Treat project policy as versioned behavior and a task decision as one task or one exact action only.
- Require an independent task decision and upstream platform gates for every controlled action.
- Stop with stable blocker codes when runtime, projection, source, scope, binding, branch, target, or evidence cannot be verified.
"""


def _managed_agents_content(current: str) -> str:
    block = (
        f"{HARNESS_MARKER_START}\n"
        f"{_agents_block().rstrip()}\n"
        f"{HARNESS_MARKER_END}\n"
    )
    return replace_marked_block(current, block)


def _replace_toml_block(current: str, block: str | None) -> str:
    start = current.find(_TOML_MARKER_START)
    if start >= 0:
        end = current.find(_TOML_MARKER_END, start + len(_TOML_MARKER_START))
        if end < 0:
            raise ValueError("GOVERNANCE_INHERITANCE_INVALID")
        end += len(_TOML_MARKER_END)
        if end < len(current) and current[end] == "\n":
            end += 1
        current = f"{current[:start]}{current[end:]}"
    current = current.rstrip()
    if block is None:
        return f"{current}\n" if current else ""
    managed = (
        f"{_TOML_MARKER_START}\n"
        f"{block.rstrip()}\n"
        f"{_TOML_MARKER_END}\n"
    )
    return f"{current}\n\n{managed}" if current else managed


def _merge_hook_feature(current: str, *, enabled: bool) -> str:
    cleaned = _replace_toml_block(current, None)
    if not enabled:
        return cleaned
    try:
        document = tomllib.loads(cleaned) if cleaned.strip() else {}
    except tomllib.TOMLDecodeError as exc:
        raise ValueError("GOVERNANCE_INHERITANCE_INVALID") from exc
    features = document.get("features", {})
    if features is not None and not isinstance(features, dict):
        raise ValueError("GOVERNANCE_INHERITANCE_INVALID")
    if "hooks" in features:
        if features["hooks"] is not True:
            raise ValueError("GOVERNANCE_INHERITANCE_INVALID")
        return cleaned

    marker = (
        f"{_TOML_MARKER_START}\n"
        "hooks = true\n"
        f"{_TOML_MARKER_END}\n"
    )
    match = next(
        (
            item
            for item in re.finditer(
                r"(?m)^\[features\][ \t]*(?:#.*)?$", cleaned
            )
        ),
        None,
    )
    if match:
        insertion = match.end()
        return f"{cleaned[:insertion]}\n{marker}{cleaned[insertion:].lstrip(chr(10))}"
    block = "[features]\nhooks = true"
    return _replace_toml_block(cleaned, block)


def _harness_hook_group(event: str) -> dict[str, Any]:
    handler: dict[str, Any] = {
        "type": "command",
        "command": "sdd-harness hook",
        "timeout": 10,
    }
    group: dict[str, Any] = {"hooks": [handler]}
    if event in {"SessionStart"}:
        group["matcher"] = "startup|resume|clear|compact"
    elif event in {"PreToolUse", "PermissionRequest", "PostToolUse"}:
        group["matcher"] = "*"
    return group


def _merge_hook_config(
    current: str | None,
    *,
    enabled: bool,
) -> str | None:
    if current:
        try:
            document = json.loads(current)
        except json.JSONDecodeError as exc:
            raise ValueError("GOVERNANCE_INHERITANCE_INVALID") from exc
        if not isinstance(document, dict):
            raise ValueError("GOVERNANCE_INHERITANCE_INVALID")
    else:
        document = {}
    hooks = document.get("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError("GOVERNANCE_INHERITANCE_INVALID")
    for event in list(hooks):
        groups = hooks[event]
        if not isinstance(groups, list):
            raise ValueError("GOVERNANCE_INHERITANCE_INVALID")
        filtered = [
            group
            for group in groups
            if "sdd-harness hook" not in json.dumps(group, sort_keys=True)
        ]
        if filtered:
            hooks[event] = filtered
        else:
            hooks.pop(event)
    if enabled:
        for event in _HOOK_EVENTS:
            hooks.setdefault(event, []).append(_harness_hook_group(event))
        document["description"] = (
            "Optional Harness defense-in-depth for this trusted repository."
        )
    document["hooks"] = hooks
    if not hooks:
        document.pop("hooks", None)
        if document.get("description", "").startswith("Optional Harness"):
            document.pop("description", None)
    return _json_text(document) if document else None


def compile_repository_projection(
    repository: Path,
    *,
    project_config: dict[str, Any],
    snapshot_overrides: dict[str, str | bytes | None] | None = None,
) -> dict[str, Any]:
    root = repository.resolve()
    snapshot = create_repository_snapshot(
        root, content_overrides=snapshot_overrides
    )
    discovery = discover_repository(root)
    facts = extract_source_facts(
        discovery,
        snapshot,
        project_policy=project_config["project_policy"],
    )
    graph = build_action_graph(facts)
    bundle = compile_governance_projection(
        snapshot,
        facts,
        graph,
        project_policy=project_config["project_policy"],
    )
    return {"snapshot": snapshot, "discovery": discovery, "bundle": bundle}


def _target_mode(repository: Path) -> str:
    return str(classify_repository_model(repository)["mode"])


def _planned_files(
    repository: Path,
    *,
    config: dict[str, Any],
    bundle: dict[str, dict[str, Any]] | None,
    agents_content: str,
    hooks_enabled: bool,
) -> tuple[dict[str, str | None], list[str], list[str]]:
    files: dict[str, str | None] = {
        ".harness/harness.yaml": render_project_config(config),
        ".harness/.gitignore": (
            "runtime/\nreports/\nevidence/\nruns/\ncache/\n"
        ),
        "AGENTS.md": agents_content,
    }
    if bundle is not None:
        files.update(_projection_files(bundle))
    canonical_skill_paths: set[str] = set()
    for relative, payload in iter_resource_files(repo_skill_root()):
        target = f".agents/skills/harness/{relative}"
        canonical_skill_paths.add(target)
        files[target] = payload.decode("utf-8")

    target_skill = repository / ".agents" / "skills" / "harness"
    if target_skill.is_dir():
        for path in target_skill.rglob("*"):
            if path.is_file():
                relative = path.relative_to(repository).as_posix()
                if relative not in canonical_skill_paths:
                    files[relative] = None

    blockers: list[str] = []
    documentation_files, documentation_blockers, preserved_customizations = (
        _planned_documentation_skill(repository)
    )
    files.update(documentation_files)
    blockers.extend(documentation_blockers)
    config_path = repository / ".codex" / "config.toml"
    hook_path = repository / ".codex" / "hooks.json"
    current_config = (
        config_path.read_text(encoding="utf-8") if config_path.is_file() else ""
    )
    current_hooks = (
        hook_path.read_text(encoding="utf-8") if hook_path.is_file() else None
    )
    try:
        next_config = _merge_hook_feature(
            current_config, enabled=hooks_enabled
        )
        next_hooks = _merge_hook_config(current_hooks, enabled=hooks_enabled)
        if next_config or config_path.exists():
            files[".codex/config.toml"] = next_config or None
        if next_hooks is not None or hook_path.exists():
            files[".codex/hooks.json"] = next_hooks
    except ValueError:
        blockers.append("GOVERNANCE_INHERITANCE_INVALID")

    agent_dir = repository / ".codex" / "agents"
    if agent_dir.is_dir():
        for path in agent_dir.glob("*.toml"):
            try:
                managed = path.read_text(encoding="utf-8").startswith(
                    "# managed-by: sdd-harness"
                )
            except OSError:
                managed = False
            if managed:
                files[path.relative_to(repository).as_posix()] = None
    return files, blockers, preserved_customizations


def _projection_files(
    bundle: dict[str, dict[str, Any]],
) -> dict[str, str]:
    return {
        ".harness/governance/sources.lock.json": _json_text(bundle["sources"]),
        ".harness/governance/action-graph.json": _json_text(
            bundle["action_graph"]
        ),
        ".harness/governance/rules.json": _json_text(bundle["rules"]),
        ".harness/governance/projection.lock.json": _json_text(
            bundle["projection_lock"]
        ),
        ".harness/governance/compatibility.json": _json_text(
            {
                "core_version": CORE_VERSION,
                "schema_version": SCHEMA_VERSION,
                "skill_version": SCHEMA_VERSION,
                "plugin_version": SCHEMA_VERSION,
            }
        ),
    }


def _file_actions(
    repository: Path,
    files: dict[str, str | None],
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for relative, content in sorted(files.items()):
        target = repository / relative
        if content is None:
            operation = "delete" if target.is_file() else "unchanged"
        elif target.is_file():
            operation = (
                "unchanged"
                if target.read_text(encoding="utf-8") == content
                else "update"
            )
        else:
            operation = "create"
        actions.append(
            {
                "path": relative,
                "expected_digest": path_digest(target),
                "content": content,
                "operation": operation,
            }
        )
    return actions


def _preserved_paths(
    repository: Path,
    managed_paths: set[str],
    snapshot: dict[str, Any],
) -> list[str]:
    preserved = {
        item["path"]
        for item in snapshot["files"]
        if item["path"] not in managed_paths
    }
    for name in (
        "README.md",
        "pyproject.toml",
        "package.json",
        "requirements.txt",
    ):
        if (repository / name).is_file() and name not in managed_paths:
            preserved.add(name)
    for name in (
        "src",
        "tests",
        "apps",
        "services",
        ".github/workflows",
    ):
        if (repository / name).is_dir() and not any(
            path == name or path.startswith(f"{name}/")
            for path in managed_paths
        ):
            preserved.add(f"{name}/**")
    return sorted(preserved)


def build_initialization_plan(
    repository: Path,
    *,
    with_hooks: bool = False,
    project_config_override: dict[str, Any] | None = None,
    include_projection: bool = False,
) -> dict[str, Any]:
    root = repository.resolve()
    existing = load_project_config(root)
    config_blockers: list[str] = []
    config_path = root / ".harness" / "harness.yaml"
    if config_path.is_file() and existing is None:
        try:
            raw_config = yaml.safe_load(
                config_path.read_text(encoding="utf-8")
            )
        except (OSError, yaml.YAMLError):
            raw_config = None
        if (
            isinstance(raw_config, dict)
            and raw_config.get("schema_version") != SCHEMA_VERSION
        ):
            config_blockers.append("HARNESS_RUNTIME_INCOMPATIBLE")
        else:
            config_blockers.append("CONFIG_INVALID")
    mode = _target_mode(root)
    config = project_config_override or existing or default_project_config(
        mode=mode, hooks_enabled=with_hooks
    )
    if project_config_override is not None:
        config_blockers.extend(
            issue.code for issue in validate_project_config(config)
        )
    if with_hooks and config["project_policy"]["hooks"] != "enabled":
        config = json.loads(json.dumps(config))
        config["project_policy"]["hooks"] = "enabled"
    hooks_enabled = config["project_policy"]["hooks"] == "enabled"

    current_agents = (
        (root / "AGENTS.md").read_text(encoding="utf-8")
        if (root / "AGENTS.md").is_file()
        else ""
    )
    inheritance_blockers: list[str] = []
    try:
        agents_content = _managed_agents_content(current_agents)
    except ValueError:
        agents_content = current_agents
        inheritance_blockers.append("GOVERNANCE_INHERITANCE_INVALID")
    harness_text = render_project_config(config)
    preflight = create_repository_snapshot(root)
    bundle: dict[str, dict[str, Any]] | None = None
    projection_blockers: set[str] = set()
    if include_projection:
        compiled = compile_repository_projection(
            root,
            project_config=config,
            snapshot_overrides={
                "AGENTS.md": agents_content,
                ".harness/harness.yaml": harness_text,
            },
        )
        bundle = compiled["bundle"]
        projection_blockers.update(
            issue.code for issue in validate_governance_bundle(bundle)
        )
        projection_blockers.update(bundle["projection_lock"]["blockers"])
    blockers = {
        *config_blockers,
        *inheritance_blockers,
        *projection_blockers,
    }
    files, file_blockers, preserved_customizations = _planned_files(
        root,
        config=config,
        bundle=bundle,
        agents_content=agents_content,
        hooks_enabled=hooks_enabled,
    )
    blockers.update(file_blockers)

    actions = _file_actions(root, files)
    model = classify_repository_model(root)

    plan = {
        "artifact_type": "initialization-plan",
        "schema_version": SCHEMA_VERSION,
        "phase": (
            "entrypoint-and-projection"
            if include_projection
            else "entrypoint"
        ),
        "mode": "update" if existing else mode,
        "repository_model": model["model"],
        "classification_sources": model["source_refs"],
        "classification_reason": model["reason"],
        "preflight_snapshot_digest": preflight["snapshot_digest"],
        "projection_id": (
            bundle["projection_lock"]["projection_id"]
            if bundle is not None
            else None
        ),
        "with_hooks": hooks_enabled,
        "actions": actions,
        "write_scope": [
            item["path"]
            for item in actions
            if item["operation"] != "unchanged"
        ],
        "preserved_paths": _preserved_paths(
            root, set(files), preflight
        ),
        "preserved_customizations": preserved_customizations,
        "blocker_codes": sorted(blockers),
    }
    return attach_digest(plan, "plan_digest")


def build_projection_plan(repository: Path) -> dict[str, Any]:
    """Build the zero-write second-phase governance projection plan."""

    root = repository.resolve()
    preflight = create_repository_snapshot(root)
    config = load_project_config(root)
    blockers: set[str] = set()
    if config is None:
        blockers.add("CONFIG_INVALID")
        bundle = None
        discovery = discover_repository(root)
        files: dict[str, str | None] = {}
    else:
        compiled = compile_repository_projection(
            root,
            project_config=config,
        )
        discovery = compiled["discovery"]
        bundle = compiled["bundle"]
        blockers.update(
            issue.code for issue in validate_governance_bundle(bundle)
        )
        blockers.update(bundle["projection_lock"]["blockers"])
        files = _projection_files(bundle)

    actions = _file_actions(root, files)
    graph_actions = (
        bundle["action_graph"].get("actions", []) if bundle is not None else []
    )
    available = [
        {
            "action_id": action["action_id"],
            "semantics": action["semantics"],
            "cwd": action.get("binding", {}).get("cwd"),
            "source_refs": action["source_refs"],
        }
        for action in graph_actions
        if not all(
            str(source).startswith("harness://")
            for source in action.get("source_refs", [])
        )
    ]
    available_semantics = {item["semantics"] for item in available}
    capability_gaps = [
        semantics
        for semantics in ("test", "build", "ci", "release", "deploy")
        if semantics not in available_semantics
    ]
    model = (
        config.get("mode")
        if config is not None
        else discovery["repository_model"]["mode"]
    )
    plan = {
        "artifact_type": "governance-projection-plan",
        "schema_version": SCHEMA_VERSION,
        "phase": "projection",
        "mode": "projection",
        "repository_model": (
            "Gray" if model == "adopt" else "Blue"
        ),
        "classification_mode": (
            "Adopt" if model == "adopt" else "Bootstrap"
        ),
        "classification_sources": discovery["repository_model"][
            "source_refs"
        ],
        "classification_reason": discovery["repository_model"]["reason"],
        "preflight_snapshot_digest": preflight["snapshot_digest"],
        "projection_id": (
            bundle["projection_lock"]["projection_id"]
            if bundle is not None
            else None
        ),
        "with_hooks": False,
        "actions": actions,
        "write_scope": [
            item["path"]
            for item in actions
            if item["operation"] != "unchanged"
        ],
        "preserved_paths": _preserved_paths(
            root, set(files), preflight
        ),
        "preserved_customizations": [],
        "available_capabilities": available,
        "capability_gaps": capability_gaps,
        "coverage": {
            "total": (
                len(bundle["rules"]["cells"]) if bundle is not None else 0
            ),
            "missing": (
                [
                    cell["cell_id"]
                    for cell in bundle["rules"]["cells"]
                    if cell["coverage_status"] == "missing"
                ]
                if bundle is not None
                else []
            ),
        },
        "blocker_codes": sorted(blockers),
    }
    return attach_digest(plan, "plan_digest")


def apply_projection_plan(
    repository: Path,
    plan: dict[str, Any],
    *,
    approved_plan_digest: str | None = None,
) -> dict[str, Any]:
    """Apply exactly the five managed projection files from a current plan."""

    expected_paths = {
        ".harness/governance/sources.lock.json",
        ".harness/governance/action-graph.json",
        ".harness/governance/rules.json",
        ".harness/governance/projection.lock.json",
        ".harness/governance/compatibility.json",
    }
    observed_paths = {
        str(item.get("path"))
        for item in plan.get("actions", [])
        if isinstance(item, dict)
    }
    if (
        plan.get("artifact_type") != "governance-projection-plan"
        or observed_paths != expected_paths
    ):
        return {
            "status": "blocked",
            "blocker_codes": ["INITIALIZATION_PLAN_STALE"],
        }
    result = apply_initialization_plan(
        repository,
        plan,
        approved_plan_digest=approved_plan_digest,
    )
    if result["status"] == "applied":
        result.update(
            {
                "status": (
                    "unchanged"
                    if not result["changed_paths"]
                    else "applied"
                ),
                "repository_model": plan["repository_model"],
                "classification_mode": plan["classification_mode"],
                "available_capabilities": plan["available_capabilities"],
                "capability_gaps": plan["capability_gaps"],
                "coverage": plan["coverage"],
            }
        )
    return result


def apply_initialization_plan(
    repository: Path,
    plan: dict[str, Any],
    *,
    approved_plan_digest: str | None = None,
) -> dict[str, Any]:
    root = repository.resolve()
    if plan.get("plan_digest") != attach_digest(
        plan, "plan_digest"
    )["plan_digest"]:
        return {
            "status": "blocked",
            "blocker_codes": ["INITIALIZATION_PLAN_STALE"],
        }
    if approved_plan_digest != plan["plan_digest"]:
        return {"status": "blocked", "blocker_codes": ["HANDOFF_REQUIRED"]}
    if plan.get("blocker_codes"):
        return {"status": "blocked", "blocker_codes": plan["blocker_codes"]}
    current = create_repository_snapshot(root)
    if current["snapshot_digest"] != plan.get("preflight_snapshot_digest"):
        return {
            "status": "blocked",
            "blocker_codes": ["INITIALIZATION_PLAN_STALE"],
        }

    resolved: list[tuple[Path, str | None, bool, str]] = []
    for action in plan["actions"]:
        target = (root / action["path"]).resolve()
        if not target.is_relative_to(root):
            return {
                "status": "blocked",
                "blocker_codes": [
                    "GOVERNANCE_SCOPE_UNRESOLVED",
                    "HANDOFF_REQUIRED",
                ],
            }
        if path_digest(target) != action["expected_digest"]:
            return {
                "status": "blocked",
                "blocker_codes": ["INITIALIZATION_PLAN_STALE"],
            }
        resolved.append(
            (
                target,
                action["content"],
                target.exists(),
                action["operation"],
            )
        )

    backup_root = Path(tempfile.mkdtemp(prefix="sdd-harness-rollback-"))
    touched: list[tuple[Path, bool, Path | None]] = []
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
            touched.append((target, existed, backup))
            if operation == "delete":
                target.unlink()
                continue
            parent = target.parent
            while parent != root and not parent.exists():
                created_directories.add(parent)
                parent = parent.parent
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(f".{target.name}.sdd-harness.tmp")
            temporary.write_text(
                str(content), encoding="utf-8", newline="\n"
            )
            os.replace(temporary, target)
            temporary = None
    except Exception:
        if temporary is not None and temporary.exists():
            temporary.unlink()
        for target, existed, backup in reversed(touched):
            if existed and backup is not None:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup, target)
            elif target.exists():
                target.unlink()
        for directory in sorted(
            created_directories,
            key=lambda value: len(value.parts),
            reverse=True,
        ):
            try:
                directory.rmdir()
            except OSError:
                pass
        return {
            "status": "blocked",
            "blocker_codes": [
                "GOVERNANCE_SCOPE_UNRESOLVED",
                "HANDOFF_REQUIRED",
            ],
        }
    finally:
        shutil.rmtree(backup_root, ignore_errors=True)

    return {
        "status": "applied",
        "mode": plan["mode"],
        "projection_id": plan["projection_id"],
        "plan_digest": plan["plan_digest"],
        "with_hooks": plan["with_hooks"],
        "changed_paths": [
            item["path"]
            for item in plan["actions"]
            if item["operation"] != "unchanged"
        ],
        "unchanged_paths": [
            item["path"]
            for item in plan["actions"]
            if item["operation"] == "unchanged"
        ],
        "preserved_customizations": plan.get(
            "preserved_customizations", []
        ),
        "blocker_codes": [],
    }
