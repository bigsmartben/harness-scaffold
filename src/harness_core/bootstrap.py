"""Consumer bootstrap and 3.0.1-to-current migration boundary."""

from __future__ import annotations

import os
import re
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from .artifacts import canonical_digest
from .load_core import build_load_request, load_repository
from .package_resources import repo_skill_bytes
from .scaffold import GovernanceRepository


SKILL_RELATIVE_PATH = ".agents/skills/harness/SKILL.md"
LEGACY_ARCHIVE_ROOT = ".harness/legacy/3.0.1"
_VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _is_maintainer_repository(repository: Path) -> bool:
    pyproject = repository / "pyproject.toml"
    return (
        (repository / "src/harness_core/model.py").is_file()
        and pyproject.is_file()
        and 'name = "sdd-harness"' in pyproject.read_text(encoding="utf-8")
    )


def _rewrite_legacy_references(
    result: dict[str, Any],
    archive_root: str,
) -> dict[str, Any]:
    updated = deepcopy(result)
    for candidate in updated["candidates"]:
        for source in candidate["sources"]:
            reference = source["reference"]
            if reference.startswith(".harness/harness.yaml#"):
                source["reference"] = (
                    f"{archive_root}/harness.yaml"
                    + reference.removeprefix(".harness/harness.yaml")
                )
    updated.pop("result_digest", None)
    updated["result_digest"] = canonical_digest(updated)
    return updated


def _legacy_archive_root(config: Path) -> str:
    try:
        document = yaml.safe_load(config.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        document = None
    version = (
        document.get("schema_version")
        if isinstance(document, dict)
        else None
    )
    if not isinstance(version, str) or _VERSION_PATTERN.fullmatch(version) is None:
        version = "unversioned"
    return f".harness/legacy/{version}"


def load_and_bootstrap(repository: Path) -> dict[str, Any]:
    """Load governance, persist state, archive v3 input, and install the Skill."""

    root = repository.resolve()
    if not root.is_dir():
        return {
            "status": "blocked",
            "repository": str(root),
            "diagnostics": [
                {
                    "code": "REPOSITORY_NOT_FOUND",
                    "message": "target repository does not exist",
                }
            ],
        }
    if _is_maintainer_repository(root):
        return {
            "status": "blocked",
            "repository": str(root),
            "diagnostics": [
                {
                    "code": "MAINTAINER_REPOSITORY_FORBIDDEN",
                    "message": (
                        "Harness maintainer root is not a consumer load target"
                    ),
                }
            ],
        }
    skill_path = root / SKILL_RELATIVE_PATH
    expected_skill = repo_skill_bytes()
    existing_skill = (
        skill_path.read_bytes() if skill_path.is_file() else None
    )
    if (
        existing_skill is not None
        and existing_skill != expected_skill
        and b"Harness 3.0" not in existing_skill
    ):
        return {
            "status": "blocked",
            "repository": str(root),
            "diagnostics": [
                {
                    "code": "SKILL_INSTALLATION_CONFLICT",
                    "message": "existing Harness Skill is not a recognized v3 resource",
                }
            ],
        }

    load_result = load_repository(build_load_request(root))
    if load_result["status"] != "ready":
        return {
            "status": "blocked",
            "repository": str(root),
            "load_result": load_result,
            "diagnostics": load_result["diagnostics"],
        }
    legacy_config = root / ".harness/harness.yaml"
    legacy_archive_relative = (
        _legacy_archive_root(legacy_config)
        if legacy_config.is_file()
        else LEGACY_ARCHIVE_ROOT
    )
    if legacy_config.is_file():
        load_result = _rewrite_legacy_references(
            load_result, legacy_archive_relative
        )
    store = GovernanceRepository(root)
    state_existed = store.path.is_file()
    previous_state = store.path.read_bytes() if state_existed else None
    ingested = store.ingest(load_result)
    if ingested["status"] != "loaded":
        return {
            "status": "blocked",
            "repository": str(root),
            "load_result": load_result,
            "diagnostics": ingested["diagnostics"],
        }

    archived_paths: list[str] = []
    moved_paths: list[tuple[Path, Path]] = []
    archive_root = root / legacy_archive_relative
    legacy_targets = [
        (legacy_config, archive_root / "harness.yaml"),
        (
            root / ".harness/governance/model.lock.json",
            archive_root / "model.lock.json",
        ),
    ]
    if (
        existing_skill is not None
        and existing_skill != expected_skill
        and b"Harness 3.0" in existing_skill
    ):
        legacy_targets.append(
            (skill_path, archive_root / "SKILL.md")
        )
    try:
        for source, target in legacy_targets:
            if not source.is_file():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, target)
            moved_paths.append((source, target))
            archived_paths.append(target.relative_to(root).as_posix())
        if not skill_path.is_file() or skill_path.read_bytes() != expected_skill:
            _atomic_write(skill_path, expected_skill)
    except OSError as exc:
        rollback_diagnostics = []
        for source, target in reversed(moved_paths):
            try:
                if target.is_file() and not source.exists():
                    source.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(target, source)
            except OSError as rollback_exc:
                rollback_diagnostics.append(str(rollback_exc))
        try:
            if previous_state is None:
                store.path.unlink(missing_ok=True)
            else:
                _atomic_write(store.path, previous_state)
            if existing_skill is None:
                skill_path.unlink(missing_ok=True)
            elif not skill_path.is_file():
                _atomic_write(skill_path, existing_skill)
        except OSError as rollback_exc:
            rollback_diagnostics.append(str(rollback_exc))
        return {
            "status": "blocked",
            "repository": str(root),
            "diagnostics": [
                {
                    "code": "BOOTSTRAP_WRITE_FAILED",
                    "message": str(exc),
                    "actual": type(exc).__name__,
                    "rollback_diagnostics": rollback_diagnostics,
                }
            ],
        }
    return {
        "status": "loaded",
        "repository": str(root),
        "state_path": store.path.relative_to(root).as_posix(),
        "skill_path": SKILL_RELATIVE_PATH,
        "archived_paths": archived_paths,
        "snapshot_digest": load_result["snapshot_digest"],
        "result_digest": load_result["result_digest"],
        "projection": ingested["projection"],
        "changed": ingested["changed"] or bool(archived_paths),
        "diagnostics": [],
    }
