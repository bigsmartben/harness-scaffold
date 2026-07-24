from __future__ import annotations

import sys
from pathlib import Path

import pytest

from harness_core import (
    EVIDENCE_FIELDS,
    create_external_request,
    create_task_request,
    effective_automation,
    evaluate_merge,
    execute_publish,
    request_digest,
    resolve_action_policy,
    run_github_actions_task,
    run_local_task,
    route_intent,
    select_validation,
)


TASKS = {
    "tasks": [
        {
            "id": "test:unit",
            "category": "test",
            "automation_level": "routine",
            "auto_allowed": True,
            "backend": "local",
            "working_directory": "repository-root",
            "supports_scope": "affected",
            "timeout": "5s",
            "outputs": {"report": ".harness/reports/unit.json"},
        },
        {
            "id": "test:contract",
            "category": "test",
            "automation_level": "routine",
            "auto_allowed": True,
            "backend": "local",
            "working_directory": "repository-root",
            "supports_scope": "contract",
            "timeout": "5s",
            "outputs": {"report": ".harness/reports/contract.json"},
        },
        {
            "id": "publish:package",
            "category": "publish",
            "automation_level": "critical",
            "auto_allowed": False,
            "backend": "local",
            "working_directory": "repository-root",
            "supports_scope": "publish",
            "timeout": "5s",
            "outputs": {"report": ".harness/reports/publish.json"},
        },
    ]
}
IMPACT = {
    "rules": [
        {
            "id": "docs",
            "paths": ["**/*.md"],
            "validation_level": "inspect",
            "tasks": [],
        },
        {
            "id": "source",
            "paths": ["src/**"],
            "validation_level": "affected",
            "tasks": ["test:unit"],
        },
        {
            "id": "harness",
            "paths": [".harness/**"],
            "validation_level": "full",
            "tasks": ["test:unit"],
        },
    ]
}


def _select(
    paths: list[str], facts: dict | None = None, recommended: list[str] | None = None
) -> dict:
    manifest = {"paths": paths, "recommended_tasks": recommended or []}
    return select_validation(manifest, paths, IMPACT, TASKS, facts)


def test_document_change_selects_inspect() -> None:
    result = _select(["README.md"])

    assert result["status"] == "selected"
    assert result["validation_level"] == "inspect"
    assert result["selected_tasks"] == []


def test_single_module_change_selects_affected() -> None:
    result = _select(["src/orders/service.py"])

    assert result["validation_level"] == "affected"
    assert [item["task_id"] for item in result["selected_tasks"]] == ["test:unit"]


def test_public_contract_fact_upgrades_to_contract() -> None:
    result = _select(
        ["src/api.py"], {"public_contract_paths": ["src/api.py"]}
    )

    assert result["validation_level"] == "contract"


def test_full_requires_dm004_fact() -> None:
    result = _select([".harness/tasks.yaml"])

    assert result["status"] == "blocked"
    assert result["blocker_codes"] == ["IMPACT_UNRESOLVED"]
    assert result["validation_level"] == "inspect"


def test_dm004_fact_selects_full_but_excludes_publish() -> None:
    result = _select(
        ["src/orders/service.py"],
        {"merge_policy_requires_full": True},
        recommended=["publish:package"],
    )

    assert result["validation_level"] == "full"
    assert result["status"] == "confirmation-required"
    assert result["backend_calls"] == 0
    assert {item["task_id"] for item in result["selected_tasks"]} == {
        "test:unit",
        "test:contract",
    }
    assert {
        item["automation_level"]
        for item in result["confirmation_required_tasks"]
    } == {"expensive"}
    assert any("not selected" in reason for reason in result["reasons"])


def test_manifest_mismatch_and_unknown_impact_block_without_full() -> None:
    result = select_validation(
        {"paths": ["src/a.py"]}, ["unmapped/file.xyz"], IMPACT, TASKS
    )

    assert result["status"] == "blocked"
    assert result["validation_level"] == "inspect"
    assert result["blocker_codes"] == ["IMPACT_UNRESOLVED"]


def _task(backend: str = "local") -> dict:
    return {
        "id": "test:unit",
        "category": "test",
        "automation_level": "routine",
        "auto_allowed": True,
        "backend": backend,
        "working_directory": "repository-root",
        "supports_scope": "affected",
        "timeout": "5s",
        "outputs": {"report": ".harness/reports/unit.json"},
    }


def test_local_success_returns_complete_evidence(tmp_path: Path) -> None:
    evidence = run_local_task(
        _task(),
        [sys.executable, "-c", "print('ok')"],
        tmp_path,
        "affected",
        change_manifest="sha256:manifest",
        selection="sha256:selection",
    )

    assert set(evidence) == EVIDENCE_FIELDS
    assert evidence["status"] == "passed"
    assert evidence["primary_error"] is None
    assert (tmp_path / evidence["full_log"]).read_text("utf-8") == "ok\n"


def test_local_failure_summarizes_first_error_without_embedding_log(
    tmp_path: Path,
) -> None:
    evidence = run_local_task(
        _task(),
        [
            sys.executable,
            "-c",
            "import sys; print('first error', file=sys.stderr); print('detail', file=sys.stderr); raise SystemExit(2)",
        ],
        tmp_path,
        "affected",
    )

    assert evidence["status"] == "failed"
    assert evidence["primary_error"] == "first error"
    assert "detail" not in evidence["summary"]
    assert "detail" not in str({k: v for k, v in evidence.items() if k != "full_log"})


def test_github_actions_uses_same_evidence_shape(tmp_path: Path) -> None:
    evidence = run_github_actions_task(
        _task("github-actions"),
        lambda task: {
            "run_id": "123",
            "status": "passed",
            "log": "ok\n",
            "workflow": ".github/workflows/ci.yml",
            "commit_sha": "abc123",
        },
        tmp_path,
        "affected",
        change_manifest="sha256:manifest",
        selection="sha256:selection",
    )

    assert set(evidence) == EVIDENCE_FIELDS
    assert evidence["backend"] == "github-actions"
    assert evidence["status"] == "passed"


def test_merge_without_bound_complete_evidence_stays_blocked() -> None:
    pipeline = {
        "stages": [
            {"id": "test", "tasks": ["test:unit"], "requires_evidence": True}
        ]
    }

    result = evaluate_merge(pipeline, [{"task_id": "test:unit", "status": "passed"}])

    assert result["status"] == "blocked"
    assert result["blocker_codes"] == ["EVIDENCE_INCOMPLETE"]


def test_publish_without_current_confirmation_does_not_call_backend() -> None:
    calls = 0

    def backend() -> str:
        nonlocal calls
        calls += 1
        return "published"

    pipeline = {"requires_independent_confirmation": True}
    request = {"version": "1.2.3", "artifact": "dist/a.whl", "target": "pypi"}

    result = execute_publish(pipeline, request, None, backend)

    assert result["status"] == "blocked"
    assert result["backend_calls"] == 0
    assert calls == 0


def test_publish_current_confirmation_calls_backend_once() -> None:
    calls = 0

    def backend() -> str:
        nonlocal calls
        calls += 1
        return "published"

    pipeline = {"requires_independent_confirmation": True}
    request = {"version": "1.2.3", "artifact": "dist/a.whl", "target": "pypi"}
    confirmation = {
        "confirmed": True,
        "request_digest": request_digest(request),
    }

    platform = {
        "workflow": ".github/workflows/publish.yml",
        "commit_sha": "abc123",
        "protected_environment": "production",
        "approval_status": "approved",
    }
    result = execute_publish(pipeline, request, confirmation, backend, platform)

    assert result["status"] == "passed"
    assert result["backend_calls"] == 1
    assert calls == 1


@pytest.mark.parametrize(
    ("task_id", "category", "scope"),
    [
        ("test:integration", "test", "integration"),
        ("test:e2e", "test", "affected"),
        ("ci:full", "ci", "full"),
        ("build:large", "build", "affected"),
    ],
)
def test_expensive_task_never_runs_without_current_confirmation(
    tmp_path: Path, task_id: str, category: str, scope: str
) -> None:
    calls = 0
    task = {
        **_task("github-actions"),
        "id": task_id,
        "category": category,
        "automation_level": "expensive",
        "auto_allowed": False,
        "supports_scope": scope,
    }

    def dispatch(_: dict) -> dict:
        nonlocal calls
        calls += 1
        return {"run_id": "should-not-exist", "status": "passed"}

    evidence = run_github_actions_task(
        task, dispatch, tmp_path, scope
    )

    assert evidence["status"] == "blocked"
    assert evidence["backend_calls"] == 0
    assert evidence["blocker_codes"] == ["HANDOFF_REQUIRED"]
    assert calls == 0


def test_expensive_task_runs_only_with_matching_request_and_confirmation(
    tmp_path: Path,
) -> None:
    task = {
        **_task("github-actions"),
        "id": "test:integration",
        "automation_level": "expensive",
        "auto_allowed": False,
        "supports_scope": "integration",
    }
    task_request = create_task_request(
        task, "integration", {"commit_sha": "abc123", "target": "ci"}
    )
    confirmation = {
        "confirmed": True,
        "request_digest": task_request["request_digest"],
    }
    evidence = run_github_actions_task(
        task,
        lambda _: {
            "run_id": "456",
            "status": "passed",
            "log": "ok\n",
            "workflow": ".github/workflows/ci.yml",
            "commit_sha": "abc123",
        },
        tmp_path,
        "integration",
        request=task_request["request"],
        confirmation=confirmation,
    )

    assert evidence["status"] == "passed"
    assert evidence["backend_calls"] == 1
    assert evidence["automation_level"] == "expensive"


def test_critical_github_run_requires_complete_platform_evidence(
    tmp_path: Path,
) -> None:
    task = {
        **_task("github-actions"),
        "id": "publish:package",
        "category": "publish",
        "automation_level": "critical",
        "auto_allowed": False,
        "supports_scope": "publish",
    }
    task_request = create_task_request(
        task, "publish", {"commit_sha": "abc123", "target": "production"}
    )
    confirmation = {
        "confirmed": True,
        "request_digest": task_request["request_digest"],
    }

    incomplete = run_github_actions_task(
        task,
        lambda _: {
            "run_id": "789",
            "status": "passed",
            "log": "published\n",
            "workflow": ".github/workflows/publish.yml",
            "commit_sha": "abc123",
            "approval_status": "approved",
            "protected_environment": "production",
        },
        tmp_path,
        "publish",
        request=task_request["request"],
        confirmation=confirmation,
    )
    complete = run_github_actions_task(
        task,
        lambda _: {
            "run_id": "790",
            "status": "passed",
            "log": "published\n",
            "workflow": ".github/workflows/publish.yml",
            "commit_sha": "abc123",
            "approval_status": "approved",
            "approver": "maintainer",
            "protected_environment": "production",
            "artifact_digest": "sha256:artifact",
        },
        tmp_path,
        "publish",
        request=task_request["request"],
        confirmation=confirmation,
    )

    assert incomplete["status"] == "blocked"
    assert incomplete["formal_authority"] is False
    assert incomplete["blocker_codes"] == ["EVIDENCE_INCOMPLETE"]
    assert complete["status"] == "passed"
    assert complete["formal_authority"] is True
    assert complete["platform"]["run_id"] == "790"
    assert (
        complete["platform"]["request_digest"]
        == task_request["request_digest"]
    )


def test_critical_semantics_override_incorrect_declared_level() -> None:
    task = {
        **_task(),
        "id": "merge:main",
        "category": "merge",
        "automation_level": "routine",
        "auto_allowed": True,
    }

    automation = effective_automation(task, "affected")

    assert automation["automation_level"] == "critical"
    assert automation["auto_allowed"] is False
    assert automation["configuration_errors"]


def test_same_semantic_task_has_same_gate_across_channels() -> None:
    task = {
        **_task(),
        "id": "publish:release",
        "category": "publish",
        "automation_level": "critical",
        "auto_allowed": False,
    }
    tools = {
        "tools": [
            {
                "id": f"{channel}:publish",
                "type": channel,
                "invocation_mode": "managed",
                "task_ref": "publish:release",
            }
            for channel in ("shell", "cli", "mcp-tool", "external-api")
        ]
    }
    policies = [
        resolve_action_policy(
            item["id"], tools, {"tasks": [task]}, "publish"
        )
        for item in tools["tools"]
    ]

    assert {policy["automation_level"] for policy in policies} == {"critical"}
    assert {policy["status"] for policy in policies} == {"confirmation-required"}
    assert {policy["task_id"] for policy in policies} == {"publish:release"}


def test_ordinary_actions_remain_direct_without_harness_confirmation() -> None:
    tools = {
        "tools": [
            {
                "id": "mcp:read-file",
                "type": "mcp-tool",
                "invocation_mode": "direct",
            },
            {
                "id": "shell:inspect",
                "type": "shell",
                "invocation_mode": "direct",
            },
        ]
    }

    policies = [
        resolve_action_policy(item["id"], tools, {"tasks": []})
        for item in tools["tools"]
    ]

    assert {policy["status"] for policy in policies} == {"direct"}
    assert all(policy["confirmation_required"] is False for policy in policies)


@pytest.mark.parametrize(
    ("task_id", "category"),
    [
        ("push:main", "push"),
        ("merge:main", "merge"),
        ("publish:package", "publish"),
        ("release:github", "release"),
        ("deploy:production", "deploy"),
    ],
)
def test_each_critical_action_has_zero_backend_calls_without_confirmation(
    tmp_path: Path, task_id: str, category: str
) -> None:
    calls = 0
    task = {
        **_task("github-actions"),
        "id": task_id,
        "category": category,
        "automation_level": "critical",
        "auto_allowed": False,
    }

    def dispatch(_: dict) -> dict:
        nonlocal calls
        calls += 1
        return {"run_id": "should-not-exist", "status": "passed"}

    evidence = run_github_actions_task(
        task, dispatch, tmp_path, "publish" if category != "merge" else "affected"
    )

    assert evidence["status"] == "blocked"
    assert evidence["backend_calls"] == 0
    assert calls == 0


@pytest.mark.parametrize("level", ["integration", "full"])
def test_high_cost_validation_overrides_routine_task_and_requires_confirmation(
    tmp_path: Path, level: str
) -> None:
    calls = 0

    def dispatch(_: dict) -> dict:
        nonlocal calls
        calls += 1
        return {"run_id": "should-not-exist", "status": "passed"}

    evidence = run_github_actions_task(
        _task("github-actions"), dispatch, tmp_path, level
    )

    assert evidence["automation_level"] == "expensive"
    assert evidence["backend_calls"] == 0
    assert calls == 0


def test_merge_complete_evidence_still_requires_current_confirmation() -> None:
    pipeline = {
        "stages": [
            {"id": "test", "tasks": ["test:unit"], "requires_evidence": True}
        ]
    }
    evidence = [
        {
            "task_id": "test:unit",
            "status": "passed",
            "change_manifest": "sha256:manifest",
            "selection": "sha256:selection",
        }
    ]

    result = evaluate_merge(pipeline, evidence)

    assert result["status"] == "confirmation-required"
    assert result["backend_calls"] == 0
    assert result["blocker_codes"] == ["HANDOFF_REQUIRED"]


def test_merge_requires_platform_required_checks_after_confirmation() -> None:
    pipeline = {
        "stages": [
            {"id": "test", "tasks": ["test:unit"], "requires_evidence": True}
        ]
    }
    evidence = [
        {
            "task_id": "test:unit",
            "status": "passed",
            "change_manifest": "sha256:manifest",
            "selection": "sha256:selection",
        }
    ]
    request = {"task_id": "merge:main", "target": "main", "commit_sha": "abc"}
    confirmation = {
        "confirmed": True,
        "request_digest": request_digest(request),
    }

    blocked = evaluate_merge(pipeline, evidence, request, confirmation)
    passed = evaluate_merge(
        pipeline,
        evidence,
        request,
        confirmation,
        {
            "workflow": ".github/workflows/merge.yml",
            "commit_sha": "abc",
            "required_checks": "passed",
        },
    )

    assert blocked["status"] == "blocked"
    assert blocked["backend_calls"] == 0
    assert passed["status"] == "passed"
    assert passed["backend_calls"] == 1


def test_publish_confirmation_without_platform_approval_does_not_dispatch() -> None:
    calls = 0

    def backend() -> str:
        nonlocal calls
        calls += 1
        return "published"

    pipeline = {"requires_independent_confirmation": True}
    request = {"version": "1.2.3", "artifact": "dist/a.whl", "target": "pypi"}
    confirmation = {
        "confirmed": True,
        "request_digest": request_digest(request),
    }

    result = execute_publish(pipeline, request, confirmation, backend)

    assert result["status"] == "blocked"
    assert result["backend_calls"] == 0
    assert result["blocker_codes"] == ["EVIDENCE_INCOMPLETE"]
    assert calls == 0


def test_work_verify_merge_publish_expressions_route_to_one_skill() -> None:
    examples = {
        "请在已批准范围内实现订单状态修改": "work",
        "验证这次 Python 改动需要哪些测试": "verify",
        "现有 Evidence 是否已经可以合并？": "merge",
        "为版本 1.2.3 准备发布计划": "publish",
    }

    assert {text: route_intent(text) for text in examples} == examples


def test_external_event_creates_request_without_backend_call() -> None:
    result = create_external_request(
        {"type": "push", "ref": "refs/heads/main"}, "merge:default"
    )

    assert result["status"] == "blocked"
    assert result["backend_calls"] == 0
    assert result["blocker_codes"] == ["HANDOFF_REQUIRED"]
