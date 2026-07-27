"""Postcondition validation for governed Action execution."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .artifacts import canonical_digest, path_digest


def _load_json_report(repository: Path, relative_path: str) -> dict[str, Any] | None:
    path = (repository.resolve() / relative_path).resolve()
    if not path.is_relative_to(repository.resolve()) or not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def validate_postconditions(
    *,
    repository: Path,
    semantics: str,
    exit_code: int,
    required_reports: list[str] | None = None,
    expected_files: list[str] | None = None,
) -> dict[str, Any]:
    """Validate observable results; exit code alone is insufficient for tests."""

    blockers: set[str] = set()
    reports = []
    files = []
    if exit_code != 0:
        blockers.add("GOVERNANCE_EVIDENCE_INCOMPLETE")

    for relative in sorted(set(required_reports or [])):
        report = _load_json_report(repository, relative)
        reports.append(
            {
                "path": relative,
                "digest": path_digest(repository / relative),
                "parsed": report is not None,
            }
        )
        if report is None:
            blockers.add("GOVERNANCE_EVIDENCE_INCOMPLETE")
        elif report.get("status") not in {"passed", "success", "ok"}:
            blockers.add("GOVERNANCE_EVIDENCE_INCOMPLETE")

    if semantics in {"test", "validation", "ci"} and not required_reports:
        blockers.add("GOVERNANCE_EVIDENCE_INCOMPLETE")

    for relative in sorted(set(expected_files or [])):
        digest = path_digest(repository / relative)
        files.append({"path": relative, "digest": digest})
        if digest == "absent":
            blockers.add("GOVERNANCE_EVIDENCE_INCOMPLETE")

    result = {
        "status": "blocked" if blockers else "passed",
        "exit_code": exit_code,
        "reports": reports,
        "files": files,
        "blocker_codes": sorted(blockers),
    }
    result["postconditions_digest"] = canonical_digest(result)
    return result
