"""Canonical artifact and content digest helpers for Harness 2.0."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "2.0.0"
GOVERNANCE_SCHEMA_VERSION = SCHEMA_VERSION
CORE_VERSION = SCHEMA_VERSION
PROJECTION_COMPILER_VERSION = SCHEMA_VERSION
ABSENT = "absent"
ABSENT_DIGEST = ABSENT


def canonical_json_bytes(
    document: Any,
    *,
    exclude_field: str | None = None,
) -> bytes:
    """Serialize a value as deterministic UTF-8 JSON."""

    payload = deepcopy(document)
    if exclude_field is not None and isinstance(payload, dict):
        payload.pop(exclude_field, None)
    return json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_digest(
    document: Any,
    *,
    exclude_field: str | None = None,
) -> str:
    """Return a lowercase SHA-256 digest for canonical JSON."""

    return content_digest(
        canonical_json_bytes(document, exclude_field=exclude_field)
    )


def canonical_json(
    document: Any,
    *,
    exclude_field: str | None = None,
) -> str:
    return canonical_json_bytes(
        document, exclude_field=exclude_field
    ).decode("utf-8")


def artifact_digest(document: Any, digest_field: str) -> str:
    return canonical_digest(document, exclude_field=digest_field)


def attach_digest(
    document: dict[str, Any],
    digest_field: str,
) -> dict[str, Any]:
    result = deepcopy(document)
    result[digest_field] = artifact_digest(result, digest_field)
    return result


def content_digest(content: str | bytes) -> str:
    payload = content.encode("utf-8") if isinstance(content, str) else content
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def path_digest(path: Path) -> str:
    return content_digest(path.read_bytes()) if path.is_file() else ABSENT


file_digest = path_digest


def normalized_path_digest(repository: Path, relative_path: str) -> str:
    root = repository.resolve()
    target = (root / relative_path.replace("\\", "/")).resolve()
    if not target.is_relative_to(root):
        raise ValueError(f"path escapes repository: {relative_path}")
    return path_digest(target)


def digest_matches(document: dict[str, Any], digest_field: str) -> bool:
    recorded = document.get(digest_field)
    return isinstance(recorded, str) and recorded == artifact_digest(
        document, digest_field
    )


verify_digest = digest_matches


def paths_digest(repository: Path, relative_paths: Iterable[str]) -> str:
    """Hash path names and exact contents, including absent paths."""

    root = repository.resolve()
    entries = []
    for relative in sorted(set(relative_paths)):
        normalized = relative.replace("\\", "/")
        entries.append(
            {
                "path": normalized,
                "digest": normalized_path_digest(root, normalized),
            }
        )
    return canonical_digest(entries)
