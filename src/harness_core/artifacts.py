"""Canonical JSON and digest helpers for Harness 4."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

from .model import (
    CORE_VERSION,
    PROJECTION_COMPILER_VERSION,
    SCHEMA_VERSION,
)


GOVERNANCE_SCHEMA_VERSION = SCHEMA_VERSION


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


def digest_matches(document: dict[str, Any], digest_field: str) -> bool:
    recorded = document.get(digest_field)
    return isinstance(recorded, str) and recorded == artifact_digest(
        document, digest_field
    )
