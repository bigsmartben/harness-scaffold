"""Canonical JSON and SHA-256 helpers for runtime artifact bindings."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any


ABSENT = "absent"
ABSENT_DIGEST = ABSENT
SCHEMA_VERSION = "0.3.0"
GOVERNANCE_SCHEMA_VERSION = "1.0.0"
CORE_VERSION = "1.0.0"
PROJECTION_COMPILER_VERSION = "1.0.0"


def canonical_json_bytes(
    document: Any,
    *,
    exclude_field: str | None = None,
) -> bytes:
    """Return UTF-8 canonical JSON with recursive key sorting and no padding."""

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
    """Return a lowercase SHA-256 digest for a canonical JSON document."""

    digest = hashlib.sha256(
        canonical_json_bytes(document, exclude_field=exclude_field)
    ).hexdigest()
    return f"sha256:{digest}"


def canonical_json(
    document: Any,
    *,
    exclude_field: str | None = None,
) -> str:
    """Return the canonical JSON text used for runtime artifact digests."""

    return canonical_json_bytes(
        document, exclude_field=exclude_field
    ).decode("utf-8")


def artifact_digest(document: Any, digest_field: str) -> str:
    """Return an artifact digest while excluding only its own digest field."""

    return canonical_digest(document, exclude_field=digest_field)


def attach_digest(
    document: dict[str, Any],
    digest_field: str,
) -> dict[str, Any]:
    """Return a copy with a canonical digest attached."""

    result = deepcopy(document)
    result[digest_field] = artifact_digest(result, digest_field)
    return result


def content_digest(content: str | bytes) -> str:
    """Return a lowercase SHA-256 digest for exact file content."""

    payload = content.encode("utf-8") if isinstance(content, str) else content
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def path_digest(path: Path) -> str:
    """Return the exact file digest, or the stable `absent` sentinel."""

    return content_digest(path.read_bytes()) if path.is_file() else ABSENT


def file_digest(path: Path) -> str:
    """Compatibility name for exact file or absent-state hashing."""

    return path_digest(path)


def normalized_path_digest(repository: Path, relative_path: str) -> str:
    """Hash a normalized repository-relative file path without escaping root."""

    root = repository.resolve()
    target = (root / relative_path.replace("\\", "/")).resolve()
    if not target.is_relative_to(root):
        raise ValueError(f"path escapes repository: {relative_path}")
    return path_digest(target)


def digest_matches(
    document: dict[str, Any],
    digest_field: str,
) -> bool:
    """Check that an artifact's recorded digest matches its canonical payload."""

    recorded = document.get(digest_field)
    return isinstance(recorded, str) and recorded == canonical_digest(
        document, exclude_field=digest_field
    )


def verify_digest(
    document: dict[str, Any],
    digest_field: str,
) -> bool:
    """Compatibility name for canonical runtime digest verification."""

    return digest_matches(document, digest_field)
