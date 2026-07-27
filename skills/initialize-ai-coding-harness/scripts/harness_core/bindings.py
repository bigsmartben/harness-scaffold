"""Validate one Grant → Manifest → Selection → Request execution chain."""

from __future__ import annotations

from fnmatch import fnmatch
from typing import Any

from .artifacts import SCHEMA_VERSION, canonical_digest, digest_matches
from .automation import CRITICAL_CATEGORIES
from .contracts import runtime_artifact_is_valid


def _path_matches(path: str, pattern: str) -> bool:
    normalized = path.replace("\\", "/")
    return fnmatch(normalized, pattern) or (
        pattern.startswith("**/") and fnmatch(normalized, pattern[3:])
    )


def execution_binding_blockers(
    grant: dict[str, Any] | None,
    manifest: dict[str, Any] | None,
    selection: dict[str, Any] | None,
    request: dict[str, Any] | None,
    confirmation: dict[str, Any] | None = None,
    platform: dict[str, Any] | None = None,
) -> list[str]:
    """Return stable blockers for stale authority or cross-chain mismatches."""

    if (
        not isinstance(grant, dict)
        or not runtime_artifact_is_valid(grant)
        or grant.get("artifact_type") != "work-grant"
        or grant.get("schema_version") != SCHEMA_VERSION
        or grant.get("status") != "active"
        or not digest_matches(grant, "grant_digest")
    ):
        return ["GRANT_STALE", "HANDOFF_REQUIRED"]

    scopes = grant.get("write_scope", [])
    changed_paths = manifest.get("changed_paths", []) if isinstance(manifest, dict) else []
    if any(
        not any(_path_matches(str(path), str(scope)) for scope in scopes)
        for path in changed_paths
    ):
        return ["GRANT_STALE", "HANDOFF_REQUIRED"]

    delivery_target = grant.get("delivery_target")
    request_target = request.get("target") if isinstance(request, dict) else None
    if delivery_target is not None and request_target != delivery_target:
        return ["GRANT_STALE", "HANDOFF_REQUIRED"]

    artifacts = (
        (manifest, "change-manifest", "manifest_digest"),
        (selection, "selection", "selection_digest"),
        (request, "task-request", "request_digest"),
    )
    if any(
        not isinstance(artifact, dict)
        or not runtime_artifact_is_valid(artifact)
        or artifact.get("artifact_type") != artifact_type
        or artifact.get("schema_version") != SCHEMA_VERSION
        or not digest_matches(artifact, digest_field)
        for artifact, artifact_type, digest_field in artifacts
    ):
        return ["EVIDENCE_BINDING_MISMATCH", "HANDOFF_REQUIRED"]

    expected_diff = canonical_digest(
        sorted(
            {
                str(path).replace("\\", "/")
                for path in manifest["changed_paths"]
            }
        )
    )
    selected = {
        item.get("task_id"): item
        for item in selection.get("selected_tasks", [])
        if isinstance(item, dict)
    }
    selected_task = selected.get(request.get("task_id"))
    task_is_bound = (
        request.get("action_semantics") in CRITICAL_CATEGORIES
        or selected_task is not None
    )
    same_chain = (
        manifest["grant_digest"] == grant["grant_digest"]
        and selection["manifest_digest"] == manifest["manifest_digest"]
        and selection["diff_digest"] == expected_diff
        and selection.get("status") != "blocked"
        and request["grant_digest"] == grant["grant_digest"]
        and request["manifest_digest"] == manifest["manifest_digest"]
        and request["selection_digest"] == selection["selection_digest"]
        and request.get("validation_level") == selection.get("validation_level")
        and task_is_bound
        and (
            selected_task is None
            or selected_task.get("automation_level")
            == request.get("automation_level")
        )
    )
    if confirmation is not None:
        same_chain = same_chain and (
            runtime_artifact_is_valid(confirmation)
            and confirmation.get("artifact_type") == "confirmation"
            and confirmation.get("schema_version") == SCHEMA_VERSION
            and confirmation.get("confirmation_status") == "confirmed"
            and confirmation.get("request_digest") == request["request_digest"]
        )
    if platform is not None:
        same_chain = same_chain and (
            runtime_artifact_is_valid(platform)
            and platform.get("artifact_type") == "platform-evidence"
            and platform.get("schema_version") == SCHEMA_VERSION
            and digest_matches(platform, "platform_evidence_digest")
            and platform.get("request_digest") == request["request_digest"]
            and platform.get("commit_sha") == request["commit_sha"]
            and (
                request.get("artifact_digest") is None
                or platform.get("artifact_digest") == request["artifact_digest"]
            )
            and (
                request.get("environment") is None
                or platform.get("protected_environment")
                == request.get("environment")
            )
        )
    return [] if same_chain else ["EVIDENCE_BINDING_MISMATCH", "HANDOFF_REQUIRED"]
