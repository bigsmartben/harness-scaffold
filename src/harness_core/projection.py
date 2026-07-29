"""Deterministic Harness 3.0 model-lock compilation and validation."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable

import yaml

from .artifacts import canonical_digest
from .contracts import (
    ValidationIssue,
    validate_governance_artifact,
    validate_project_config,
)
from .model import (
    AUDIENCES,
    CELL_DIRECTIVES,
    CELL_IDS,
    CONTRACT_VERSION,
    CORE_VERSION,
    DOMAINS,
    PROJECTION_COMPILER_VERSION,
    RESPONSIBILITIES,
    SCHEMA_VERSION,
)


MODEL_LOCK_RELATIVE_PATH = ".harness/governance/model.lock.json"


class ContractValidationError(ValueError):
    """Raised when compilation receives invalid v3 source input."""

    def __init__(self, issues: list[ValidationIssue]) -> None:
        self.issues = issues
        super().__init__(", ".join(issue.code for issue in issues))


def _pointer(*parts: object) -> str:
    if not parts:
        return ""
    return "/" + "/".join(
        str(part).replace("~", "~0").replace("/", "~1")
        for part in parts
    )


def _load_source(document_or_path: dict[str, Any] | Path) -> dict[str, Any]:
    issues = validate_project_config(document_or_path)
    if issues:
        raise ContractValidationError(issues)
    if isinstance(document_or_path, Path):
        document = yaml.safe_load(
            document_or_path.read_text(encoding="utf-8")
        )
    else:
        document = document_or_path
    assert isinstance(document, dict)
    return document


def normalize_project_config(
    document_or_path: dict[str, Any] | Path,
) -> dict[str, Any]:
    """Return the canonical v3 source form without mutating user input."""

    document = _load_source(document_or_path)
    instances = document["rule_instances"]
    normalized: dict[str, list[dict[str, Any]]] = {}
    for domain in DOMAINS:
        normalized[domain] = sorted(
            (
                {
                    "rule_id": item["rule_id"],
                    "directive": item["directive"].strip(),
                    "scope": sorted(item["scope"]),
                }
                for item in instances[domain]
            ),
            key=lambda item: item["rule_id"],
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "rule_instances": normalized,
    }


def _fixed_cells() -> list[dict[str, str]]:
    cells: list[dict[str, str]] = []
    for identifier in CELL_IDS:
        audience, responsibility, domain = identifier.split(".")
        cells.append(
            {
                "cell_id": identifier,
                "audience": audience,
                "responsibility": responsibility,
                "domain": domain,
                "directive": CELL_DIRECTIVES[identifier],
            }
        )
    return cells


def _project_rules(
    normalized_config: dict[str, Any],
) -> list[dict[str, Any]]:
    projected: list[dict[str, Any]] = []
    for domain in DOMAINS:
        for item in normalized_config["rule_instances"][domain]:
            rule_id = item["rule_id"]
            projected.append(
                {
                    "domain": domain,
                    "kind": "guidance",
                    "rule_id": rule_id,
                    "directive": item["directive"],
                    "scope": item["scope"],
                    "source_ref": (
                        ".harness/harness.yaml#/rule_instances/"
                        f"{domain}/{rule_id}"
                    ),
                }
            )
    return projected


def compile_model_lock(
    document_or_path: dict[str, Any] | Path,
) -> dict[str, Any]:
    """Compile one complete lock entirely from validated v3 source."""

    normalized = normalize_project_config(document_or_path)
    source_digest = canonical_digest(normalized)
    lock: dict[str, Any] = {
        "artifact_type": "harness-model-lock",
        "schema_version": SCHEMA_VERSION,
        "components": {
            "core_version": CORE_VERSION,
            "contract_version": CONTRACT_VERSION,
            "compiler_version": PROJECTION_COMPILER_VERSION,
        },
        "model": {
            "audiences": list(AUDIENCES),
            "responsibilities": list(RESPONSIBILITIES),
            "domains": list(DOMAINS),
            "cells": _fixed_cells(),
        },
        "rules": _project_rules(normalized),
        "source_digest": source_digest,
    }
    lock["projection_digest"] = canonical_digest(lock)
    return lock


def render_model_lock(lock: dict[str, Any]) -> bytes:
    """Render stable UTF-8 JSON with LF newlines and one final newline."""

    return (
        json.dumps(
            lock,
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _load_lock(
    document_or_path: dict[str, Any] | Path,
) -> tuple[dict[str, Any] | None, list[ValidationIssue]]:
    if isinstance(document_or_path, Path):
        if not document_or_path.is_file():
            return None, [
                ValidationIssue(
                    "MODEL_LOCK_MISSING",
                    "",
                    "model lock does not exist",
                    expected=MODEL_LOCK_RELATIVE_PATH,
                    actual=str(document_or_path),
                )
            ]
        try:
            document = json.loads(
                document_or_path.read_text(encoding="utf-8")
            )
        except OSError as exc:
            return None, [
                ValidationIssue(
                    "MODEL_LOCK_READ_FAILED",
                    "",
                    str(exc),
                    expected="readable UTF-8 JSON",
                )
            ]
        except json.JSONDecodeError as exc:
            return None, [
                ValidationIssue(
                    "MODEL_LOCK_JSON_INVALID",
                    "",
                    str(exc),
                    expected="valid JSON",
                )
            ]
    else:
        document = document_or_path
    if not isinstance(document, dict):
        return None, [
            ValidationIssue(
                "MODEL_LOCK_TYPE_INVALID",
                "",
                "model lock must be an object",
                expected="object",
                actual=type(document).__name__,
            )
        ]
    return document, []


def _first_difference(
    expected: Any,
    actual: Any,
    parts: tuple[object, ...] = (),
) -> tuple[str, Any, Any] | None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return _pointer(*parts), expected, actual
        for key in expected:
            if key not in actual:
                return _pointer(*parts, key), expected[key], "<missing>"
            difference = _first_difference(
                expected[key],
                actual[key],
                (*parts, key),
            )
            if difference is not None:
                return difference
        for key in sorted(set(actual) - set(expected)):
            return _pointer(*parts, key), "<absent>", actual[key]
        return None
    if isinstance(expected, list):
        if not isinstance(actual, list):
            return _pointer(*parts), expected, actual
        if len(expected) != len(actual):
            return _pointer(*parts), len(expected), len(actual)
        for index, value in enumerate(expected):
            difference = _first_difference(
                value,
                actual[index],
                (*parts, index),
            )
            if difference is not None:
                return difference
        return None
    if expected != actual:
        return _pointer(*parts), expected, actual
    return None


def _mismatch_issue(
    path: str,
    expected: Any,
    actual: Any,
    lock: dict[str, Any],
) -> ValidationIssue:
    code = "MODEL_LOCK_MISMATCH"
    rule_id: str | None = None
    if path.startswith("/model/cells"):
        code = "FIXED_MODEL_MISMATCH"
        parts = path.split("/")
        if len(parts) > 3 and parts[3].isdigit():
            index = int(parts[3])
            cells = lock.get("model", {}).get("cells", [])
            if isinstance(cells, list) and index < len(cells):
                cell = cells[index]
                if isinstance(cell, dict):
                    value = cell.get("cell_id")
                    rule_id = value if isinstance(value, str) else None
    elif path.startswith("/rules"):
        code = "PROJECTED_RULE_MISMATCH"
        parts = path.split("/")
        if len(parts) > 2 and parts[2].isdigit():
            index = int(parts[2])
            rules = lock.get("rules", [])
            if isinstance(rules, list) and index < len(rules):
                rule = rules[index]
                if isinstance(rule, dict):
                    value = rule.get("rule_id")
                    rule_id = value if isinstance(value, str) else None
    elif path.startswith("/components") or path == "/schema_version":
        code = "COMPONENT_VERSION_MISMATCH"
    elif path == "/source_digest":
        code = "SOURCE_DIGEST_MISMATCH"
    elif path == "/projection_digest":
        code = "PROJECTION_DIGEST_MISMATCH"
    return ValidationIssue(
        code,
        path,
        "model lock differs from the projection recomputed from source",
        rule_id=rule_id,
        expected=expected,
        actual=actual,
    )


def validate_model_lock(
    source: dict[str, Any] | Path,
    lock_or_path: dict[str, Any] | Path,
) -> list[ValidationIssue]:
    """Recompute the complete lock and compare it with untrusted input."""

    try:
        expected = compile_model_lock(source)
    except ContractValidationError as exc:
        return exc.issues
    actual, read_issues = _load_lock(lock_or_path)
    if read_issues or actual is None:
        return read_issues

    issues = validate_governance_artifact(actual)
    difference = _first_difference(expected, actual)
    if difference is not None:
        issues.append(_mismatch_issue(*difference, actual))
    unique = {
        (
            issue.code,
            issue.path,
            issue.message,
            repr(issue.expected),
            repr(issue.actual),
        ): issue
        for issue in issues
    }
    return sorted(
        unique.values(),
        key=lambda issue: (issue.path, issue.code, issue.message),
    )


def project_model_lock(
    source: dict[str, Any] | Path,
    target: Path,
    *,
    replace: Callable[[str | os.PathLike[str], str | os.PathLike[str]], Any]
    | None = None,
) -> dict[str, Any]:
    """Validate, compile, and atomically replace one model lock."""

    try:
        lock = compile_model_lock(source)
    except ContractValidationError as exc:
        return {
            "status": "blocked",
            "path": str(target),
            "diagnostics": [issue.as_dict() for issue in exc.issues],
        }
    payload = render_model_lock(lock)
    try:
        if target.is_file() and target.read_bytes() == payload:
            return {
                "status": "unchanged",
                "path": str(target),
                "source_digest": lock["source_digest"],
                "projection_digest": lock["projection_digest"],
                "diagnostics": [],
            }
    except OSError as exc:
        return {
            "status": "blocked",
            "path": str(target),
            "diagnostics": [
                ValidationIssue(
                    "MODEL_LOCK_READ_FAILED",
                    "",
                    str(exc),
                    expected="readable existing model lock",
                ).as_dict()
            ],
        }

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.",
            suffix=".tmp",
            dir=target.parent,
        )
    except OSError as exc:
        return {
            "status": "blocked",
            "path": str(target),
            "diagnostics": [
                ValidationIssue(
                    "MODEL_LOCK_WRITE_FAILED",
                    "",
                    str(exc),
                    expected="writable model lock directory",
                    actual=type(exc).__name__,
                ).as_dict()
            ],
        }
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        operation = replace or os.replace
        operation(temporary, target)
    except Exception as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        return {
            "status": "blocked",
            "path": str(target),
            "diagnostics": [
                ValidationIssue(
                    "MODEL_LOCK_WRITE_FAILED",
                    "",
                    str(exc),
                    expected="atomic replacement",
                    actual=type(exc).__name__,
                ).as_dict()
            ],
        }

    return {
        "status": "projected",
        "path": str(target),
        "source_digest": lock["source_digest"],
        "projection_digest": lock["projection_digest"],
        "diagnostics": [],
    }


def default_model_lock_path(repository: Path) -> Path:
    return repository / MODEL_LOCK_RELATIVE_PATH
