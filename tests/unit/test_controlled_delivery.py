from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from harness_core.codex_adapter import runtime_state
from harness_core.contracts import validate_runtime_artifact
from harness_core.decisions import create_task_decision
from harness_core.delivery import (
    build_controlled_delivery_plan,
    build_platform_gate_evidence,
    delivery_decision_target,
    execute_controlled_delivery_plan,
    validate_controlled_delivery_receipt,
)
from harness_core.workspace import workspace_state

from conftest import git, initialize


ARTIFACT = "sha256:" + "a" * 64


def _targets(repository: Path) -> dict[str, dict]:
    state = workspace_state(repository)
    return {
        "delivery:pull-request": {
            "provider": "github",
            "repository": "owner/repo",
            "base_ref": "refs/heads/main",
            "head_ref": state["head_ref"],
            "title": "Harness 2.0",
            "body": "Exact changes.",
            "draft": True,
            "commit_sha": state["base_commit"],
        },
        "delivery:merge": {
            "provider": "github",
            "repository": "owner/repo",
            "pull_request_number": 22,
            "method": "squash",
            "expected_head_sha": state["base_commit"],
        },
        "delivery:publish": {
            "provider": "github",
            "repository": "owner/repo",
            "package": "sdd-harness",
            "version": "2.0.0",
            "registry": "pypi",
            "artifact_digest": ARTIFACT,
        },
        "delivery:release": {
            "provider": "github",
            "repository": "owner/repo",
            "tag": "v2.0.0",
            "commit_sha": state["base_commit"],
            "title": "Harness 2.0",
            "notes": "Release notes.",
            "artifact_digests": [ARTIFACT],
        },
        "delivery:deploy": {
            "provider": "github",
            "repository": "owner/repo",
            "environment": "production",
            "commit_sha": state["base_commit"],
            "artifact_digest": ARTIFACT,
        },
    }


def _receipt(plan: dict) -> dict:
    target = plan["target"]
    common = {
        "status": "succeeded",
        "provider": "github",
        "repository": target["repository"],
        "action_id": plan["action_id"],
        "target_digest": plan["target_digest"],
    }
    if plan["semantics"] == "pull-request":
        evidence = {
            "pull_request_number": 22,
            "url": "https://github.test/owner/repo/pull/22",
            "base_ref": target["base_ref"],
            "head_ref": target["head_ref"],
            "head_sha": target["commit_sha"],
            "draft": target["draft"],
        }
    elif plan["semantics"] == "merge":
        evidence = {
            "pull_request_number": target["pull_request_number"],
            "head_sha": target["expected_head_sha"],
            "merge_commit_sha": "abc123",
            "method": target["method"],
        }
    elif plan["semantics"] == "publish":
        evidence = {
            key: target[key]
            for key in ("package", "version", "registry", "artifact_digest")
        }
    elif plan["semantics"] == "release":
        evidence = {
            "tag": target["tag"],
            "commit_sha": target["commit_sha"],
            "artifact_digests": target["artifact_digests"],
            "url": "https://github.test/owner/repo/releases/v2.0.0",
        }
    else:
        evidence = {
            "environment": target["environment"],
            "commit_sha": target["commit_sha"],
            "artifact_digest": target["artifact_digest"],
            "deployment_id": "deployment-22",
        }
    return {**common, "evidence": evidence}


def _gate(action_id: str, target: dict) -> dict:
    return build_platform_gate_evidence(
        action_id=action_id,
        target=target,
        checks=[
            {
                "name": "required-checks",
                "status": "passed",
                "source": "github://owner/repo/rules",
                "evidence_id": "ruleset-22",
            }
        ],
    )


@pytest.mark.parametrize(
    "action_id",
    [
        "delivery:pull-request",
        "delivery:merge",
        "delivery:publish",
        "delivery:release",
        "delivery:deploy",
    ],
)
def test_controlled_delivery_is_source_bound_decision_bound_and_evidenced(
    private_repository: Path,
    action_id: str,
) -> None:
    initialize(private_repository)
    target = _targets(private_repository)[action_id]
    plan = build_controlled_delivery_plan(
        private_repository,
        action_id=action_id,
        target=target,
        platform_evidence=_gate(action_id, target),
    )
    assert plan["blocker_codes"] == []
    assert validate_runtime_artifact(plan) == []

    runtime = runtime_state(private_repository)
    workspace = workspace_state(private_repository)
    decision = create_task_decision(
        task_id=f"deliver-{plan['semantics']}",
        projection_id=runtime["projection_id"],
        workspace_digest=workspace["workspace_digest"],
        exact_action=action_id,
        target=delivery_decision_target(plan),
    )
    calls: list[dict] = []
    result = execute_controlled_delivery_plan(
        private_repository,
        plan,
        decision=decision,
        provider_writer=lambda request: calls.append(request) or _receipt(plan),
    )

    assert result["status"] == "delivered"
    assert len(calls) == 1
    assert calls[0]["target_digest"] == plan["target_digest"]
    assert result["receipt"]["action_id"] == action_id


def test_delivery_never_calls_provider_without_exact_decision_or_current_plan(
    private_repository: Path,
) -> None:
    initialize(private_repository)
    target = _targets(private_repository)["delivery:pull-request"]
    plan = build_controlled_delivery_plan(
        private_repository,
        action_id="delivery:pull-request",
        target=target,
        platform_evidence=_gate("delivery:pull-request", target),
    )
    calls: list[dict] = []

    blocked = execute_controlled_delivery_plan(
        private_repository,
        plan,
        decision=None,
        provider_writer=lambda request: calls.append(request) or _receipt(plan),
    )
    assert blocked["blocker_codes"] == [
        "TASK_DECISION_REQUIRED",
        "HANDOFF_REQUIRED",
    ]
    assert calls == []

    tampered = deepcopy(plan)
    tampered["target"]["title"] = "Changed"
    blocked = execute_controlled_delivery_plan(
        private_repository,
        tampered,
        decision=None,
        provider_writer=lambda request: calls.append(request) or _receipt(plan),
    )
    assert blocked["blocker_codes"] == ["CONTROLLED_DELIVERY_PLAN_STALE"]
    assert calls == []


def test_delivery_failure_and_incomplete_receipt_fail_closed(
    private_repository: Path,
) -> None:
    initialize(private_repository)
    target = _targets(private_repository)["delivery:publish"]
    plan = build_controlled_delivery_plan(
        private_repository,
        action_id="delivery:publish",
        target=target,
        platform_evidence=_gate("delivery:publish", target),
    )
    runtime = runtime_state(private_repository)
    decision = create_task_decision(
        task_id="publish-once",
        projection_id=runtime["projection_id"],
        workspace_digest=workspace_state(private_repository)["workspace_digest"],
        exact_action=plan["action_id"],
        target=delivery_decision_target(plan),
    )

    failed = execute_controlled_delivery_plan(
        private_repository,
        plan,
        decision=decision,
        provider_writer=lambda _request: (_ for _ in ()).throw(
            RuntimeError("provider unavailable")
        ),
    )
    assert failed["blocker_codes"] == [
        "REMOTE_DELIVERY_FAILED",
        "HANDOFF_REQUIRED",
    ]

    receipt = _receipt(plan)
    receipt["evidence"]["artifact_digest"] = "sha256:" + "b" * 64
    assert validate_controlled_delivery_receipt(plan, receipt) == [
        "GOVERNANCE_EVIDENCE_INCOMPLETE",
        "HANDOFF_REQUIRED",
    ]


def test_delivery_plan_blocks_controlled_and_unclassified_branches(
    private_repository: Path,
) -> None:
    initialize(private_repository)
    git(private_repository, "add", ".")
    git(private_repository, "commit", "-m", "initialize")
    git(private_repository, "checkout", "-b", "main")
    plan = build_controlled_delivery_plan(
        private_repository,
        action_id="delivery:pull-request",
        target=(target := _targets(private_repository)[
            "delivery:pull-request"
        ]),
        platform_evidence=_gate("delivery:pull-request", target),
    )
    assert "CONTROLLED_BRANCH_GATE_REQUIRED" in plan["blocker_codes"]
    assert "HANDOFF_REQUIRED" in plan["blocker_codes"]

    git(private_repository, "checkout", "-b", "feature/unclassified")
    plan = build_controlled_delivery_plan(
        private_repository,
        action_id="delivery:pull-request",
        target=(target := _targets(private_repository)[
            "delivery:pull-request"
        ]),
        platform_evidence=_gate("delivery:pull-request", target),
    )
    assert "CONTROLLED_BRANCH_GATE_REQUIRED" in plan["blocker_codes"]
    assert "HANDOFF_REQUIRED" in plan["blocker_codes"]


def test_delivery_requires_current_platform_gate_before_provider_call(
    private_repository: Path,
) -> None:
    initialize(private_repository)
    action_id = "delivery:deploy"
    target = _targets(private_repository)[action_id]
    missing = build_controlled_delivery_plan(
        private_repository,
        action_id=action_id,
        target=target,
        platform_evidence=None,
    )
    assert missing["blocker_codes"] == [
        "HANDOFF_REQUIRED",
        "PLATFORM_GATE_REQUIRED",
    ]
    assert validate_runtime_artifact(missing) == []

    gate = _gate(action_id, target)
    gate["checks"][0]["status"] = "failed"
    tampered = build_controlled_delivery_plan(
        private_repository,
        action_id=action_id,
        target=target,
        platform_evidence=gate,
    )
    assert tampered["blocker_codes"] == [
        "HANDOFF_REQUIRED",
        "PLATFORM_GATE_REQUIRED",
    ]

    unresolved = build_controlled_delivery_plan(
        private_repository,
        action_id="delivery:unknown",
        target={},
        platform_evidence=None,
    )
    assert "TOOL_BINDING_AMBIGUOUS" in unresolved["blocker_codes"]
    assert validate_runtime_artifact(unresolved) == []
