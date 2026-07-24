"""Load and validate committed Harness configuration contracts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource


CONFIG_SCHEMAS = {
    "harness.yaml": "harness.schema.json",
    "boundaries.yaml": "boundaries.schema.json",
    "tools.yaml": "tools.schema.json",
    "tasks.yaml": "tasks.schema.json",
    "impact.yaml": "impact.schema.json",
}
REQUIRED_PIPELINES = ("merge.yaml", "publish.yaml")


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    path: str
    message: str


def _load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def blocker_codes(schema_dir: Path) -> tuple[str, ...]:
    """Return the canonical blocker-code enumeration from the shared schema."""

    schema = _load_json(schema_dir / "common.schema.json")
    return tuple(schema["$defs"]["blockerCode"]["enum"])


def _yaml_document(path: Path, relative_path: str, issues: list[ValidationIssue]) -> Any:
    try:
        document = _load_yaml(path)
    except yaml.YAMLError as exc:
        issues.append(ValidationIssue("YAML_INVALID", relative_path, str(exc)))
        return None
    if document is None:
        issues.append(ValidationIssue("CONFIG_INVALID", relative_path, "document is empty"))
        return None
    return document


def _validate_document(
    document: Any,
    relative_path: str,
    schema_path: Path,
    registry: Registry,
) -> list[ValidationIssue]:
    schema = _load_json(schema_path)
    validator = Draft202012Validator(schema, registry=registry)
    result: list[ValidationIssue] = []
    for error in sorted(validator.iter_errors(document), key=lambda item: list(item.path)):
        location = "/".join(str(part) for part in error.absolute_path)
        issue_path = f"{relative_path}#{location}" if location else relative_path
        result.append(ValidationIssue("SCHEMA_INVALID", issue_path, error.message))
    return result


def validate_config(
    config_dir: Path, schema_dir: Path
) -> list[ValidationIssue]:
    """Validate five config files, pipelines, and cross-file references."""

    issues: list[ValidationIssue] = []
    documents: dict[str, Any] = {}
    registry = Registry()

    for schema_path in schema_dir.glob("*.schema.json"):
        schema = _load_json(schema_path)
        if schema_id := schema.get("$id"):
            registry = registry.with_resource(
                schema_id, Resource.from_contents(schema)
            )

    for filename, schema_name in CONFIG_SCHEMAS.items():
        path = config_dir / filename
        if not path.is_file():
            issues.append(
                ValidationIssue("CONFIG_FILE_MISSING", filename, "required file is missing")
            )
            continue
        document = _yaml_document(path, filename, issues)
        if document is None:
            continue

        documents[filename] = document
        schema_path = schema_dir / schema_name
        issues.extend(_validate_document(document, filename, schema_path, registry))

    pipeline_schema_path = schema_dir / "pipeline.schema.json"
    if pipeline_schema_path.is_file():
        for filename in REQUIRED_PIPELINES:
            path = config_dir / "pipelines" / filename
            relative_path = f"pipelines/{filename}"
            if not path.is_file():
                issues.append(
                    ValidationIssue(
                        "CONFIG_FILE_MISSING", relative_path, "required file is missing"
                    )
                )
                continue
            document = _yaml_document(path, relative_path, issues)
            if document is None:
                continue
            documents[relative_path] = document
            issues.extend(
                _validate_document(
                    document, relative_path, pipeline_schema_path, registry
                )
            )

    task_document = documents.get("tasks.yaml")
    task_items = task_document.get("tasks", []) if isinstance(task_document, dict) else []
    tasks = {
        item["id"]
        for item in task_items
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    tools = documents.get("tools.yaml")
    tool_items = tools.get("tools", []) if isinstance(tools, dict) else []
    tool_ids = {
        item["id"]
        for item in tool_items
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    server_ids = {
        item["id"]
        for item in tool_items
        if isinstance(item, dict)
        and item.get("type") == "mcp-server"
        and isinstance(item.get("id"), str)
    }
    if len(tool_ids) != len(
        [item for item in tool_items if isinstance(item, dict) and "id" in item]
    ):
        issues.append(
            ValidationIssue(
                "CONFIG_INVALID", "tools.yaml#tools", "tool ids must be unique"
            )
        )
    if len(tasks) != len(
        [item for item in task_items if isinstance(item, dict) and "id" in item]
    ):
        issues.append(
            ValidationIssue(
                "CONFIG_INVALID", "tasks.yaml#tasks", "task ids must be unique"
            )
        )

    for index, tool in enumerate(tool_items):
        if isinstance(tool, dict) and tool.get("invocation_mode") == "managed":
            task_ref = tool.get("task_ref")
            if task_ref not in tasks:
                issues.append(
                    ValidationIssue(
                        "TASK_REF_UNRESOLVED",
                        f"tools.yaml#tools/{index}/task_ref",
                        f"task_ref {task_ref!r} does not exist in tasks.yaml",
                    )
                )
        if isinstance(tool, dict) and tool.get("type") == "mcp-tool":
            server_ref = tool.get("server_ref")
            if server_ref not in server_ids:
                issues.append(
                    ValidationIssue(
                        "TOOL_REF_UNRESOLVED",
                        f"tools.yaml#tools/{index}/server_ref",
                        f"server_ref {server_ref!r} does not identify an MCP server",
                    )
                )

    for index, rule in enumerate(documents.get("impact.yaml", {}).get("rules", [])):
        if not isinstance(rule, dict):
            continue
        for task_ref in rule.get("tasks", []):
            if task_ref not in tasks:
                issues.append(
                    ValidationIssue(
                        "TASK_REF_UNRESOLVED",
                        f"impact.yaml#rules/{index}/tasks",
                        f"task_ref {task_ref!r} does not exist in tasks.yaml",
                    )
                )

    for filename in REQUIRED_PIPELINES:
        document = documents.get(f"pipelines/{filename}")
        if not isinstance(document, dict):
            continue
        for index, stage in enumerate(document.get("stages", [])):
            for task_ref in stage.get("tasks", []):
                if task_ref not in tasks:
                    issues.append(
                        ValidationIssue(
                            "TASK_REF_UNRESOLVED",
                            f"pipelines/{filename}#stages/{index}/tasks",
                            f"task_ref {task_ref!r} does not exist in tasks.yaml",
                        )
                    )

    merge = documents.get("pipelines/merge.yaml")
    if isinstance(merge, dict) and merge.get("kind") != "merge":
        issues.append(
            ValidationIssue("CONFIG_INVALID", "pipelines/merge.yaml#kind", "must be merge")
        )
    publish = documents.get("pipelines/publish.yaml")
    if isinstance(publish, dict) and publish.get("kind") != "publish":
        issues.append(
            ValidationIssue("CONFIG_INVALID", "pipelines/publish.yaml#kind", "must be publish")
        )

    return issues
