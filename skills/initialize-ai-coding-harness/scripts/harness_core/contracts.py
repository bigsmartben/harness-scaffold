"""Load and validate committed Harness configuration contracts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from .artifacts import digest_matches


CONFIG_SCHEMAS = {
    "harness.yaml": "harness.schema.json",
    "boundaries.yaml": "boundaries.schema.json",
    "tools.yaml": "tools.schema.json",
    "tasks.yaml": "tasks.schema.json",
    "impact.yaml": "impact.schema.json",
}
REQUIRED_PIPELINES = ("merge.yaml", "publish.yaml")
_PACKAGED_SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"
DEFAULT_SCHEMA_DIR = (
    _PACKAGED_SCHEMA_DIR
    if _PACKAGED_SCHEMA_DIR.is_dir()
    else Path(__file__).resolve().parents[2] / "assets" / "schemas"
)


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


def _schema_registry(schema_dir: Path) -> Registry:
    registry = Registry()
    for schema_path in schema_dir.glob("*.schema.json"):
        schema = _load_json(schema_path)
        if schema_id := schema.get("$id"):
            registry = registry.with_resource(
                schema_id, Resource.from_contents(schema)
            )
    return registry


def validate_runtime_artifact(
    document: Any, schema_dir: Path
) -> list[ValidationIssue]:
    """Validate one 1.0 runtime artifact, including its canonical digest."""

    registry = _schema_registry(schema_dir)
    issues = _validate_document(
        document,
        "runtime",
        schema_dir / "runtime.schema.json",
        registry,
    )
    if issues or not isinstance(document, dict):
        return issues

    digest_fields = {
        "plan": "plan_digest",
        "work-grant": "grant_digest",
        "change-manifest": "manifest_digest",
        "selection": "selection_digest",
        "task-request": "request_digest",
        "platform-evidence": "platform_evidence_digest",
        "evidence": "evidence_digest",
    }
    digest_field = digest_fields.get(document.get("artifact_type"))
    if digest_field and not digest_matches(document, digest_field):
        issues.append(
            ValidationIssue(
                "DIGEST_INVALID",
                f"runtime#{digest_field}",
                f"{digest_field} does not match canonical artifact content",
            )
        )
    return issues


def validate_governance_artifact(
    document: Any, schema_dir: Path = DEFAULT_SCHEMA_DIR
) -> list[ValidationIssue]:
    """Validate one 1.0 governance artifact and its canonical digest."""

    registry = _schema_registry(schema_dir)
    issues = _validate_document(
        document,
        "governance",
        schema_dir / "governance.schema.json",
        registry,
    )
    if issues or not isinstance(document, dict):
        return issues
    digest_fields = {
        "repository-snapshot": "snapshot_digest",
        "source-facts": "facts_digest",
        "action-graph": "action_graph_digest",
        "governance-rules": "rules_digest",
        "projection-lock": "projection_lock_digest",
        "governance-work-grant": "grant_digest",
        "action-request": "request_digest",
        "confirmation-package": "confirmation_digest",
        "gate-decision": "decision_digest",
        "action-evidence": "evidence_digest",
        "agent-input": "input_digest",
        "agent-output": "output_digest",
        "rule-candidate": "candidate_digest",
        "reconciliation-result": "result_digest",
    }
    digest_field = digest_fields.get(document.get("artifact_type"))
    if digest_field and digest_field in document and not digest_matches(document, digest_field):
        issues.append(
            ValidationIssue(
                "DIGEST_INVALID",
                f"governance#{digest_field}",
                f"{digest_field} does not match canonical artifact content",
            )
        )
    return issues


def validate_governance_bundle(
    bundle: dict[str, Any], schema_dir: Path = DEFAULT_SCHEMA_DIR
) -> list[ValidationIssue]:
    """Validate projection artifacts plus cross-file identity and references."""

    issues: list[ValidationIssue] = []
    required = ("sources", "action_graph", "rules", "projection_lock")
    for key in required:
        document = bundle.get(key)
        if not isinstance(document, dict):
            issues.append(
                ValidationIssue(
                    "CONFIG_FILE_MISSING", key, "required governance artifact is missing"
                )
            )
            continue
        issues.extend(validate_governance_artifact(document, schema_dir))
    if issues:
        return issues

    sources = bundle["sources"]
    graph = bundle["action_graph"]
    rules = bundle["rules"]
    lock = bundle["projection_lock"]
    projection_id = lock["projection_id"]
    expected = {
        "facts_digest": sources["facts_digest"],
        "action_graph_digest": graph["action_graph_digest"],
        "rules_digest": rules["rules_digest"],
    }
    for field, value in expected.items():
        if lock.get(field) != value:
            issues.append(
                ValidationIssue(
                    "EVIDENCE_BINDING_MISMATCH",
                    f"projection_lock#{field}",
                    f"{field} does not match its referenced artifact",
                )
            )
    if graph.get("facts_digest") != sources.get("facts_digest"):
        issues.append(
            ValidationIssue(
                "EVIDENCE_BINDING_MISMATCH",
                "action_graph#facts_digest",
                "Action Graph is not bound to Source Facts",
            )
        )
    if graph.get("snapshot_digest") != sources.get("snapshot_digest"):
        issues.append(
            ValidationIssue(
                "EVIDENCE_BINDING_MISMATCH",
                "action_graph#snapshot_digest",
                "Action Graph and Source Facts use different snapshots",
            )
        )
    if lock.get("snapshot_digest") != sources.get("snapshot_digest"):
        issues.append(
            ValidationIssue(
                "EVIDENCE_BINDING_MISMATCH",
                "projection_lock#snapshot_digest",
                "Projection Lock and Source Facts use different snapshots",
            )
        )
    if (
        lock.get("blockers") != graph.get("blockers")
        or lock.get("ready") is not (not graph.get("blockers"))
    ):
        issues.append(
            ValidationIssue(
                "GOVERNANCE_CONFLICT",
                "projection_lock#ready",
                "Projection readiness must exactly reflect Action Graph blockers",
            )
        )
    action_ids = [item.get("action_id") for item in graph.get("actions", [])]
    if len(action_ids) != len(set(action_ids)):
        issues.append(
            ValidationIssue(
                "TOOL_BINDING_AMBIGUOUS",
                "action_graph#actions",
                "action_id values must be unique",
            )
        )
    fact_refs = {
        ref
        for fact in sources.get("facts", [])
        for ref in fact.get("source_refs", [])
    }
    common = _load_json(schema_dir / "common.schema.json")
    audiences = common["$defs"]["audience"]["enum"]
    subdomains = common["$defs"]["subdomain"]["enum"]
    expected_matrix = set(product(audiences, subdomains))
    observed_matrix = {
        (item.get("audience"), item.get("subdomain"))
        for item in rules.get("matrix", [])
        if isinstance(item, dict)
    }
    if observed_matrix != expected_matrix or len(rules.get("matrix", [])) != len(
        expected_matrix
    ):
        issues.append(
            ValidationIssue(
                "GOVERNANCE_COVERAGE_INCOMPLETE",
                "rules#matrix",
                "audience/subdomain matrix must contain every unique 2 x 6 lane",
            )
        )
    rule_ids = [item.get("rule_id") for item in rules.get("rules", [])]
    if len(rule_ids) != len(set(rule_ids)):
        issues.append(
            ValidationIssue(
                "GOVERNANCE_CONFLICT",
                "rules#rules",
                "rule_id values must be unique",
            )
        )
    covered_lanes = {
        (rule.get("audience"), subdomain)
        for rule in rules.get("rules", [])
        for subdomain in rule.get("subdomains", [])
    }
    if not expected_matrix.issubset(covered_lanes):
        issues.append(
            ValidationIssue(
                "GOVERNANCE_COVERAGE_INCOMPLETE",
                "rules#rules",
                "every audience/subdomain lane needs at least one sourced rule",
            )
        )
    for index, rule in enumerate(rules.get("rules", [])):
        if rule.get("projection_id") != projection_id:
            issues.append(
                ValidationIssue(
                    "GOVERNANCE_PROJECTION_STALE",
                    f"rules#rules/{index}/projection_id",
                    "rule projection_id does not match Projection Lock",
                )
            )
        if rule.get("action_id") is not None and rule.get("action_id") not in action_ids:
            issues.append(
                ValidationIssue(
                    "TOOL_ACTION_UNCLASSIFIED",
                    f"rules#rules/{index}/action_id",
                    "rule references an unknown action_id",
                )
            )
        if rule.get("action_id") is not None and rule.get("action_id") in action_ids:
            action = next(
                item
                for item in graph["actions"]
                if item.get("action_id") == rule.get("action_id")
            )
            if (
                rule.get("invocation") != action.get("invocation")
                or not set(action.get("subdomains", [])).issubset(
                    set(rule.get("subdomains", []))
                )
            ):
                issues.append(
                    ValidationIssue(
                        "TOOL_BINDING_AMBIGUOUS",
                        f"rules#rules/{index}/invocation",
                        "rule invocation and subdomains must match the Action binding",
                    )
                )
        for ref in rule.get("source_refs", []):
            if ref not in fact_refs:
                issues.append(
                    ValidationIssue(
                        "GOVERNANCE_SOURCE_MISSING",
                        f"rules#rules/{index}/source_refs",
                        f"source_ref {ref!r} is absent from Source Facts",
                    )
                )
    return issues


def runtime_artifact_is_valid(document: Any) -> bool:
    """Validate a runtime artifact against the Skill's bundled 1.0 schema."""

    return not validate_runtime_artifact(document, DEFAULT_SCHEMA_DIR)


def validate_config(
    config_dir: Path, schema_dir: Path
) -> list[ValidationIssue]:
    """Validate five config files, pipelines, and cross-file references."""

    issues: list[ValidationIssue] = []
    documents: dict[str, Any] = {}
    registry = _schema_registry(schema_dir)
    action_semantics = set(
        _load_json(schema_dir / "common.schema.json")["$defs"]["actionSemantics"][
            "enum"
        ]
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
    tasks_by_id = {
        item["id"]: item
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
        if not isinstance(tool, dict):
            continue
        semantics = tool.get("action_semantics")
        invocation_mode = tool.get("invocation_mode")
        task_ref = tool.get("task_ref")
        if semantics not in action_semantics:
            issues.extend(
                [
                    ValidationIssue(
                        "ACTION_CLASSIFICATION_UNRESOLVED",
                        f"tools.yaml#tools/{index}/action_semantics",
                        "action_semantics is missing or unsupported",
                    ),
                    ValidationIssue(
                        "HANDOFF_REQUIRED",
                        f"tools.yaml#tools/{index}/action_semantics",
                        "classify the action before execution",
                    ),
                ]
            )
        elif semantics == "ordinary":
            if invocation_mode != "direct" or task_ref is not None:
                issues.append(
                    ValidationIssue(
                        "CONFIG_INVALID",
                        f"tools.yaml#tools/{index}",
                        "ordinary actions must be direct and must not declare task_ref",
                    )
                )
        elif isinstance(semantics, str):
            if invocation_mode == "direct":
                issues.extend(
                    [
                        ValidationIssue(
                            "TASK_BYPASS_ATTEMPT",
                            f"tools.yaml#tools/{index}/invocation_mode",
                            f"{semantics} actions must use a managed Task",
                        ),
                        ValidationIssue(
                            "HANDOFF_REQUIRED",
                            f"tools.yaml#tools/{index}/invocation_mode",
                            "register and select the managed Task before execution",
                        ),
                    ]
                )
            task = tasks_by_id.get(task_ref)
            if task is not None and task.get("category") != semantics:
                issues.append(
                    ValidationIssue(
                        "CONFIG_INVALID",
                        f"tools.yaml#tools/{index}/action_semantics",
                        "action_semantics must match the referenced Task category",
                    )
                )
        if isinstance(tool, dict) and tool.get("invocation_mode") == "managed":
            if task_ref not in tasks:
                issues.append(
                    ValidationIssue(
                        "TASK_REF_UNRESOLVED",
                        f"tools.yaml#tools/{index}/task_ref",
                        f"task_ref {task_ref!r} does not exist in tasks.yaml",
                    )
                )
        if tool.get("type") == "mcp-tool":
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
