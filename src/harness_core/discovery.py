"""Read-only repository fact discovery for Harness planning."""

from __future__ import annotations

import json
import re
import shlex
import tomllib
from pathlib import Path
from typing import Any

import yaml

from .templates import HARNESS_MARKER_END, HARNESS_MARKER_START


PROTECTED_TRIGGERS = {"push", "pull_request", "schedule"}
SCRIPT_CATEGORIES = {
    "lint": "lint",
    "validate": "validation",
    "check": "validation",
    "test": "test",
    "build": "build",
    "codegen": "codegen",
    "generate": "codegen",
    "ci": "ci",
    "package": "package",
    "pack": "package",
    "push": "push",
    "merge": "merge",
    "publish": "publish",
    "release": "release",
    "deploy": "deploy",
}
UNSUPPORTED_SOURCES = {
    ".mcp.json": ("TOOL_NOT_REGISTERED", "MCP"),
    "mcp.json": ("TOOL_NOT_REGISTERED", "MCP"),
    "Makefile": ("ACTION_CLASSIFICATION_UNRESOLVED", "Make"),
    "build.gradle": ("ACTION_CLASSIFICATION_UNRESOLVED", "Gradle"),
    "build.gradle.kts": ("ACTION_CLASSIFICATION_UNRESOLVED", "Gradle"),
    "settings.gradle": ("ACTION_CLASSIFICATION_UNRESOLVED", "Gradle"),
    "settings.gradle.kts": ("ACTION_CLASSIFICATION_UNRESOLVED", "Gradle"),
    "pom.xml": ("ACTION_CLASSIFICATION_UNRESOLVED", "Maven"),
    "Fastfile": ("ACTION_CLASSIFICATION_UNRESOLVED", "Fastlane"),
}


def _package_document(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return document if isinstance(document, dict) else {}


def _package_scripts(path: Path) -> dict[str, str]:
    scripts = _package_document(path).get("scripts", {})
    return scripts if isinstance(scripts, dict) else {}


def _workflow_document(path: Path) -> dict[str, Any]:
    try:
        document = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    except (OSError, yaml.YAMLError):
        return {}
    return document if isinstance(document, dict) else {}


def _workflow_triggers(document: dict[str, Any]) -> list[str]:
    triggers = document.get("on", {})
    if isinstance(triggers, str):
        return [triggers]
    if isinstance(triggers, list):
        return [item for item in triggers if isinstance(item, str)]
    if isinstance(triggers, dict):
        return [item for item in triggers if isinstance(item, str)]
    return []


def _slug(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return result or "root"


def _classify_action(name: str, command: str = "") -> str | None:
    def matches(text: str) -> list[str]:
        return [
            category
            for keyword, category in SCRIPT_CATEGORIES.items()
            if re.search(
                rf"(^|[^a-z]){re.escape(keyword)}([^a-z]|$)",
                text.lower(),
            )
        ]

    name_matches = matches(name)
    command_matches = matches(command)
    categories = name_matches + command_matches
    if not categories:
        return None
    rank = {
        "lint": 1,
        "validation": 1,
        "test": 1,
        "build": 2,
        "codegen": 2,
        "package": 2,
        "ci": 3,
        "push": 4,
        "merge": 4,
        "publish": 4,
        "release": 4,
        "deploy": 4,
    }
    maximum = max(rank[category] for category in categories)
    for category in name_matches + command_matches:
        if rank[category] == maximum:
            return category
    return None


def _workspace_members(root: Path, package: dict[str, Any]) -> list[Path]:
    workspaces = package.get("workspaces", [])
    if isinstance(workspaces, dict):
        workspaces = workspaces.get("packages", [])
    if not isinstance(workspaces, list):
        return []
    members: set[Path] = set()
    for pattern in workspaces:
        if not isinstance(pattern, str):
            continue
        for candidate in root.glob(pattern):
            manifest = candidate / "package.json"
            if (
                candidate.is_dir()
                and manifest.is_file()
                and candidate.resolve().is_relative_to(root)
            ):
                members.add(candidate.resolve())
    return sorted(members)


def _python_workspace_members(root: Path, document: dict[str, Any]) -> list[Path]:
    tool = document.get("tool", {})
    uv = tool.get("uv", {}) if isinstance(tool, dict) else {}
    workspace = uv.get("workspace", {}) if isinstance(uv, dict) else {}
    patterns = workspace.get("members", []) if isinstance(workspace, dict) else []
    if not isinstance(patterns, list):
        return []
    members: set[Path] = set()
    for pattern in patterns:
        if not isinstance(pattern, str):
            continue
        for candidate in root.glob(pattern):
            manifest = candidate / "pyproject.toml"
            if (
                candidate.is_dir()
                and manifest.is_file()
                and candidate.resolve().is_relative_to(root)
            ):
                members.add(candidate.resolve())
    return sorted(members)


def _python_unit(
    root: Path, manifest: Path
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    relative_manifest = manifest.relative_to(root).as_posix()
    text = manifest.read_text(encoding="utf-8")
    commands: list[dict[str, str]] = []
    try:
        document = (
            tomllib.loads(text)
            if manifest.name == "pyproject.toml"
            else {}
        )
    except tomllib.TOMLDecodeError:
        document = {}
    tool = document.get("tool", {}) if isinstance(document, dict) else {}
    harness = (
        tool.get("ai-coding-harness", {})
        if isinstance(tool, dict)
        else {}
    )
    declared_tasks = (
        harness.get("tasks", {}) if isinstance(harness, dict) else {}
    )
    if isinstance(declared_tasks, dict):
        for name, command in sorted(declared_tasks.items()):
            task_options = command if isinstance(command, dict) else {}
            declared_argv = (
                task_options.get("argv")
                if isinstance(task_options.get("argv"), list)
                else command
            )
            command_text = (
                " ".join(str(item) for item in declared_argv)
                if isinstance(declared_argv, list)
                else str(declared_argv)
            )
            category = _classify_action(name, command_text)
            if category:
                item = {
                    "name": name,
                    "category": category,
                    "command": command_text,
                    "argv": (
                        [str(value) for value in declared_argv]
                        if isinstance(declared_argv, list)
                        else shlex.split(command_text)
                    ),
                    "raw_command": command_text,
                    "source": (
                        f"{relative_manifest}"
                        f"#tool.ai-coding-harness.tasks.{name}"
                    ),
                }
                reports = task_options.get("required_reports")
                if isinstance(reports, list) and all(
                    isinstance(value, str) and value for value in reports
                ):
                    item["required_reports"] = reports
                commands.append(item)
    dependency_values: list[str] = []
    if isinstance(document, dict):
        project = document.get("project", {})
        if isinstance(project, dict) and isinstance(project.get("dependencies"), list):
            dependency_values.extend(str(item) for item in project["dependencies"])
        groups = document.get("dependency-groups", {})
        if isinstance(groups, dict):
            for values in groups.values():
                if isinstance(values, list):
                    dependency_values.extend(str(item) for item in values)
    if manifest.name == "requirements.txt":
        dependency_values.extend(
            line.strip()
            for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
    if not commands and any(
        re.match(r"(?i)^pytest(?:\[|[<>=~! ]|$)", item.strip("\"' "))
        for item in dependency_values
    ):
        argv = (
            ["uv", "run", "python", "-m", "pytest"]
            if (manifest.parent / "uv.lock").is_file()
            else ["python", "-m", "pytest"]
        )
        commands.append(
            {
                "name": "test",
                "category": "test",
                "command": " ".join(argv),
                "argv": argv,
                "raw_command": " ".join(argv),
                "source": f"{relative_manifest}#pytest-dependency",
            }
        )
    unit = {
        "id": f"python-{_slug(manifest.parent.relative_to(root).as_posix())}",
        "type": "python",
        "root": (
            manifest.parent.relative_to(root).as_posix()
            if manifest.parent != root
            else "."
        ),
        "manifest": relative_manifest,
        "commands": commands,
    }
    gaps = []
    if not commands:
        gaps.append(
            {
                "code": "ACTION_CLASSIFICATION_UNRESOLVED",
                "severity": "source-backed",
                "source": relative_manifest,
                "reason": "Python manifest declares no supported validation command; Bootstrap may create an empty Task catalog",
            }
        )
    return unit, gaps


def _node_unit(
    root: Path, manifest: Path
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    scripts = _package_scripts(manifest)
    relative_manifest = manifest.relative_to(root).as_posix()
    commands = [
        {
            "name": name,
            "category": category,
            "command": f"npm run {name}",
            "argv": ["npm", "run", name],
            "raw_command": str(command),
            "source": f"{relative_manifest}#scripts.{name}",
        }
        for name, command in sorted(scripts.items())
        if (category := _classify_action(name, str(command))) is not None
    ]
    unit = {
        "id": f"node-{_slug(manifest.parent.relative_to(root).as_posix())}",
        "type": "node",
        "root": (
            manifest.parent.relative_to(root).as_posix()
            if manifest.parent != root
            else "."
        ),
        "manifest": relative_manifest,
        "commands": commands,
    }
    gaps = [
        {
            "code": "ACTION_CLASSIFICATION_UNRESOLVED",
            "severity": "source-backed",
            "blocks_plan": True,
            "source": f"{relative_manifest}#scripts.{name}",
            "reason": "manifest script cannot be classified deterministically",
        }
        for name, command in sorted(scripts.items())
        if _classify_action(name, str(command)) is None
    ]
    if not commands:
        gaps.append(
            {
                "code": "ACTION_CLASSIFICATION_UNRESOLVED",
                "severity": "source-backed",
                "blocks_plan": bool(scripts),
                "source": relative_manifest,
                "reason": (
                    "Node manifest scripts cannot be classified deterministically"
                    if scripts
                    else "Node manifest declares no scripts; Bootstrap may create an empty Task catalog"
                ),
            }
        )
    return unit, gaps


def _workflow_jobs(document: dict[str, Any], relative_path: str) -> list[dict[str, Any]]:
    jobs = document.get("jobs", {})
    if not isinstance(jobs, dict):
        return []
    result = []
    for job_id, job in sorted(jobs.items()):
        if not isinstance(job_id, str) or not isinstance(job, dict):
            continue
        commands = []
        for step in job.get("steps", []):
            if isinstance(step, dict) and isinstance(step.get("run"), str):
                commands.append(step["run"])
        category = _classify_action(
            f"{job_id} {job.get('name', '')}", "\n".join(commands)
        ) or "ci"
        result.append(
            {
                "id": _slug(job_id),
                "category": category,
                "source": f"{relative_path}#jobs.{job_id}",
                "commands": commands,
            }
        )
    return result


def _referenced_scripts(root: Path, sources: list[str]) -> list[str]:
    referenced: set[str] = set()
    pattern = re.compile(r"(?:^|[\s\"'])(scripts[/\\][A-Za-z0-9_./\\-]+)")
    for source in sources:
        for match in pattern.findall(source):
            candidate = match.replace("\\", "/").rstrip(";,)")
            path = (root / candidate).resolve()
            if path.is_file() and path.is_relative_to(root):
                referenced.add(path.relative_to(root).as_posix())
    return sorted(referenced)


def summarize_discovery(
    facts: dict[str, Any], *, ignored_paths: set[str] | None = None
) -> dict[str, Any]:
    """Return facts whose change makes an approved Plan stale."""

    ignored = {path.replace("\\", "/") for path in (ignored_paths or set())}
    return {
        "project_types": facts.get("project_types", []),
        "project_units": facts.get("project_units", []),
        "fact_sources": facts.get("fact_sources", {}),
        "source_roots": facts.get("source_roots", []),
        "test_roots": facts.get("test_roots", []),
        "package_scripts": facts.get("package_scripts", {}),
        "referenced_scripts": facts.get("referenced_scripts", []),
        "workflows": [
            workflow
            for workflow in facts.get("workflows", [])
            if workflow.get("path") not in ignored
        ],
        "gaps": facts.get("gaps", []),
    }


def classify_repository_model(root: Path) -> dict[str, Any]:
    """Classify repository adoption from governance facts, never from Git alone."""

    repository = root.resolve()
    reasons: list[str] = []
    agents = repository / "AGENTS.md"
    if agents.is_file():
        agents_text = agents.read_text(encoding="utf-8")
        marker_start = agents_text.find(HARNESS_MARKER_START)
        marker_end = agents_text.find(HARNESS_MARKER_END)
        if marker_start >= 0 and marker_end >= marker_start:
            marker_end += len(HARNESS_MARKER_END)
            agents_text = (
                agents_text[:marker_start] + agents_text[marker_end:]
            )
        if agents_text.strip():
            reasons.append("AGENTS.md")

    workflow_root = repository / ".github" / "workflows"
    if workflow_root.is_dir() and any(
        path.is_file()
        for path in (
            *workflow_root.glob("*.yml"),
            *workflow_root.glob("*.yaml"),
        )
    ):
        reasons.append(".github/workflows")

    package_json = repository / "package.json"
    if _package_scripts(package_json):
        reasons.append("package.json#scripts")

    mode = "adopt" if reasons else "bootstrap"
    return {
        "model": "Gray" if mode == "adopt" else "Blue",
        "mode": mode,
        "source_refs": sorted(reasons),
        "reason": (
            "existing governance, automation, or repository instructions must be preserved"
            if reasons
            else "no existing governance, CI, delivery entrypoint, or user instruction was found"
        ),
    }


def discover_repository(root: Path) -> dict[str, Any]:
    """Return source-backed facts without modifying the repository."""

    root = root.resolve()
    project_types: list[str] = []
    fact_sources: dict[str, str] = {}
    project_units: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []

    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        project_types.append("python")
        fact_sources["python"] = "pyproject.toml"
        unit, unit_gaps = _python_unit(root, pyproject)
        project_units.append(unit)
        gaps.extend(unit_gaps)
        try:
            pyproject_document = tomllib.loads(
                pyproject.read_text(encoding="utf-8")
            )
        except tomllib.TOMLDecodeError:
            pyproject_document = {}
        for member in _python_workspace_members(root, pyproject_document):
            unit, unit_gaps = _python_unit(root, member / "pyproject.toml")
            project_units.append(unit)
            gaps.extend(unit_gaps)
    elif (root / "requirements.txt").is_file():
        project_types.append("python")
        fact_sources["python"] = "requirements.txt"
        requirements = root / "requirements.txt"
        unit, unit_gaps = _python_unit(root, requirements)
        project_units.append(unit)
        gaps.extend(unit_gaps)

    package_json = root / "package.json"
    package = _package_document(package_json)
    scripts = _package_scripts(package_json)
    if package_json.is_file():
        project_types.append("node")
        fact_sources["node"] = "package.json"
        if scripts or not package.get("workspaces"):
            unit, unit_gaps = _node_unit(root, package_json)
            project_units.append(unit)
            gaps.extend(unit_gaps)
        for member in _workspace_members(root, package):
            unit, unit_gaps = _node_unit(root, member / "package.json")
            project_units.append(unit)
            gaps.extend(unit_gaps)

    workflows: list[dict[str, Any]] = []
    referenced_sources = [
        command.get("raw_command", "")
        for unit in project_units
        for command in unit.get("commands", [])
    ]
    workflow_root = root / ".github" / "workflows"
    if workflow_root.is_dir():
        for path in sorted((*workflow_root.glob("*.yml"), *workflow_root.glob("*.yaml"))):
            document = _workflow_document(path)
            triggers = _workflow_triggers(document)
            relative_path = path.relative_to(root).as_posix()
            jobs = _workflow_jobs(document, relative_path)
            for job in jobs:
                referenced_sources.extend(job["commands"])
            workflows.append(
                {
                    "path": relative_path,
                    "triggers": triggers,
                    "controlled_entry": "workflow_dispatch" in triggers,
                    "protected_trigger_uncontrolled": bool(
                        PROTECTED_TRIGGERS.intersection(triggers)
                    )
                    or (
                        "workflow_call" in triggers
                        and "workflow_dispatch" not in triggers
                    ),
                    "jobs": jobs,
                }
            )

    for source, (code, system) in UNSUPPORTED_SOURCES.items():
        path = root / source
        if path.is_file():
            gaps.append(
                {
                    "code": code,
                    "severity": "source-backed",
                    "blocks_plan": False,
                    "source": source,
                    "reason": f"{system} is detected but has no deterministic Adapter",
                }
            )

    referenced_scripts = _referenced_scripts(root, referenced_sources)
    scripts_root = root / "scripts"
    if scripts_root.is_dir():
        for path in sorted(item for item in scripts_root.rglob("*") if item.is_file()):
            relative = path.relative_to(root).as_posix()
            if relative not in referenced_scripts:
                gaps.append(
                    {
                        "code": "ACTION_CLASSIFICATION_UNRESOLVED",
                        "severity": "source-backed",
                        "blocks_plan": False,
                        "source": relative,
                        "reason": "repository script is not referenced by a manifest or Workflow",
                    }
                )

    source_roots = [
        name
        for name in ("src", "lib", "app", "packages")
        if (root / name).is_dir()
    ]
    test_roots = [
        name for name in ("tests", "test", "__tests__") if (root / name).is_dir()
    ]

    return {
        "repository_root": str(root),
        "repository_model": classify_repository_model(root),
        "project_types": project_types,
        "project_units": project_units,
        "fact_sources": fact_sources,
        "agents": {
            "exists": (root / "AGENTS.md").is_file(),
            "path": "AGENTS.md",
        },
        "harness": {
            "exists": (root / ".harness").is_dir(),
            "path": ".harness",
        },
        "source_roots": source_roots,
        "test_roots": test_roots,
        "package_scripts": scripts,
        "referenced_scripts": referenced_scripts,
        "workflows": workflows,
        "gaps": gaps
        or (
            [
                {
                    "code": "CONFIG_INVALID",
                    "severity": "source-backed",
                    "blocks_plan": False,
                    "source": ".",
                    "reason": "no supported project manifest was found",
                }
            ]
            if not project_types
            else []
        ),
    }
