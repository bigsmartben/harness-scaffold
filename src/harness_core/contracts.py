"""JSON Schema and cross-artifact validation for Harness 2.0."""

from __future__ import annotations

import json
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from .artifacts import SCHEMA_VERSION, digest_matches
from .package_resources import schema_root


AUDIENCES = ("maintainer", "consumer")
RESPONSIBILITIES = ("generate", "enforce")
DOMAINS = ("specification", "implementation", "verification", "delivery")


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    path: str
    message: str


def _schema_documents() -> dict[str, dict[str, Any]]:
    documents: dict[str, dict[str, Any]] = {}
    for child in schema_root().iterdir():
        if child.name.endswith(".schema.json"):
            documents[child.name] = json.loads(child.read_text(encoding="utf-8"))
    return documents


def _registry(documents: dict[str, dict[str, Any]]) -> Registry:
    registry = Registry()
    for document in documents.values():
        registry = registry.with_resource(
            document["$id"], Resource.from_contents(document)
        )
    return registry


def blocker_codes() -> tuple[str, ...]:
    common = _schema_documents()["common.schema.json"]
    return tuple(common["$defs"]["blockerCode"]["enum"])


def validate_artifact(
    document: Any,
    schema_name: str,
) -> list[ValidationIssue]:
    documents = _schema_documents()
    schema = documents[schema_name]
    validator = Draft202012Validator(schema, registry=_registry(documents))
    return [
        ValidationIssue(
            "CONFIG_INVALID",
            "/".join(str(item) for item in error.absolute_path) or "$",
            error.message,
        )
        for error in sorted(validator.iter_errors(document), key=str)
    ]


def validate_project_config(document_or_path: dict[str, Any] | Path) -> list[ValidationIssue]:
    if isinstance(document_or_path, Path):
        try:
            document = yaml.safe_load(document_or_path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            return [ValidationIssue("CONFIG_INVALID", "$", str(exc))]
    else:
        document = document_or_path
    return validate_artifact(document, "harness.schema.json")


def validate_runtime_artifact(document: Any) -> list[ValidationIssue]:
    return validate_artifact(document, "runtime.schema.json")


def validate_governance_artifact(document: Any) -> list[ValidationIssue]:
    return validate_artifact(document, "governance.schema.json")


def validate_governance_bundle(
    bundle: dict[str, dict[str, Any]],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    required = ("sources", "action_graph", "rules", "projection_lock")
    for name in required:
        if name not in bundle:
            issues.append(
                ValidationIssue(
                    "GOVERNANCE_SOURCE_MISSING",
                    name,
                    f"missing governance artifact: {name}",
                )
            )
            continue
        issues.extend(validate_governance_artifact(bundle[name]))
    if issues:
        return issues

    sources = bundle["sources"]
    graph = bundle["action_graph"]
    rules = bundle["rules"]
    lock = bundle["projection_lock"]
    fact_ids = [fact["fact_id"] for fact in sources["facts"]]
    if len(fact_ids) != len(set(fact_ids)):
        issues.append(
            ValidationIssue(
                "GOVERNANCE_CONFLICT",
                "sources.facts",
                "source fact IDs must be unique",
            )
        )
    digest_fields = {
        "sources": "facts_digest",
        "action_graph": "action_graph_digest",
        "rules": "rules_digest",
        "projection_lock": "projection_lock_digest",
    }
    for name, field in digest_fields.items():
        if not digest_matches(bundle[name], field):
            issues.append(
                ValidationIssue(
                    "GOVERNANCE_DRIFT_DETECTED",
                    name,
                    f"{field} does not match the artifact",
                )
            )

    expected_cells = {
        f"{audience}.{responsibility}.{domain}"
        for audience, responsibility, domain in product(
            AUDIENCES, RESPONSIBILITIES, DOMAINS
        )
    }
    observed = [cell["cell_id"] for cell in rules["cells"]]
    if set(observed) != expected_cells or len(observed) != len(expected_cells):
        issues.append(
            ValidationIssue(
                "GOVERNANCE_COVERAGE_INCOMPLETE",
                "rules.cells",
                "the projection must contain exactly one record for every governance cell",
            )
        )
    for index, cell in enumerate(rules["cells"]):
        if (
            cell["coverage_status"] == "not_applicable"
            and (
                not cell["source_refs"]
                or not isinstance(cell["not_applicable_reason"], str)
                or not cell["not_applicable_reason"].strip()
            )
        ):
            issues.append(
                ValidationIssue(
                    "GOVERNANCE_COVERAGE_INCOMPLETE",
                    f"rules.cells.{index}",
                    "not_applicable requires source_refs and a reason",
                )
            )
        if cell["coverage_status"] == "missing":
            issues.append(
                ValidationIssue(
                    "GOVERNANCE_COVERAGE_INCOMPLETE",
                    f"rules.cells.{index}",
                    f"{cell['cell_id']} is missing",
                )
            )

    cross_checks = (
        (
            digest_matches(sources["snapshot"], "snapshot_digest")
            and sources["snapshot"]["snapshot_digest"]
            == sources["snapshot_digest"],
            "source facts snapshot summary does not match its snapshot digest",
        ),
        (
            sources["snapshot_digest"] == graph["snapshot_digest"],
            "action graph snapshot does not match source facts",
        ),
        (
            sources["facts_digest"] == graph["facts_digest"],
            "action graph does not bind the current source facts",
        ),
        (
            graph["action_graph_digest"] == lock["action_graph_digest"],
            "projection lock does not bind the current action graph",
        ),
        (
            sources["facts_digest"] == lock["facts_digest"],
            "projection lock does not bind the current source facts",
        ),
        (
            rules["projection_id"] == lock["projection_id"],
            "rules and projection lock use different projection IDs",
        ),
        (
            rules["rules_digest"] == lock["rules_digest"],
            "projection lock does not bind the current rules",
        ),
    )
    for passed, message in cross_checks:
        if not passed:
            issues.append(
                ValidationIssue("GOVERNANCE_CONFLICT", "$", message)
            )

    graph_blockers = sorted(
        {item["code"] for item in graph.get("blockers", [])}
    )
    if sorted(lock["blockers"]) != graph_blockers:
        issues.append(
            ValidationIssue(
                "GOVERNANCE_CONFLICT",
                "projection_lock.blockers",
                "projection blockers do not match the action graph",
            )
        )
    if lock["ready"] != (not lock["blockers"]):
        issues.append(
            ValidationIssue(
                "GOVERNANCE_CONFLICT",
                "projection_lock.ready",
                "ready must equal the absence of blockers",
            )
        )
    if any(
        artifact.get("schema_version") != SCHEMA_VERSION
        for artifact in bundle.values()
    ):
        issues.append(
            ValidationIssue(
                "HARNESS_RUNTIME_INCOMPATIBLE",
                "$",
                "every governance artifact must use schema 2.0.0",
            )
        )
    return issues


# Compatibility aliases used only by read-only callers.
validate_config = validate_project_config


def runtime_artifact_is_valid(document: Any) -> bool:
    return not validate_runtime_artifact(document)
