"""Closed Harness 3.0 configuration and fixed-model contracts."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from .model import (
    AUDIENCES,
    CELL_IDS,
    DOMAINS,
    RESPONSIBILITIES,
    RULE_ID_MAX_LENGTH,
    RULE_ID_PATTERN,
    SCHEMA_VERSION,
    cell_id,
)
from .package_resources import schema_root


_RULE_FIELDS = ("rule_id", "directive", "scope")
_RULE_ID = re.compile(RULE_ID_PATTERN, re.ASCII)
_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")
_SCOPE_SEGMENT = re.compile(r"^[A-Za-z0-9._*?-]+$", re.ASCII)


@dataclass(frozen=True)
class ValidationIssue:
    """One stable, location-aware contract diagnostic."""

    code: str
    path: str
    message: str
    rule_id: str | None = None
    expected: Any | None = None
    actual: Any | None = None

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "code": self.code,
            "path": self.path,
            "message": self.message,
        }
        for name in ("rule_id", "expected", "actual"):
            value = getattr(self, name)
            if value is not None:
                result[name] = value
        return result


def _pointer(*parts: object) -> str:
    if not parts:
        return ""
    encoded = [
        str(part).replace("~", "~0").replace("/", "~1")
        for part in parts
    ]
    return "/" + "/".join(encoded)


def _sorted(issues: list[ValidationIssue]) -> list[ValidationIssue]:
    return sorted(
        issues,
        key=lambda issue: (issue.path, issue.code, issue.message),
    )


def _issue(
    code: str,
    path: str,
    message: str,
    *,
    rule_id: str | None = None,
    expected: Any | None = None,
    actual: Any | None = None,
) -> ValidationIssue:
    return ValidationIssue(
        code=code,
        path=path,
        message=message,
        rule_id=rule_id,
        expected=expected,
        actual=actual,
    )


def _valid_scope(value: str) -> bool:
    if (
        not value
        or not value.isascii()
        or value.startswith("/")
        or _DRIVE_PREFIX.match(value)
        or "\\" in value
    ):
        return False
    segments = value.split("/")
    for segment in segments:
        if (
            not segment
            or segment in {".", ".."}
            or not _SCOPE_SEGMENT.fullmatch(segment)
            or ("**" in segment and segment != "**")
        ):
            return False
    return True


def _validate_rule(
    rule: Any,
    *,
    domain: str,
    index: int,
    seen_ids: dict[str, str],
) -> list[ValidationIssue]:
    base = ("rule_instances", domain, index)
    path = _pointer(*base)
    if not isinstance(rule, dict):
        return [
            _issue(
                "RULE_TYPE_INVALID",
                path,
                "rule instance must be an object",
                expected="object",
                actual=type(rule).__name__,
            )
        ]

    issues: list[ValidationIssue] = []
    for field in sorted(set(rule) - set(_RULE_FIELDS)):
        issues.append(
            _issue(
                "RULE_FIELD_FORBIDDEN",
                _pointer(*base, field),
                f"rule field is not allowed: {field}",
                rule_id=rule.get("rule_id")
                if isinstance(rule.get("rule_id"), str)
                else None,
                expected=list(_RULE_FIELDS),
                actual=field,
            )
        )
    for field in _RULE_FIELDS:
        if field not in rule:
            issues.append(
                _issue(
                    "RULE_FIELD_MISSING",
                    _pointer(*base, field),
                    f"required rule field is missing: {field}",
                    rule_id=rule.get("rule_id")
                    if isinstance(rule.get("rule_id"), str)
                    else None,
                    expected=field,
                )
            )

    rule_id = rule.get("rule_id")
    valid_rule_id = (
        isinstance(rule_id, str)
        and len(rule_id) <= RULE_ID_MAX_LENGTH
        and _RULE_ID.fullmatch(rule_id) is not None
    )
    if "rule_id" in rule and not valid_rule_id:
        issues.append(
            _issue(
                "RULE_ID_INVALID",
                _pointer(*base, "rule_id"),
                "rule_id must be 1-64 ASCII lowercase kebab-case characters",
                rule_id=rule_id if isinstance(rule_id, str) else None,
                expected=RULE_ID_PATTERN,
                actual=rule_id,
            )
        )
    elif valid_rule_id:
        assert isinstance(rule_id, str)
        if rule_id in seen_ids:
            issues.append(
                _issue(
                    "RULE_ID_DUPLICATE",
                    _pointer(*base, "rule_id"),
                    "rule_id must be globally unique",
                    rule_id=rule_id,
                    expected="globally unique rule_id",
                    actual=rule_id,
                )
            )
        else:
            seen_ids[rule_id] = _pointer(*base, "rule_id")

    directive = rule.get("directive")
    if "directive" in rule:
        if not isinstance(directive, str):
            issues.append(
                _issue(
                    "RULE_DIRECTIVE_INVALID",
                    _pointer(*base, "directive"),
                    "directive must be a string",
                    rule_id=rule_id if valid_rule_id else None,
                    expected="string",
                    actual=type(directive).__name__,
                )
            )
        elif not directive.strip():
            issues.append(
                _issue(
                    "RULE_DIRECTIVE_EMPTY",
                    _pointer(*base, "directive"),
                    "directive must not be empty after trimming",
                    rule_id=rule_id if valid_rule_id else None,
                    expected="non-empty trimmed string",
                    actual=directive,
                )
            )

    scope = rule.get("scope")
    if "scope" in rule:
        if not isinstance(scope, list):
            issues.append(
                _issue(
                    "RULE_SCOPE_INVALID",
                    _pointer(*base, "scope"),
                    "scope must be a non-empty array",
                    rule_id=rule_id if valid_rule_id else None,
                    expected="non-empty array",
                    actual=type(scope).__name__,
                )
            )
        elif not scope:
            issues.append(
                _issue(
                    "RULE_SCOPE_EMPTY",
                    _pointer(*base, "scope"),
                    "scope must contain at least one repository-relative glob",
                    rule_id=rule_id if valid_rule_id else None,
                    expected="at least one scope glob",
                    actual=[],
                )
            )
        else:
            observed: set[str] = set()
            for scope_index, item in enumerate(scope):
                item_path = _pointer(*base, "scope", scope_index)
                if not isinstance(item, str) or not _valid_scope(item):
                    issues.append(
                        _issue(
                            "RULE_SCOPE_INVALID",
                            item_path,
                            "scope must be a portable repository-relative glob",
                            rule_id=rule_id if valid_rule_id else None,
                            expected=(
                                "ASCII repository-relative glob using /, *, ?, "
                                "and a complete ** segment"
                            ),
                            actual=item,
                        )
                    )
                    continue
                if item in observed:
                    issues.append(
                        _issue(
                            "RULE_SCOPE_DUPLICATE",
                            item_path,
                            "scope entries must be unique",
                            rule_id=rule_id if valid_rule_id else None,
                            expected="unique scope entries",
                            actual=item,
                        )
                    )
                observed.add(item)
    return issues


def validate_project_config(
    document_or_path: dict[str, Any] | Path,
) -> list[ValidationIssue]:
    """Validate the only supported Harness 3.0 user input."""

    if isinstance(document_or_path, Path):
        try:
            document = yaml.safe_load(
                document_or_path.read_text(encoding="utf-8")
            )
        except OSError as exc:
            return [
                _issue(
                    "CONFIG_READ_FAILED",
                    "",
                    str(exc),
                    expected="readable UTF-8 YAML",
                )
            ]
        except yaml.YAMLError as exc:
            return [
                _issue(
                    "CONFIG_YAML_INVALID",
                    "",
                    str(exc),
                    expected="valid YAML",
                )
            ]
    else:
        document = document_or_path

    if not isinstance(document, dict):
        return [
            _issue(
                "CONFIG_TYPE_INVALID",
                "",
                "Harness configuration must be an object",
                expected="object",
                actual=type(document).__name__,
            )
        ]

    issues: list[ValidationIssue] = []
    allowed_root = {"schema_version", "rule_instances"}
    for field in sorted(set(document) - allowed_root):
        issues.append(
            _issue(
                "CONFIG_ADDITIONAL_PROPERTY",
                _pointer(field),
                f"root property is not allowed: {field}",
                expected=sorted(allowed_root),
                actual=field,
            )
        )

    if "schema_version" not in document:
        issues.append(
            _issue(
                "CONFIG_REQUIRED_FIELD_MISSING",
                _pointer("schema_version"),
                "required root property is missing: schema_version",
                expected=SCHEMA_VERSION,
            )
        )
    elif document["schema_version"] != SCHEMA_VERSION:
        issues.append(
            _issue(
                "SCHEMA_VERSION_UNSUPPORTED",
                _pointer("schema_version"),
                "only Harness schema_version 3.0.0 is supported",
                expected=SCHEMA_VERSION,
                actual=document["schema_version"],
            )
        )

    if "rule_instances" not in document:
        issues.append(
            _issue(
                "CONFIG_REQUIRED_FIELD_MISSING",
                _pointer("rule_instances"),
                "required root property is missing: rule_instances",
                expected=list(DOMAINS),
            )
        )
        return _sorted(issues)

    instances = document["rule_instances"]
    if not isinstance(instances, dict):
        issues.append(
            _issue(
                "RULE_INSTANCES_TYPE_INVALID",
                _pointer("rule_instances"),
                "rule_instances must be an object",
                expected="object",
                actual=type(instances).__name__,
            )
        )
        return _sorted(issues)

    for domain in sorted(set(instances) - set(DOMAINS)):
        issues.append(
            _issue(
                "GOVERNANCE_DOMAIN_UNKNOWN",
                _pointer("rule_instances", domain),
                f"unknown governance domain: {domain}",
                expected=list(DOMAINS),
                actual=domain,
            )
        )
    for domain in DOMAINS:
        if domain not in instances:
            issues.append(
                _issue(
                    "GOVERNANCE_DOMAIN_MISSING",
                    _pointer("rule_instances", domain),
                    f"governance domain must be explicit: {domain}",
                    expected=[],
                )
            )

    seen_ids: dict[str, str] = {}
    for domain in DOMAINS:
        if domain not in instances:
            continue
        rules = instances[domain]
        if not isinstance(rules, list):
            issues.append(
                _issue(
                    "GOVERNANCE_DOMAIN_TYPE_INVALID",
                    _pointer("rule_instances", domain),
                    "governance domain value must be an array",
                    expected="array",
                    actual=type(rules).__name__,
                )
            )
            continue
        for index, rule in enumerate(rules):
            issues.extend(
                _validate_rule(
                    rule,
                    domain=domain,
                    index=index,
                    seen_ids=seen_ids,
                )
            )
    return _sorted(issues)


def validate_fixed_model_cells(cells: Any) -> list[ValidationIssue]:
    """Validate exact cell membership and axis-to-ID consistency."""

    if not isinstance(cells, list):
        return [
            _issue(
                "FIXED_MODEL_CELLS_INVALID",
                "/cells",
                "cells must be an array",
                expected=list(CELL_IDS),
                actual=type(cells).__name__,
            )
        ]

    issues: list[ValidationIssue] = []
    observed: list[Any] = []
    for index, cell in enumerate(cells):
        base = ("cells", index)
        if not isinstance(cell, dict):
            issues.append(
                _issue(
                    "FIXED_MODEL_CELL_INVALID",
                    _pointer(*base),
                    "cell must be an object",
                    expected=(
                        "cell_id, audience, responsibility, and domain"
                    ),
                    actual=type(cell).__name__,
                )
            )
            observed.append(None)
            continue
        observed.append(cell.get("cell_id"))
        audience = cell.get("audience")
        responsibility = cell.get("responsibility")
        domain = cell.get("domain")
        if audience not in AUDIENCES:
            issues.append(
                _issue(
                    "FIXED_MODEL_AXIS_INVALID",
                    _pointer(*base, "audience"),
                    "invalid audience",
                    expected=list(AUDIENCES),
                    actual=audience,
                )
            )
        if responsibility not in RESPONSIBILITIES:
            issues.append(
                _issue(
                    "FIXED_MODEL_AXIS_INVALID",
                    _pointer(*base, "responsibility"),
                    "invalid responsibility",
                    expected=list(RESPONSIBILITIES),
                    actual=responsibility,
                )
            )
        if domain not in DOMAINS:
            issues.append(
                _issue(
                    "FIXED_MODEL_AXIS_INVALID",
                    _pointer(*base, "domain"),
                    "invalid governance domain",
                    expected=list(DOMAINS),
                    actual=domain,
                )
            )
        if (
            audience in AUDIENCES
            and responsibility in RESPONSIBILITIES
            and domain in DOMAINS
        ):
            expected_id = cell_id(audience, responsibility, domain)
            if cell.get("cell_id") != expected_id:
                issues.append(
                    _issue(
                        "FIXED_MODEL_CELL_ID_MISMATCH",
                        _pointer(*base, "cell_id"),
                        "cell_id must match its three axis fields",
                        expected=expected_id,
                        actual=cell.get("cell_id"),
                    )
                )

    if observed != list(CELL_IDS):
        issues.append(
            _issue(
                "FIXED_MODEL_CELL_SET_MISMATCH",
                "/cells",
                "cells must contain the exact fixed IDs in canonical order",
                expected=list(CELL_IDS),
                actual=observed,
            )
        )
    return _sorted(issues)


def _schema_document(schema_name: str) -> dict[str, Any]:
    return json.loads(
        schema_root().joinpath(schema_name).read_text(encoding="utf-8")
    )


def validate_artifact(
    document: Any,
    schema_name: str,
) -> list[ValidationIssue]:
    """Validate a v3 artifact against one self-contained public Schema."""

    validator = Draft202012Validator(_schema_document(schema_name))
    issues = [
        _issue(
            "SCHEMA_VALIDATION_FAILED",
            _pointer(*error.absolute_path),
            error.message,
            expected=error.validator_value,
            actual=error.instance,
        )
        for error in validator.iter_errors(document)
    ]
    return _sorted(issues)


def validate_governance_artifact(document: Any) -> list[ValidationIssue]:
    issues = validate_artifact(document, "governance.schema.json")
    if issues or not isinstance(document, dict):
        return issues
    model = document.get("model")
    if not isinstance(model, dict):
        return issues
    return validate_fixed_model_cells(model.get("cells"))
