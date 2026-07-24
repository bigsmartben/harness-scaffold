"""Build deterministic Adopt, Bootstrap, Audit, and Update plans."""

from __future__ import annotations

import hashlib
import json
from typing import Any


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


def _task_context(facts: dict[str, Any], mode: str) -> dict[str, str]:
    project_types = facts.get("project_types", [])
    project_type = project_types[0] if project_types else "project"
    source_roots = facts.get("source_roots", [])
    test_roots = facts.get("test_roots", [])
    manifest = facts.get("fact_sources", {}).get(project_type, "project-manifest")
    return {
        "project_mode": mode,
        "project_manifest": manifest,
        "source_scope": f"{source_roots[0]}/**" if source_roots else "**/*",
        "test_scope": f"{test_roots[0]}/**" if test_roots else "tests/**",
        "task_id": f"test:{project_type}",
        "publish_task_id": f"publish:{project_type}",
        "task_report": f"{project_type}-tests.json",
        "command_source": f"{manifest}#test",
        "backend": "local",
        "workflow_path": (
            facts.get("workflows", [{}])[0].get(
                "path", ".github/workflows/harness.yml"
            )
            if facts.get("workflows")
            else ".github/workflows/harness.yml"
        ),
        "git_ref": "current-branch",
        "validation_command": (
            "uv run pytest" if project_type == "python" else "npm test"
        ),
    }


def build_plan(facts: dict[str, Any], mode: str) -> dict[str, Any]:
    if mode not in {"adopt", "bootstrap", "audit", "update"}:
        raise ValueError(f"unsupported mode: {mode}")

    actions: list[dict[str, str]] = []
    blockers: list[str] = []
    selected_backends = set(facts.get("selected_backends", ["local"]))
    if mode in {"adopt", "bootstrap", "update"}:
        agents_action = "update" if facts.get("agents", {}).get("exists") else "create"
        actions.append(
            {
                "action": agents_action,
                "path": "AGENTS.md",
                "template": "scaffold/AGENTS.md",
                "merge": "preserve-existing" if agents_action == "update" else "replace",
            }
        )
        for path in CONFIG_PATHS:
            actions.append(
                {
                    "action": "update" if facts.get("harness", {}).get("exists") else "create",
                    "path": path,
                    "template": f"scaffold/{path}",
                    "merge": "replace",
                }
            )
        project_types = facts.get("project_types", [])
        if project_types:
            actions.append(
                {
                    "action": (
                        "update"
                        if facts.get("harness", {}).get("exists")
                        else "create"
                    ),
                    "path": ".harness/adapters/local.yaml",
                    "template": f"backends/local/{project_types[0]}.yaml",
                    "merge": "replace",
                }
            )
        if mode in {"adopt", "update"} and facts.get("workflows"):
            actions.append(
                {
                    "action": (
                        "update"
                        if facts.get("harness", {}).get("exists")
                        else "create"
                    ),
                    "path": ".harness/adapters/github-actions.yaml",
                    "template": "backends/github-actions/adapter.yaml",
                    "merge": "replace",
                }
            )
        if mode == "bootstrap" and "github-actions" in selected_backends:
            actions.extend(
                [
                    {
                        "action": "create",
                        "path": ".harness/adapters/github-actions.yaml",
                        "template": "backends/github-actions/adapter.yaml",
                        "merge": "replace",
                    },
                    {
                        "action": "create",
                        "path": ".github/workflows/harness.yml",
                        "template": "backends/github-actions/.github/workflows/harness.yml",
                        "merge": "replace",
                    },
                ]
            )

    if mode in {"adopt", "bootstrap"} and not facts.get("project_types"):
        blockers.append("CONFIG_INVALID")
    if mode == "adopt" and any(
        workflow.get("protected_trigger_uncontrolled")
        for workflow in facts.get("workflows", [])
    ):
        blockers.append("PROTECTED_TRIGGER_UNCONTROLLED")

    plan = {
        "plan_type": mode,
        "repository_root": facts.get("repository_root"),
        "read_only": mode == "audit",
        "write_scope": (
            ["AGENTS.md", ".harness/**"]
            + (
                [".github/workflows/harness.yml"]
                if mode == "bootstrap" and "github-actions" in selected_backends
                else []
            )
            if actions
            else []
        ),
        "actions": actions,
        "preserve": [item["path"] for item in facts.get("workflows", [])],
        "render_context": _task_context(facts, "adopt" if mode == "adopt" else "bootstrap"),
        "blocker_codes": blockers,
        "approved": False,
    }
    canonical = json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()
    plan["plan_digest"] = f"sha256:{hashlib.sha256(canonical).hexdigest()}"
    return plan
