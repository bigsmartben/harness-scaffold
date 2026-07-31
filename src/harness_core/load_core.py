"""Read-only repository discovery and governance calibration core."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from .artifacts import canonical_digest, content_digest
from .model import CONTRACT_VERSION, DOMAINS


LOAD_CONTRACT_VERSION = CONTRACT_VERSION
_IGNORED_PARTS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "node_modules",
    "__pycache__",
}
_GOVERNANCE_MARKDOWN = {
    "AGENTS.md",
    "CLAUDE.md",
    "CONTRIBUTING.md",
    ".github/copilot-instructions.md",
}
_SOURCE_PRIORITIES = {
    ".harness/governance/state.json": 400,
    ".harness/harness.yaml": 300,
    "AGENTS.md": 250,
    "CLAUDE.md": 225,
    ".github/copilot-instructions.md": 200,
    "CONTRIBUTING.md": 150,
}
_DOMAIN_TERMS = {
    "specification": (
        "spec",
        "requirement",
        "acceptance",
        "需求",
        "规范",
        "验收",
    ),
    "implementation": (
        "implement",
        "code",
        "source",
        "format",
        "实现",
        "代码",
        "源码",
    ),
    "verification": (
        "test",
        "verify",
        "check",
        "evidence",
        "测试",
        "验证",
        "证据",
    ),
    "delivery": (
        "release",
        "deploy",
        "publish",
        "package",
        "git",
        "发布",
        "部署",
        "交付",
    ),
}
_SHA256_PATTERN = re.compile(r"^sha256:[a-f0-9]{64}$")


def build_load_request(repository: Path) -> dict[str, Any]:
    """Build the client-independent load request."""

    return {
        "contract_version": LOAD_CONTRACT_VERSION,
        "repository": str(repository.resolve()),
    }


def _diagnostic(
    code: str,
    message: str,
    *,
    source: str | None = None,
    rule_id: str | None = None,
    actual: Any | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {"code": code, "message": message}
    if source is not None:
        result["source"] = source
    if rule_id is not None:
        result["rule_id"] = rule_id
    if actual is not None:
        result["actual"] = actual
    return result


def _blocked_load_result(
    diagnostics: list[dict[str, Any]],
    *,
    repository: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "blocked",
        "contract_version": LOAD_CONTRACT_VERSION,
        "repository": repository,
        "snapshot_digest": None,
        "facts": [],
        "governance_sources": [],
        "candidates": [],
        "calibrations": [],
        "diagnostics": diagnostics,
    }
    result["result_digest"] = canonical_digest(result)
    return result


def _repository_files(repository: Path) -> list[Path]:
    files: list[Path] = []
    for path in repository.rglob("*"):
        relative = path.relative_to(repository)
        if any(part in _IGNORED_PARTS for part in relative.parts):
            continue
        relative_text = relative.as_posix()
        if relative_text.startswith(
            (".harness/", ".agents/skills/harness/")
        ):
            continue
        if path.is_symlink() or not path.is_file():
            continue
        files.append(path)
    return sorted(files, key=lambda item: item.relative_to(repository).as_posix())


def _snapshot(repository: Path) -> dict[str, Any]:
    entries = []
    for path in _repository_files(repository):
        relative = path.relative_to(repository).as_posix()
        payload = path.read_bytes()
        entries.append(
            {
                "path": relative,
                "size": len(payload),
                "digest": content_digest(payload),
            }
        )
    return {"files": entries}


def _fact(
    fact_id: str,
    kind: str,
    paths: list[str],
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    entries = {
        item["path"]: item
        for item in snapshot["files"]
        if item["path"] in paths
    }
    value = {
        "fact_id": fact_id,
        "kind": kind,
        "paths": sorted(paths),
        "entries": entries,
    }
    value["digest"] = canonical_digest(value)
    return value


def _discover_facts(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    paths = [item["path"] for item in snapshot["files"]]
    specification = [
        path
        for path in paths
        if path.lower().endswith((".md", ".rst"))
        or path.startswith(("docs/", "specs/"))
    ]
    implementation = [
        path
        for path in paths
        if path.endswith(
            (
                ".py",
                ".js",
                ".ts",
                ".tsx",
                ".go",
                ".rs",
                ".java",
                ".kt",
                ".swift",
            )
        )
        and not path.startswith(("tests/", "test/"))
    ]
    verification = [
        path
        for path in paths
        if path.startswith(("tests/", "test/"))
        or "/test_" in path
        or path.startswith(".github/workflows/")
    ]
    delivery = [
        path
        for path in paths
        if path in {"pyproject.toml", "package.json", "Cargo.toml", "go.mod"}
        or path.startswith(".github/workflows/")
        or "release" in path.lower()
    ]
    groups = {
        "specification": specification,
        "implementation": implementation,
        "verification": verification,
        "delivery": delivery,
    }
    return [
        _fact(
            f"{domain}-surfaces",
            "present" if domain_paths else "absent",
            domain_paths,
            snapshot,
        )
        for domain, domain_paths in groups.items()
    ]


def _source(fact: dict[str, Any]) -> dict[str, str]:
    return {
        "source_type": "repository_fact",
        "reference": f"snapshot:{fact['fact_id']}",
        "digest": fact["digest"],
    }


def _generated_candidate(fact: dict[str, Any]) -> dict[str, Any]:
    domain = fact["fact_id"].removesuffix("-surfaces")
    paths = fact["paths"]
    if paths:
        joined = ", ".join(paths[:3])
        directive = {
            "specification": (
                f"Keep observable requirements and acceptance criteria aligned with {joined}."
            ),
            "implementation": (
                f"Keep implementation changes within the discovered source surfaces: {joined}."
            ),
            "verification": (
                f"Provide repeatable verification evidence through the discovered surfaces: {joined}."
            ),
            "delivery": (
                f"Keep delivery metadata and artifacts aligned with the discovered surfaces: {joined}."
            ),
        }[domain]
        scope = paths
    else:
        directive = {
            "specification": (
                "Create an explicit specification source with observable acceptance criteria "
                "before implementation."
            ),
            "implementation": (
                "Establish explicit source boundaries before adding implementation files."
            ),
            "verification": (
                "Add a repeatable verification surface before accepting governed changes."
            ),
            "delivery": (
                "Define delivery metadata and required release evidence before distribution."
            ),
        }[domain]
        scope = ["**"]
    return {
        "rule_id": f"repo-{domain}-baseline",
        "domain": domain,
        "directive": directive,
        "scope": scope,
        "sources": [_source(fact)],
        "_origin": "snapshot",
        "_priority": 500,
    }


def _governance_paths(repository: Path) -> list[Path]:
    result = []
    for relative in sorted(_GOVERNANCE_MARKDOWN):
        path = repository / relative
        if path.is_file() and not path.is_symlink():
            result.append(path)
    harness = repository / ".harness" / "harness.yaml"
    if harness.is_file() and not harness.is_symlink():
        result.append(harness)
    state = repository / ".harness" / "governance" / "state.json"
    if state.is_file() and not state.is_symlink():
        result.append(state)
    return sorted(
        result,
        key=lambda path: (
            -_SOURCE_PRIORITIES[
                path.relative_to(repository).as_posix()
            ],
            path.relative_to(repository).as_posix(),
        ),
    )


def _source_record(repository: Path, path: Path) -> dict[str, Any]:
    relative = path.relative_to(repository).as_posix()
    payload = path.read_bytes()
    version = None
    if path.name == "state.json":
        try:
            document = json.loads(payload)
            version = document.get("contract_version")
        except (json.JSONDecodeError, AttributeError):
            pass
    elif path.name == "harness.yaml":
        try:
            document = yaml.safe_load(payload)
            version = (
                document.get("schema_version")
                if isinstance(document, dict)
                else None
            )
        except yaml.YAMLError:
            pass
    return {
        "path": relative,
        "priority": _SOURCE_PRIORITIES[relative],
        "version": version,
        "digest": content_digest(payload),
    }


def _classify(text: str) -> str | None:
    lowered = text.lower()
    matches = [
        domain
        for domain, terms in _DOMAIN_TERMS.items()
        if any(term in lowered for term in terms)
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def _valid_scope(value: Any) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and len(value) == len(set(value))
        and all(isinstance(item, str) and item for item in value)
    )


def _valid_sources(value: Any) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(
            isinstance(source, dict)
            and set(source) == {"source_type", "reference", "digest"}
            and source["source_type"]
            in {"repository_fact", "governance_source", "user_intent"}
            and isinstance(source["reference"], str)
            and bool(source["reference"])
            and isinstance(source["digest"], str)
            and _SHA256_PATTERN.fullmatch(source["digest"]) is not None
            for source in value
        )
    )


def _markdown_candidates(
    repository: Path,
    path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidates: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    relative = path.relative_to(repository).as_posix()
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        match = re.match(r"^\s*[-*]\s+(.+?)\s*$", line)
        if match is None:
            continue
        directive = match.group(1)
        domain = _classify(directive)
        reference = f"{relative}#L{line_number}"
        if domain is None:
            diagnostics.append(
                _diagnostic(
                    "GOVERNANCE_SOURCE_UNCLASSIFIED",
                    "existing governance directive cannot be classified without guessing",
                    source=reference,
                    actual=directive,
                )
            )
            continue
        suffix = canonical_digest(
            {"source": reference, "directive": directive}
        ).split(":", maxsplit=1)[1][:10]
        candidates.append(
            {
                "rule_id": f"source-{domain}-{suffix}",
                "domain": domain,
                "directive": directive,
                "scope": ["**"],
                "sources": [
                    {
                        "source_type": "governance_source",
                        "reference": reference,
                        "digest": content_digest(line),
                    }
                ],
                "_origin": relative,
                "_priority": _SOURCE_PRIORITIES[relative],
            }
        )
    return candidates, diagnostics


def _harness_candidates(
    repository: Path,
    path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    relative = path.relative_to(repository).as_posix()
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        return [], [
            _diagnostic(
                "GOVERNANCE_SOURCE_INVALID",
                "existing Harness governance source is unreadable",
                source=relative,
                actual=str(exc),
            )
        ]
    instances = document.get("rule_instances") if isinstance(document, dict) else None
    if not isinstance(instances, dict):
        return [], [
            _diagnostic(
                "GOVERNANCE_SOURCE_UNRECOGNIZED",
                "existing Harness source contains no recognizable rule_instances",
                source=relative,
            )
        ]
    candidates: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for domain, rules in instances.items():
        if domain not in DOMAINS or not isinstance(rules, list):
            diagnostics.append(
                _diagnostic(
                    "GOVERNANCE_SOURCE_UNCLASSIFIED",
                    "existing rule group cannot be classified",
                    source=f"{relative}#/rule_instances/{domain}",
                )
            )
            continue
        for index, rule in enumerate(rules):
            reference = f"{relative}#/rule_instances/{domain}/{index}"
            if (
                not isinstance(rule, dict)
                or not {"rule_id", "directive", "scope"}.issubset(rule)
                or not isinstance(rule["rule_id"], str)
                or not rule["rule_id"]
                or not isinstance(rule["directive"], str)
                or not rule["directive"].strip()
                or not _valid_scope(rule["scope"])
            ):
                diagnostics.append(
                    _diagnostic(
                        "GOVERNANCE_SOURCE_INVALID",
                        "existing rule is missing recognizable governance content",
                        source=reference,
                    )
                )
                continue
            candidates.append(
                {
                    "rule_id": rule["rule_id"],
                    "domain": domain,
                    "directive": str(rule["directive"]).strip(),
                    "scope": sorted(rule["scope"]),
                    "sources": [
                        {
                            "source_type": "governance_source",
                            "reference": reference,
                            "digest": canonical_digest(rule),
                        }
                    ],
                    "_origin": relative,
                    "_priority": _SOURCE_PRIORITIES[relative],
                }
            )
    return candidates, diagnostics


def _state_candidates(
    repository: Path,
    path: Path,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    set[str],
]:
    relative = path.relative_to(repository).as_posix()
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [], [
            _diagnostic(
                "GOVERNANCE_SOURCE_INVALID",
                "authoritative governance state is unreadable",
                source=relative,
                actual=str(exc),
            )
        ], set()
    rules = document.get("rules") if isinstance(document, dict) else None
    if (
        not isinstance(document, dict)
        or document.get("contract_version") != LOAD_CONTRACT_VERSION
    ):
        return [], [
            _diagnostic(
                "CONTRACT_VERSION_UNSUPPORTED",
                "authoritative governance state contract version is unsupported",
                source=relative,
                actual=(
                    document.get("contract_version")
                    if isinstance(document, dict)
                    else None
                ),
            )
        ], set()
    if not isinstance(rules, dict):
        return [], [
            _diagnostic(
                "GOVERNANCE_SOURCE_INVALID",
                "authoritative governance state has no current rules object",
                source=relative,
            )
        ], set()
    deleted_rules = document.get("deleted_rules")
    if not isinstance(deleted_rules, dict):
        return [], [
            _diagnostic(
                "GOVERNANCE_SOURCE_INVALID",
                "authoritative governance state has no deleted_rules object",
                source=relative,
            )
        ], set()
    candidates = []
    diagnostics = []
    for rule_id, rule in sorted(rules.items()):
        if (
            not isinstance(rule, dict)
            or not {
                "rule_id",
                "domain",
                "directive",
                "scope",
                "sources",
            }.issubset(rule)
            or rule["rule_id"] != rule_id
            or rule["domain"] not in DOMAINS
            or not isinstance(rule["directive"], str)
            or not rule["directive"].strip()
            or not _valid_scope(rule["scope"])
            or not _valid_sources(rule["sources"])
        ):
            diagnostics.append(
                _diagnostic(
                    "GOVERNANCE_SOURCE_INVALID",
                    "current state rule lacks recognizable governance content",
                    source=f"{relative}#/rules/{rule_id}",
                    rule_id=rule_id,
                )
            )
            continue
        candidates.append(
            {
                "rule_id": rule_id,
                "domain": rule["domain"],
                "directive": rule["directive"],
                "scope": deepcopy(rule["scope"]),
                "sources": deepcopy(rule["sources"]),
                "_origin": "state",
                "_priority": _SOURCE_PRIORITIES[relative],
            }
        )
    return candidates, diagnostics, set(deleted_rules)


def _existing_candidates(
    repository: Path,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    set[str],
]:
    candidates: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    retired_rule_ids: set[str] = set()
    paths = _governance_paths(repository)
    for path in paths:
        if path.name == "state.json":
            found, found_diagnostics, found_retired = _state_candidates(
                repository, path
            )
            retired_rule_ids.update(found_retired)
        elif path.name == "harness.yaml":
            found, found_diagnostics = _harness_candidates(repository, path)
        else:
            found, found_diagnostics = _markdown_candidates(repository, path)
        candidates.extend(found)
        diagnostics.extend(found_diagnostics)
    return (
        candidates,
        diagnostics,
        [_source_record(repository, path) for path in paths],
        retired_rule_ids,
    )


def _calibrate(
    candidates: list[dict[str, Any]],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    accepted: dict[str, dict[str, Any]] = {}
    conflicts: list[dict[str, Any]] = []
    calibrations: list[dict[str, Any]] = []
    for candidate in candidates:
        rule_id = candidate["rule_id"]
        existing = accepted.get(rule_id)
        if existing is None:
            accepted[rule_id] = candidate
            continue
        existing_content = {
            key: existing[key]
            for key in ("rule_id", "domain", "directive", "scope")
        }
        candidate_content = {
            key: candidate[key]
            for key in ("rule_id", "domain", "directive", "scope")
        }
        origins = {existing.get("_origin"), candidate.get("_origin")}
        if (
            rule_id.startswith("repo-")
            and rule_id.endswith("-baseline")
            and origins == {"snapshot", "state"}
            and canonical_digest(existing["sources"])
            != canonical_digest(candidate["sources"])
        ):
            selected = (
                existing
                if existing["_origin"] == "snapshot"
                else candidate
            )
            previous = (
                candidate
                if selected is existing
                else existing
            )
            accepted[rule_id] = selected
            calibrations.append(
                {
                    "code": "DERIVED_BASELINE_REFRESHED",
                    "rule_id": rule_id,
                    "previous_sources": previous["sources"],
                    "current_sources": selected["sources"],
                }
            )
            continue
        if canonical_digest(existing_content) == canonical_digest(
            candidate_content
        ):
            merged_sources = {
                canonical_digest(source): source
                for source in [
                    *existing["sources"],
                    *candidate["sources"],
                ]
            }
            existing["sources"] = [
                merged_sources[digest]
                for digest in sorted(merged_sources)
            ]
            continue
        if (
            rule_id.startswith("repo-")
            and rule_id.endswith("-baseline")
            and origins == {"snapshot", "state"}
        ):
            selected = (
                existing
                if existing["_origin"] == "snapshot"
                else candidate
            )
            previous = (
                candidate
                if selected is existing
                else existing
            )
            accepted[rule_id] = selected
            calibrations.append(
                {
                    "code": "DERIVED_BASELINE_REFRESHED",
                    "rule_id": rule_id,
                    "previous_sources": previous["sources"],
                    "current_sources": selected["sources"],
                }
            )
            continue
        conflicts.append(
            _diagnostic(
                "RULE_CANDIDATE_CONFLICT",
                "the same rule_id has conflicting governance content",
                rule_id=rule_id,
                actual={
                    "first": existing["sources"],
                    "second": candidate["sources"],
                },
            )
        )
    return (
        sorted(
            (
                {
                    key: value
                    for key, value in item.items()
                    if not key.startswith("_")
                }
                for item in accepted.values()
            ),
            key=lambda item: (DOMAINS.index(item["domain"]), item["rule_id"]),
        ),
        sorted(conflicts, key=lambda item: item["rule_id"]),
        sorted(calibrations, key=lambda item: item["rule_id"]),
    )


def load_repository(request: dict[str, Any]) -> dict[str, Any]:
    """Discover and calibrate governance without writing the repository."""

    if not isinstance(request, dict) or set(request) != {
        "contract_version",
        "repository",
    } or not isinstance(request.get("contract_version"), str) or not isinstance(
        request.get("repository"), str
    ):
        return _blocked_load_result(
            [
                _diagnostic(
                    "LOAD_REQUEST_INVALID",
                    "load request must contain contract_version and repository",
                )
            ]
        )
    if request["contract_version"] != LOAD_CONTRACT_VERSION:
        return _blocked_load_result(
            [
                _diagnostic(
                    "CONTRACT_VERSION_UNSUPPORTED",
                    "load contract version is unsupported",
                    actual=request["contract_version"],
                )
            ],
            repository=(
                str(Path(request["repository"]).resolve())
                if isinstance(request["repository"], str)
                else None
            ),
        )
    repository = Path(request["repository"])
    if not repository.is_dir():
        return _blocked_load_result(
            [
                _diagnostic(
                    "REPOSITORY_NOT_FOUND",
                    "load repository must be an existing directory",
                    actual=str(repository),
                )
            ],
            repository=str(repository.resolve()),
        )
    snapshot = _snapshot(repository)
    facts = _discover_facts(snapshot)
    existing, source_diagnostics, governance_sources, retired_rule_ids = (
        _existing_candidates(repository)
    )
    generated = [
        candidate
        for fact in facts
        if (
            candidate := _generated_candidate(fact)
        )["rule_id"] not in retired_rule_ids
    ]
    candidates, conflicts, calibrations = _calibrate(
        [*generated, *existing]
    )
    diagnostics = sorted(
        [*source_diagnostics, *conflicts],
        key=lambda item: (
            item.get("source", ""),
            item.get("rule_id", ""),
            item["code"],
        ),
    )
    result: dict[str, Any] = {
        "status": "blocked" if diagnostics else "ready",
        "contract_version": LOAD_CONTRACT_VERSION,
        "repository": str(repository.resolve()),
        "snapshot_digest": canonical_digest(snapshot),
        "facts": facts,
        "governance_sources": governance_sources,
        "candidates": candidates,
        "calibrations": calibrations,
        "diagnostics": diagnostics,
    }
    result["result_digest"] = canonical_digest(result)
    return result
