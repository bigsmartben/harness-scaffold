"""Build deterministic, digest-bound Harness plans and approvals."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .branching import default_branch_gate

import yaml

from .artifacts import (
    SCHEMA_VERSION,
    artifact_digest,
    attach_digest,
    canonical_digest,
    content_digest,
    path_digest,
)
from .contracts import validate_config
from .discovery import summarize_discovery
from .templates import render_template, replace_marked_block


CONFIG_PATHS = (
    ".harness/harness.yaml",
    ".harness/boundaries.yaml",
    ".harness/tools.yaml",
    ".harness/tasks.yaml",
    ".harness/impact.yaml",
    ".harness/pipelines/merge.yaml",
    ".harness/pipelines/publish.yaml",
    ".harness/.gitignore",
)
DELIVERY_CATEGORIES = {"push", "merge", "publish", "release", "deploy"}
SCOPE_ORDER = ("inspect", "affected", "contract", "integration", "full", "publish")


def _yaml_text(document: dict[str, Any]) -> str:
    return yaml.safe_dump(
        document,
        allow_unicode=True,
        sort_keys=False,
        width=1000,
    )


def _supports_scope(category: str) -> str:
    return {
        "lint": "affected",
        "validation": "contract",
        "test": "contract",
        "build": "integration",
        "ci": "full",
        "package": "integration",
        "push": "publish",
        "merge": "publish",
        "publish": "publish",
        "release": "publish",
        "deploy": "publish",
    }[category]


def _automation(category: str) -> tuple[str, bool]:
    if category in DELIVERY_CATEGORIES:
        return "critical", False
    if category in {"build", "ci", "package"}:
        return "expensive", False
    return "routine", True


def _task_id(category: str, unit_id: str, command_name: str, index: int) -> str:
    command_slug = "".join(
        character if character.isalnum() else "-" for character in command_name.lower()
    ).strip("-")
    base = f"{category}:{unit_id}"
    return base if index == 0 else f"{base}:{command_slug or index}"


def _catalogs(
    facts: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    tools: list[dict[str, Any]] = [
        {
            "id": "repository-search",
            "type": "cli",
            "purpose": "repository-text-search",
            "capability": "repository-search",
            "action_semantics": "ordinary",
            "entrypoint": "rg",
            "invocation_mode": "direct",
            "version_source": {"command": "rg", "arguments": ["--version"]},
            "working_directory": "repository-root",
            "use_when": ["search source, tests, or configuration"],
            "do_not_use_when": ["execute project validation"],
            "inputs": {},
            "outputs": {},
            "constraints": ["read-only"],
        }
    ]
    tasks: list[dict[str, Any]] = [
        {
            "id": "push:branch",
            "category": "push",
            "automation_level": "critical",
            "auto_allowed": False,
            "source": ".harness/adapters/git-remote.yaml#origin",
            "backend": "git-remote",
            "working_directory": "repository-root",
            "supports_scope": "publish",
            "timeout": "2m",
            "outputs": {"report": ".harness/reports/push-branch.json"},
        }
    ]
    tools.append(
        {
            "id": "git-push-branch",
            "type": "project-action",
            "purpose": "push-confirmed-commit-to-remote-branch",
            "capability": "project-push",
            "action_semantics": "push",
            "invocation_mode": "managed",
            "task_ref": "push:branch",
            "working_directory": "repository-root",
            "use_when": ["push an exact confirmed commit to an exact remote branch"],
            "do_not_use_when": ["force push, merge, publish, release, or deploy"],
            "inputs": {
                "scope": "publish",
                "target": "remote-branch",
                "commit_sha": "git-commit",
            },
            "outputs": {"evidence": ".harness/reports/push-branch.json"},
            "constraints": [
                "current confirmation required",
                "no force push",
                "git-remote backend only",
            ],
        }
    )
    rules: list[dict[str, Any]] = [
        {
            "id": "docs-only",
            "paths": ["**/*.md"],
            "validation_level": "inspect",
            "reason": "documentation changes require structural inspection",
        }
    ]

    for unit in facts.get("project_units", []):
        runtime = unit.get("type")
        runtime_entrypoint = "python" if runtime == "python" else "node"
        tools.append(
            {
                "id": f"runtime-{unit['id']}",
                "type": "runtime",
                "purpose": f"run-read-only-{runtime}-analysis-for-{unit['id']}",
                "capability": f"{runtime}-analysis",
                "action_semantics": "ordinary",
                "entrypoint": runtime_entrypoint,
                "invocation_mode": "direct",
                "version_source": {
                    "command": runtime_entrypoint,
                    "arguments": ["--version"],
                },
                "working_directory": unit["root"],
                "use_when": [f"inspect {unit['id']} without CI/CD semantics"],
                "do_not_use_when": [
                    "run test, build, CI, package, or delivery actions"
                ],
                "inputs": {"script": "read-only"},
                "outputs": {"result": "text-or-json"},
                "constraints": ["ordinary analysis only"],
            }
        )
        category_counts: dict[str, int] = {}
        unit_tasks: list[dict[str, str]] = []
        for command in unit.get("commands", []):
            category = command["category"]
            index = category_counts.get(category, 0)
            category_counts[category] = index + 1
            task_id = _task_id(category, unit["id"], command["name"], index)
            automation_level, auto_allowed = _automation(category)
            tasks.append(
                {
                    "id": task_id,
                    "category": category,
                    "automation_level": automation_level,
                    "auto_allowed": auto_allowed,
                    "command_source": command["source"],
                    "command": command["argv"],
                    "backend": "local",
                    "working_directory": unit["root"],
                    "supports_scope": _supports_scope(category),
                    "timeout": "10m" if automation_level != "routine" else "5m",
                    "outputs": {
                        "report": f".harness/reports/{task_id.replace(':', '-')}.json"
                    },
                }
            )
            tools.append(
                {
                    "id": f"run-{task_id.replace(':', '-')}",
                    "type": "project-action",
                    "purpose": f"run-{category}-for-{unit['id']}",
                    "capability": f"project-{category}",
                    "action_semantics": category,
                    "invocation_mode": "managed",
                    "task_ref": task_id,
                    "working_directory": "repository-root",
                    "use_when": [f"run registered {category} for {unit['id']}"],
                    "do_not_use_when": ["perform ordinary repository inspection"],
                    "inputs": {"scope": "validation-level"},
                    "outputs": {"evidence": "Harness Evidence"},
                    "constraints": ["invoke only through Harness"],
                }
            )
            if category not in DELIVERY_CATEGORIES:
                unit_tasks.append(
                    {"id": task_id, "scope": _supports_scope(category)}
                )
        if unit_tasks:
            unit_root = unit["root"]
            paths = (
                [unit["manifest"], "src/**", "tests/**"]
                if unit_root == "."
                else [f"{unit_root}/**"]
            )
            level = max(
                (item["scope"] for item in unit_tasks),
                key=SCOPE_ORDER.index,
            )
            rules.append(
                {
                    "id": f"unit-{unit['id']}",
                    "paths": paths,
                    "validation_level": level,
                    "tasks": [item["id"] for item in unit_tasks],
                    "reason": f"{unit['id']} changes require its source-backed Tasks",
                }
            )

    for workflow in facts.get("workflows", []):
        for job in workflow.get("jobs", []):
            category = job["category"]
            workflow_slug = Path(workflow["path"]).stem.lower().replace("_", "-")
            unit_id = f"github-{workflow_slug}-{job['id']}"
            task_id = f"{category}:{unit_id}"
            automation_level, auto_allowed = _automation(category)
            tasks.append(
                {
                    "id": task_id,
                    "category": category,
                    "automation_level": automation_level,
                    "auto_allowed": auto_allowed,
                    "source": job["source"],
                    "backend": "github-actions",
                    "working_directory": "repository-root",
                    "supports_scope": _supports_scope(category),
                    "timeout": "30m",
                    "outputs": {
                        "report": f".harness/reports/{task_id.replace(':', '-')}.json"
                    },
                }
            )
            tools.append(
                {
                    "id": f"run-{task_id.replace(':', '-')}",
                    "type": "project-action",
                    "purpose": f"run-{category}-from-{workflow_slug}",
                    "capability": f"github-{category}",
                    "action_semantics": category,
                    "invocation_mode": "managed",
                    "task_ref": task_id,
                    "working_directory": "repository-root",
                    "use_when": [f"run {job['source']} through GitHub Actions"],
                    "do_not_use_when": ["run an unregistered Workflow or job"],
                    "inputs": {"scope": "validation-level"},
                    "outputs": {"evidence": "Harness Evidence"},
                    "constraints": ["Adapter dispatch and platform evidence required"],
                }
            )
            rules.append(
                {
                    "id": f"workflow-{unit_id}",
                    "paths": [workflow["path"]],
                    "validation_level": _supports_scope(category),
                    "tasks": [task_id],
                    "reason": f"{job['source']} is this Task's source",
                }
            )

    return tools, tasks, rules


def _render_context(facts: dict[str, Any], mode: str) -> dict[str, str]:
    tools, tasks, rules = _catalogs(facts)
    validation_commands = [
        command["command"]
        for unit in facts.get("project_units", [])
        for command in unit.get("commands", [])
        if command["category"] not in DELIVERY_CATEGORIES
    ]
    validation_tasks = [
        task["id"] for task in tasks if task["category"] not in DELIVERY_CATEGORIES
    ]
    delivery_tasks = [
        task["id"] for task in tasks if task["category"] in DELIVERY_CATEGORIES
    ]
    roots = sorted(
        {
            *(f"{item}/**" for item in facts.get("source_roots", [])),
            *(f"{item}/**" for item in facts.get("test_roots", [])),
            *(
                (
                    unit["manifest"]
                    if unit.get("root") == "."
                    else f"{unit['root']}/**"
                )
                for unit in facts.get("project_units", [])
            ),
        }
    ) or ["**/*"]
    fact_sources = {
        key: value for key, value in sorted(facts.get("fact_sources", {}).items())
    }
    return {
        "harness_yaml": _yaml_text(
            {
                "schema_version": SCHEMA_VERSION,
                "mode": "adopt" if mode == "adopt" else "bootstrap",
                "delivery_authority": "ci-platform",
                "fact_sources": fact_sources,
            }
        ),
        "boundaries_yaml": _yaml_text(
            {
                "branch_gate": default_branch_gate(),
            }
        ),
        "tools_yaml": _yaml_text({"tools": tools}),
        "tasks_yaml": _yaml_text({"tasks": tasks}),
        "impact_yaml": _yaml_text({"rules": rules}),
        "merge_pipeline_yaml": _yaml_text(
            {
                "id": "merge:default",
                "kind": "merge",
                "requires_independent_confirmation": True,
                "stages": [
                    {
                        "id": "validate",
                        "tasks": validation_tasks,
                        "requires_evidence": True,
                    }
                ],
            }
        ),
        "publish_pipeline_yaml": _yaml_text(
            {
                "id": "publish:default",
                "kind": "publish",
                "requires_independent_confirmation": True,
                "stages": [
                    {
                        "id": "publish",
                        "tasks": delivery_tasks,
                        "requires_evidence": False,
                    }
                ],
            }
        ),
        "workflow_path": (
            facts.get("workflows", [{}])[0].get(
                "path", ".github/workflows/harness.yml"
            )
            if facts.get("workflows")
            else ".github/workflows/harness.yml"
        ),
        "git_ref": "current-branch",
        "validation_command": (
            validation_commands[0] if validation_commands else "exit 64"
        ),
    }


def _fact_source_state(root: Path, facts: dict[str, Any]) -> dict[str, str]:
    sources = set(facts.get("fact_sources", {}).values())
    sources.update(
        unit["manifest"]
        for unit in facts.get("project_units", [])
        if isinstance(unit.get("manifest"), str)
    )
    sources.update(
        workflow["path"]
        for workflow in facts.get("workflows", [])
        if isinstance(workflow.get("path"), str)
    )
    sources.update(
        path
        for path in facts.get("referenced_scripts", [])
        if isinstance(path, str)
    )
    sources.update(
        str(gap["source"]).split("#", 1)[0]
        for gap in facts.get("gaps", [])
        if isinstance(gap, dict)
        and isinstance(gap.get("source"), str)
        and (root / str(gap["source"]).split("#", 1)[0]).is_file()
    )
    return {
        source: path_digest(root / source)
        for source in sorted(source for source in sources if isinstance(source, str))
    }


def _existing_schema_version(root: Path) -> str | None:
    path = root / ".harness" / "harness.yaml"
    if not path.is_file():
        return None
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return "invalid"
    return document.get("schema_version") if isinstance(document, dict) else "invalid"


def _leaf_fields(value: Any, prefix: str = "") -> list[str]:
    """Return deterministic field paths for a preservation-only Drift Plan."""

    if isinstance(value, dict):
        if not value:
            return [prefix or "$"]
        result: list[str] = []
        for key in sorted(value, key=str):
            child = f"{prefix}.{key}" if prefix else str(key)
            result.extend(_leaf_fields(value[key], child))
        return result
    if isinstance(value, list):
        if not value:
            return [prefix or "$"]
        result = []
        for index, item in enumerate(value):
            label = (
                str(item["id"])
                if isinstance(item, dict) and isinstance(item.get("id"), str)
                else str(index)
            )
            child = f"{prefix}.{label}" if prefix else label
            result.extend(_leaf_fields(item, child))
        return result
    return [prefix or "$"]


def _preservation_drift(root: Path, relative_path: str) -> list[dict[str, str]]:
    path = root / relative_path
    if not path.is_file():
        return []
    if path.suffix in {".yaml", ".yml"}:
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            fields = ["$"]
        else:
            fields = _leaf_fields(document)
    else:
        fields = ["content"]
    return [
        {
            "path": relative_path,
            "field": field,
            "decision": "preserve",
            "reason": "valid 0.3 custom configuration is authoritative",
        }
        for field in fields
    ]


def _planned_content(
    root: Path,
    action: dict[str, Any],
    assets: Path,
    context: dict[str, str],
) -> str:
    template = (assets / action["template"]).resolve()
    if not template.is_relative_to(assets) or not template.is_file():
        raise FileNotFoundError(action["template"])
    rendered = render_template(template.read_text(encoding="utf-8"), context)
    if action["merge"] == "replace-marked-block":
        target = root / action["path"]
        current = target.read_text(encoding="utf-8") if target.is_file() else ""
        return replace_marked_block(current, rendered)
    return rendered


def build_plan(
    facts: dict[str, Any],
    mode: str,
    assets: Path | None = None,
) -> dict[str, Any]:
    """Build a fully digest-bound Plan without mutating the repository."""

    if mode not in {"adopt", "bootstrap", "audit", "update"}:
        raise ValueError(f"unsupported mode: {mode}")

    root = Path(facts.get("repository_root") or ".").resolve()
    assets = (assets or Path(__file__).parents[2] / "assets").resolve()
    selected_backends = set(facts.get("selected_backends", ["local"]))
    actions: list[dict[str, Any]] = []
    preserve = [
        workflow["path"]
        for workflow in facts.get("workflows", [])
        if isinstance(workflow.get("path"), str)
    ]
    drift: list[dict[str, str]] = []
    blockers = {
        gap["code"]
        for gap in facts.get("gaps", [])
        if gap.get("blocks_plan") is True
        and gap.get("code")
        in {
            "TOOL_NOT_REGISTERED",
            "ACTION_CLASSIFICATION_UNRESOLVED",
            "CONFIG_INVALID",
        }
    }
    if mode == "adopt" and any(
        workflow.get("protected_trigger_uncontrolled")
        for workflow in facts.get("workflows", [])
    ):
        blockers.add("PROTECTED_TRIGGER_UNCONTROLLED")

    if mode in {"adopt", "bootstrap", "update"}:
        actions.append(
            {
                "action": "update" if (root / "AGENTS.md").is_file() else "create",
                "path": "AGENTS.md",
                "template": "scaffold/AGENTS.md",
                "merge": "replace-marked-block",
            }
        )
        config_issues = (
            validate_config(root / ".harness", assets / "schemas")
            if mode == "update" and (root / ".harness").is_dir()
            else []
        )
        if mode == "update" and (
            _existing_schema_version(root) != SCHEMA_VERSION or config_issues
        ):
            blockers.update({"CONFIG_INVALID", "HANDOFF_REQUIRED"})
            if config_issues:
                drift.extend(
                    {
                        "path": issue.path.split("#", 1)[0],
                        "field": (
                            issue.path.split("#", 1)[1]
                            if "#" in issue.path
                            else "*"
                        ),
                        "decision": "block",
                        "reason": issue.message,
                    }
                    for issue in config_issues
                )
            else:
                drift.append(
                    {
                        "path": ".harness/harness.yaml",
                        "field": "schema_version",
                        "decision": "block",
                        "reason": "Update does not migrate pre-0.3 configuration; run Adopt or Bootstrap",
                    }
                )
        elif mode == "update":
            for path in CONFIG_PATHS:
                preserve.append(path)
                drift.extend(_preservation_drift(root, path))
            adapters = root / ".harness" / "adapters"
            if adapters.is_dir():
                for adapter in sorted(adapters.rglob("*.yaml")):
                    relative = adapter.relative_to(root).as_posix()
                    preserve.append(relative)
                    drift.extend(_preservation_drift(root, relative))
        else:
            for path in CONFIG_PATHS:
                exists = (root / path).is_file()
                actions.append(
                    {
                        "action": "update" if exists else "create",
                        "path": path,
                        "template": f"scaffold/{path}",
                        "merge": "replace",
                    }
                )
                drift.append(
                    {
                        "path": path,
                        "field": "*",
                        "decision": "update" if exists else "create",
                        "reason": f"{mode} establishes the complete 0.3 contract",
                    }
                )
            actions.append(
                {
                    "action": (
                        "update"
                        if (root / ".harness/adapters/local.yaml").is_file()
                        else "create"
                    ),
                    "path": ".harness/adapters/local.yaml",
                    "template": "backends/local/adapter.yaml",
                    "merge": "replace",
                }
            )
            actions.append(
                {
                    "action": (
                        "update"
                        if (root / ".harness/adapters/git-remote.yaml").is_file()
                        else "create"
                    ),
                    "path": ".harness/adapters/git-remote.yaml",
                    "template": "backends/git-remote/adapter.yaml",
                    "merge": "replace",
                }
            )
            needs_github = (mode == "adopt" and bool(facts.get("workflows"))) or (
                mode == "bootstrap" and "github-actions" in selected_backends
            )
            if needs_github:
                actions.append(
                    {
                        "action": (
                            "update"
                            if (root / ".harness/adapters/github-actions.yaml").is_file()
                            else "create"
                        ),
                        "path": ".harness/adapters/github-actions.yaml",
                        "template": "backends/github-actions/adapter.yaml",
                        "merge": "replace",
                    }
                )
            if mode == "bootstrap" and "github-actions" in selected_backends:
                actions.append(
                    {
                        "action": (
                            "update"
                            if (root / ".github/workflows/harness.yml").is_file()
                            else "create"
                        ),
                        "path": ".github/workflows/harness.yml",
                        "template": "backends/github-actions/.github/workflows/harness.yml",
                        "merge": "replace",
                    }
                )

    context = _render_context(facts, mode)
    for action in actions:
        target = root / action["path"]
        action["before_digest"] = path_digest(target)
        action["after_digest"] = content_digest(
            _planned_content(root, action, assets, context)
        )

    action_paths = {action["path"] for action in actions}
    source_facts = summarize_discovery(facts, ignored_paths=action_paths)
    source_state = _fact_source_state(root, facts)
    source_state.update(
        {
            relative: path_digest(root / relative)
            for relative in preserve
            if relative not in action_paths and (root / relative).is_file()
        }
    )
    plan = {
        "artifact_type": "plan",
        "schema_version": SCHEMA_VERSION,
        "plan_type": mode,
        "repository_root": str(root),
        "read_only": mode == "audit",
        "source_facts_digest": canonical_digest(source_facts),
        "source_facts": source_facts,
        "source_state": dict(sorted(source_state.items())),
        "write_scope": sorted(action_paths),
        "actions": actions,
        "preserve": sorted(set(preserve)),
        "render_context": context,
        "blocker_codes": sorted(blockers),
        "drift": drift,
    }
    return attach_digest(plan, "plan_digest")


def create_plan_approval(
    plan: dict[str, Any],
    confirmed_at: str | None = None,
) -> dict[str, Any]:
    """Create the separate Approval after explicit user confirmation."""

    if artifact_digest(plan, "plan_digest") != plan.get("plan_digest"):
        raise ValueError("PLAN_STALE: plan digest does not match plan content")
    return {
        "artifact_type": "plan-approval",
        "schema_version": SCHEMA_VERSION,
        "plan_digest": plan["plan_digest"],
        "confirmation_status": "confirmed",
        "confirmed_at": confirmed_at
        or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
