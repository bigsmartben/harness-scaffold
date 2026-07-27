from __future__ import annotations

import sys
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from harness_core import (
    EVIDENCE_FIELDS,
    attach_digest,
    canonical_digest,
    create_change_manifest,
    create_confirmation,
    create_confirmation_artifact,
    create_external_request,
    create_platform_evidence_artifact,
    create_selection_artifact,
    create_task_request_artifact,
    create_work_grant,
    dispatch_pipeline,
    evaluate_pipeline_readiness,
    finalize_pipeline,
    normalize_github_platform_evidence,
    resolve_action_policy,
    route_intent,
    run_github_actions_task,
    run_git_remote_push_task,
    run_local_task,
    select_validation,
    tool_entry_blockers,
    validate_runtime_artifact,
)


ROOT = Path(__file__).parents[2]
SCHEMAS = (
    ROOT
    / "skills"
    / "initialize-ai-coding-harness"
    / "assets"
    / "schemas"
)
DELIVERY = {
    "push",
    "pull-request",
    "merge",
    "publish",
    "release",
    "deploy",
}


def _task(
    *,
    task_id: str = "test:unit",
    category: str = "test",
    backend: str = "local",
    automation_level: str = "routine",
    auto_allowed: bool = True,
    supports_scope: str = "contract",
    command: list[str] | None = None,
) -> dict:
    task = {
        "id": task_id,
        "category": category,
        "automation_level": automation_level,
        "auto_allowed": auto_allowed,
        "backend": backend,
        "working_directory": "repository-root",
        "supports_scope": supports_scope,
        "timeout": "5s",
        "outputs": {"report": f".harness/reports/{task_id.replace(':', '-')}.json"},
    }
    if backend == "local":
        task["command_source"] = "test-fixture"
        task["command"] = command or [sys.executable, "-c", "print('ok')"]
    elif backend == "git-remote":
        task["source"] = ".harness/adapters/git-remote.yaml#origin"
    else:
        task["source"] = f".github/workflows/{category}.yml#jobs.main"
    return task


def _chain(
    task: dict,
    *,
    level: str = "contract",
    target: str | None = None,
    environment: str | None = None,
    artifact: str | None = None,
    commit_sha: str = "commit123",
) -> dict[str, dict]:
    grant = create_work_grant(
        grant_id="grant:test",
        goal="verify 0.3 execution",
        write_scope=["src/**"],
        merge_target="main",
        delivery_target=target,
        risk_level="high" if task["category"] in DELIVERY else "low",
    )
    manifest = create_change_manifest(
        grant,
        manifest_id="manifest:test",
        base_commit="base123",
        changed_paths=["src/example.py"],
        affected_modules=["example"],
        public_contract_changed=level in {"contract", "integration", "full"},
        recommended_tasks=[task["id"]],
    )
    selection = create_selection_artifact(
        manifest,
        ["src/example.py"],
        {
            "status": "selected",
            "validation_level": level,
            "selected_tasks": [
                {
                    "task_id": task["id"],
                    "automation_level": task["automation_level"],
                    "decision": (
                        "automatic"
                        if task["auto_allowed"]
                        else "confirmation-required"
                    ),
                    "reason": f"selected for {level}",
                }
            ],
            "skipped_tasks": [],
            "reasons": [f"selected {task['id']}"],
            "blocker_codes": [],
        },
        selection_id="selection:test",
    )
    request = create_task_request_artifact(
        task,
        grant,
        manifest,
        selection,
        request_id=f"request:{task['id']}",
        target=target,
        commit_sha=commit_sha,
        source_ref=(
            "refs/heads/feature"
            if task["category"] == "pull-request"
            else None
        ),
        pull_request_number=(
            42 if task["category"] == "merge" else None
        ),
        merge_method=(
            "squash" if task["category"] == "merge" else None
        ),
        version=(
            "1.2.3"
            if task["category"] in {"publish", "release", "deploy"}
            else None
        ),
        artifact_digest=(
            artifact or canonical_digest({"artifact": task["category"]})
            if task["category"] in {"publish", "release", "deploy"}
            else artifact
        ),
        environment=environment,
    )
    return {
        "grant": grant,
        "manifest": manifest,
        "selection": selection,
        "request": request,
    }


class FakeGitHubAdapter:
    def __init__(self, run: dict) -> None:
        self.run = run
        self.calls = {"prepare": 0, "dispatch": 0, "poll": 0, "normalize": 0}

    def prepare(self, task: dict, request: dict) -> dict:
        self.calls["prepare"] += 1
        return {"task_id": task["id"], "request_digest": request["request_digest"]}

    def dispatch(self, prepared: dict) -> dict:
        self.calls["dispatch"] += 1
        return {"run_id": self.run.get("run_id", "missing")}

    def poll(self, locator: dict) -> dict:
        self.calls["poll"] += 1
        return self.run

    def normalize(
        self, run: dict, request: dict, confirmation: dict | None
    ) -> dict:
        self.calls["normalize"] += 1
        return normalize_github_platform_evidence(run, request, confirmation)


def _complete_run(
    *,
    category: str = "test",
    artifact: str | None = None,
) -> dict:
    protected = category in DELIVERY
    return {
        "workflow": f".github/workflows/{category}.yml",
        "run_id": "123",
        "commit_sha": "commit123",
        "status": "passed",
        "log": "ok\n",
        "approval_status": "approved" if protected else "not-required",
        "required_checks": "passed" if category == "merge" else "not-applicable",
        "protected_ref": "main" if category in {"push", "merge"} else None,
        "protected_environment": (
            "production" if category in {"publish", "release", "deploy"} else None
        ),
        "artifact_digest": artifact,
        "source_ref": "github://actions/runs/123",
    }


def test_missing_action_semantics_fails_closed() -> None:
    policy = resolve_action_policy(
        "unknown",
        {"tools": [{"id": "unknown", "type": "cli", "invocation_mode": "direct"}]},
        {"tasks": []},
    )

    assert policy["blocker_codes"] == [
        "ACTION_CLASSIFICATION_UNRESOLVED",
        "HANDOFF_REQUIRED",
    ]


@pytest.mark.parametrize("semantics", sorted(DELIVERY | {"test", "build", "ci"}))
def test_managed_semantics_cannot_be_registered_as_direct(semantics: str) -> None:
    policy = resolve_action_policy(
        f"direct:{semantics}",
        {
            "tools": [
                {
                    "id": f"direct:{semantics}",
                    "type": "shell",
                    "action_semantics": semantics,
                    "invocation_mode": "direct",
                }
            ]
        },
        {"tasks": []},
    )

    assert policy["blocker_codes"] == [
        "TASK_BYPASS_ATTEMPT",
        "HANDOFF_REQUIRED",
    ]


def test_ordinary_action_is_direct_without_harness_confirmation() -> None:
    policy = resolve_action_policy(
        "read:file",
        {
            "tools": [
                {
                    "id": "read:file",
                    "type": "mcp-tool",
                    "action_semantics": "ordinary",
                    "invocation_mode": "direct",
                }
            ]
        },
        {"tasks": []},
    )

    assert policy["status"] == "direct"
    assert policy["blocker_codes"] == []


def test_changed_tool_fact_returns_tool_entry_stale() -> None:
    registered = {
        "type": "cli",
        "entrypoint": "rg",
        "version_source": {"command": "rg", "arguments": ["--version"]},
        "invocation_mode": "direct",
        "action_semantics": "ordinary",
    }
    observed = {**registered, "entrypoint": "different-rg"}

    assert tool_entry_blockers(registered, observed) == [
        "TOOL_ENTRY_STALE",
        "HANDOFF_REQUIRED",
    ]


def test_public_contract_change_adds_contract_capable_task() -> None:
    affected = _task(supports_scope="affected")
    contract = _task(task_id="test:contract", supports_scope="contract")
    grant = create_work_grant(
        grant_id="grant:selection",
        goal="select contracts",
        write_scope=["src/**"],
        merge_target="main",
        delivery_target=None,
        risk_level="low",
    )
    manifest = create_change_manifest(
        grant,
        manifest_id="manifest:selection",
        base_commit="base",
        changed_paths=["src/api.py"],
        public_contract_changed=True,
    )
    result = select_validation(
        manifest,
        ["src/api.py"],
        {
            "rules": [
                {
                    "id": "source",
                    "paths": ["src/**"],
                    "validation_level": "affected",
                    "tasks": ["test:unit"],
                }
            ]
        },
        {"tasks": [affected, contract]},
    )

    assert result["validation_level"] == "contract"
    assert {item["task_id"] for item in result["selected_tasks"]} == {
        "test:unit",
        "test:contract",
    }
    assert validate_runtime_artifact(result, SCHEMAS) == []


def test_selection_rejects_schema_incomplete_manifest_even_with_valid_digest() -> None:
    incomplete_manifest = attach_digest(
        {
            "artifact_type": "change-manifest",
            "schema_version": "0.3.0",
            "manifest_id": "manifest:incomplete",
            "changed_paths": ["src/api.py"],
            "public_contract_changed": False,
        },
        "manifest_digest",
    )

    result = select_validation(
        incomplete_manifest,
        ["src/api.py"],
        {
            "rules": [
                {
                    "id": "source",
                    "paths": ["src/**"],
                    "validation_level": "affected",
                    "tasks": ["test:unit"],
                }
            ]
        },
        {"tasks": [_task(supports_scope="affected")]},
    )

    assert result["status"] == "blocked"
    assert {
        "EVIDENCE_BINDING_MISMATCH",
        "HANDOFF_REQUIRED",
    } <= set(result["blocker_codes"])


@pytest.mark.parametrize("level", ["integration", "full"])
def test_insufficient_task_scope_blocks_selection(level: str) -> None:
    task = _task(supports_scope="contract")
    grant = create_work_grant(
        grant_id="grant:scope",
        goal="test insufficient scope",
        write_scope=["src/**"],
        merge_target="main",
        delivery_target=None,
        risk_level="low",
    )
    manifest = create_change_manifest(
        grant,
        manifest_id="manifest:scope",
        base_commit="base",
        changed_paths=["src/a.py"],
    )
    facts = {"merge_policy_requires_full": True} if level == "full" else {}
    impact_level = "affected" if level == "full" else "integration"
    result = select_validation(
        manifest,
        ["src/a.py"],
        {
            "rules": [
                {
                    "id": "source",
                    "paths": ["src/**"],
                    "validation_level": impact_level,
                    "tasks": [task["id"]],
                }
            ]
        },
        {"tasks": [task]},
        facts,
    )

    assert result["status"] == "blocked"
    assert "IMPACT_UNRESOLVED" in result["blocker_codes"]


def test_full_selection_never_adds_delivery_tasks() -> None:
    tasks = [
        _task(task_id="ci:full", category="ci", supports_scope="full"),
        *[
            _task(
                task_id=f"{category}:target",
                category=category,
                automation_level="critical",
                auto_allowed=False,
                supports_scope="publish",
            )
            for category in DELIVERY
        ],
    ]
    grant = create_work_grant(
        grant_id="grant:full",
        goal="select full",
        write_scope=["src/**"],
        merge_target="main",
        delivery_target=None,
        risk_level="low",
    )
    manifest = create_change_manifest(
        grant,
        manifest_id="manifest:full",
        base_commit="base",
        changed_paths=["src/a.py"],
    )
    result = select_validation(
        manifest,
        ["src/a.py"],
        {
            "rules": [
                {
                    "id": "source",
                    "paths": ["src/**"],
                    "validation_level": "affected",
                    "tasks": [],
                }
            ]
        },
        {"tasks": tasks},
        {"merge_policy_requires_full": True},
    )

    selected = {item["task_id"] for item in result["selected_tasks"]}
    assert selected == {"ci:full"}
    assert not any(task_id.split(":", 1)[0] in DELIVERY for task_id in selected)


def test_local_routine_task_returns_valid_bound_evidence(tmp_path: Path) -> None:
    task = _task()
    chain = _chain(task)
    evidence = run_local_task(
        task,
        [sys.executable, "-c", "print('ok')"],
        tmp_path,
        "contract",
        **chain,
    )

    assert set(evidence) == EVIDENCE_FIELDS
    assert evidence["status"] == "passed"
    assert evidence["backend_calls"] == 1
    assert validate_runtime_artifact(evidence, SCHEMAS) == []


def test_local_runner_rejects_command_that_differs_from_registered_task(
    tmp_path: Path,
) -> None:
    task = _task()
    chain = _chain(task)

    evidence = run_local_task(
        task,
        [sys.executable, "-c", "raise SystemExit(99)"],
        tmp_path,
        "contract",
        **chain,
    )

    assert evidence["status"] == "blocked"
    assert evidence["backend_calls"] == 0
    assert {"TASK_BYPASS_ATTEMPT", "HANDOFF_REQUIRED"} <= set(
        evidence["blocker_codes"]
    )


def test_local_runner_rejects_schema_incomplete_chain_before_dispatch(
    tmp_path: Path,
) -> None:
    sentinel = tmp_path / "dispatched.txt"
    command = [
        sys.executable,
        "-c",
        (
            "from pathlib import Path; "
            f"Path({sentinel.as_posix()!r}).write_text('called')"
        ),
    ]
    task = _task(command=command)
    chain = _chain(task)
    selection = dict(chain["selection"])
    selection.pop("reasons")
    chain["selection"] = attach_digest(selection, "selection_digest")
    request = dict(chain["request"])
    request["selection_digest"] = chain["selection"]["selection_digest"]
    chain["request"] = attach_digest(request, "request_digest")

    evidence = run_local_task(
        task,
        command,
        tmp_path,
        "contract",
        **chain,
    )

    assert evidence["status"] == "blocked"
    assert evidence["backend_calls"] == 0
    assert not sentinel.exists()
    assert {
        "EVIDENCE_BINDING_MISMATCH",
        "HANDOFF_REQUIRED",
    } <= set(evidence["blocker_codes"])


@pytest.mark.parametrize("artifact_name", ["manifest", "selection"])
def test_cross_chain_artifact_prevents_local_dispatch(
    tmp_path: Path, artifact_name: str
) -> None:
    task = _task()
    chain = _chain(task)
    artifact = dict(chain[artifact_name])
    digest_field = (
        "manifest_digest"
        if artifact_name == "manifest"
        else "selection_digest"
    )
    artifact[
        "base_commit" if artifact_name == "manifest" else "selection_id"
    ] = "different"
    chain[artifact_name] = attach_digest(artifact, digest_field)

    evidence = run_local_task(
        task,
        task["command"],
        tmp_path,
        "contract",
        **chain,
    )

    assert evidence["status"] == "blocked"
    assert evidence["backend_calls"] == 0
    assert "EVIDENCE_BINDING_MISMATCH" in evidence["blocker_codes"]


@pytest.mark.parametrize("category", sorted(DELIVERY))
def test_local_backend_refuses_critical_delivery(
    tmp_path: Path, category: str
) -> None:
    task = _task(
        task_id=f"{category}:target",
        category=category,
        automation_level="critical",
        auto_allowed=False,
        supports_scope="publish",
    )
    artifact = canonical_digest({"artifact": "wheel"}) if category == "publish" else None
    chain = _chain(
        task,
        level="publish",
        target="production",
        environment="production",
        artifact=artifact,
    )
    confirmation = create_confirmation(chain["request"], "2026-07-24T00:00:00Z")
    evidence = run_local_task(
        task,
        [sys.executable, "-c", "raise SystemExit(99)"],
        tmp_path,
        "publish",
        confirmation=confirmation,
        **chain,
    )

    assert evidence["status"] == "blocked"
    assert evidence["backend_calls"] == 0
    assert "BACKEND_UNAVAILABLE" in evidence["blocker_codes"]


def _git_repository(tmp_path: Path) -> tuple[Path, str]:
    repository = tmp_path / "repository"
    repository.mkdir()
    subprocess.run(["git", "init"], cwd=repository, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repository,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Harness Test"],
        cwd=repository,
        check=True,
    )
    (repository / "README.md").write_text("fixture\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repository, check=True)
    subprocess.run(
        ["git", "commit", "-m", "fixture"],
        cwd=repository,
        check=True,
        capture_output=True,
    )
    commit_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return repository, commit_sha


def test_git_remote_push_requires_matching_confirmation(tmp_path: Path) -> None:
    repository, commit_sha = _git_repository(tmp_path)
    task = _task(
        task_id="push:branch",
        category="push",
        backend="git-remote",
        automation_level="critical",
        auto_allowed=False,
        supports_scope="publish",
    )
    chain = _chain(
        task,
        level="publish",
        target="refs/heads/codex/test",
        commit_sha=commit_sha,
    )
    calls: list[list[str]] = []

    def executor(command: list[str], **kwargs: object) -> SimpleNamespace:
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="ok\n", stderr="")

    evidence = run_git_remote_push_task(
        task,
        {
            "type": "git-remote",
            "remote": "origin",
            "execution": {
                "shell": False,
                "force": False,
                "operation": "push-ref",
            },
        },
        repository,
        "publish",
        executor=executor,
        **chain,
    )

    assert evidence["status"] == "blocked"
    assert evidence["backend_calls"] == 0
    assert calls == []
    assert "HANDOFF_REQUIRED" in evidence["blocker_codes"]


def test_git_remote_push_uses_one_exact_non_force_refspec(tmp_path: Path) -> None:
    repository, commit_sha = _git_repository(tmp_path)
    task = _task(
        task_id="push:branch",
        category="push",
        backend="git-remote",
        automation_level="critical",
        auto_allowed=False,
        supports_scope="publish",
    )
    chain = _chain(
        task,
        level="publish",
        target="refs/heads/codex/test",
        commit_sha=commit_sha,
    )
    confirmation = create_confirmation_artifact(
        chain["request"], confirmed_at="2026-07-27T00:00:00Z"
    )
    calls: list[list[str]] = []

    def executor(command: list[str], **kwargs: object) -> SimpleNamespace:
        assert kwargs["shell"] is False
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="ok\n", stderr="")

    evidence = run_git_remote_push_task(
        task,
        {
            "type": "git-remote",
            "remote": "origin",
            "execution": {
                "shell": False,
                "force": False,
                "operation": "push-ref",
            },
        },
        repository,
        "publish",
        confirmation=confirmation,
        executor=executor,
        **chain,
    )

    assert evidence["status"] == "passed"
    assert evidence["backend_calls"] == 1
    assert evidence["formal_authority"] is True
    assert evidence["platform"]["platform"] == "git-remote"
    assert evidence["platform"]["protected_ref"] == "refs/heads/codex/test"
    assert calls == [
        [
            "git",
            "push",
            "--porcelain",
            "--set-upstream",
            "origin",
            f"{commit_sha}:refs/heads/codex/test",
        ]
    ]
    assert "--force" not in calls[0]
    assert validate_runtime_artifact(evidence, SCHEMAS) == []


def test_fake_adapter_is_not_called_without_matching_confirmation(
    tmp_path: Path,
) -> None:
    task = _task(
        task_id="ci:full",
        category="ci",
        backend="github-actions",
        automation_level="expensive",
        auto_allowed=False,
        supports_scope="full",
    )
    chain = _chain(task, level="full")
    adapter = FakeGitHubAdapter(_complete_run(category="ci"))

    evidence = run_github_actions_task(
        task, adapter, tmp_path, "full", **chain
    )

    assert evidence["status"] == "blocked"
    assert evidence["backend_calls"] == 0
    assert adapter.calls == {"prepare": 0, "dispatch": 0, "poll": 0, "normalize": 0}


def test_fake_adapter_protocol_runs_once_and_passes_only_after_poll(
    tmp_path: Path,
) -> None:
    task = _task(
        task_id="ci:full",
        category="ci",
        backend="github-actions",
        automation_level="expensive",
        auto_allowed=False,
        supports_scope="full",
    )
    chain = _chain(task, level="full")
    confirmation = create_confirmation(chain["request"], "2026-07-24T00:00:00Z")
    adapter = FakeGitHubAdapter(_complete_run(category="ci"))

    evidence = run_github_actions_task(
        task,
        adapter,
        tmp_path,
        "full",
        confirmation=confirmation,
        **chain,
    )

    assert evidence["status"] == "passed"
    assert evidence["backend_calls"] == 1
    assert adapter.calls == {"prepare": 1, "dispatch": 1, "poll": 1, "normalize": 1}
    assert validate_runtime_artifact(evidence, SCHEMAS) == []


def test_publish_poll_without_artifact_digest_stays_blocked(
    tmp_path: Path,
) -> None:
    task = _task(
        task_id="publish:package",
        category="publish",
        backend="github-actions",
        automation_level="critical",
        auto_allowed=False,
        supports_scope="publish",
    )
    artifact = canonical_digest({"artifact": "wheel"})
    chain = _chain(
        task,
        level="publish",
        target="pypi",
        environment="production",
        artifact=artifact,
    )
    confirmation = create_confirmation(chain["request"], "2026-07-24T00:00:00Z")
    run = _complete_run(category="publish")
    run["artifact_digest"] = None
    adapter = FakeGitHubAdapter(run)

    evidence = run_github_actions_task(
        task,
        adapter,
        tmp_path,
        "publish",
        confirmation=confirmation,
        **chain,
    )

    assert evidence["status"] == "blocked"
    assert evidence["formal_authority"] is False
    assert "EVIDENCE_INCOMPLETE" in evidence["blocker_codes"]


def test_incomplete_publish_request_never_calls_adapter(tmp_path: Path) -> None:
    task = _task(
        task_id="publish:package",
        category="publish",
        backend="github-actions",
        automation_level="critical",
        auto_allowed=False,
        supports_scope="publish",
    )
    chain = _chain(
        task,
        level="publish",
        target="pypi",
        environment="production",
        artifact=canonical_digest({"artifact": "wheel"}),
    )
    chain["request"]["artifact_digest"] = None
    chain["request"] = attach_digest(chain["request"], "request_digest")
    confirmation = create_confirmation(
        chain["request"], "2026-07-24T00:00:00Z"
    )
    adapter = FakeGitHubAdapter(_complete_run(category="publish"))

    evidence = run_github_actions_task(
        task,
        adapter,
        tmp_path,
        "publish",
        confirmation=confirmation,
        **chain,
    )

    assert evidence["status"] == "blocked"
    assert evidence["backend_calls"] == 0
    assert "EVIDENCE_INCOMPLETE" in evidence["blocker_codes"]
    assert adapter.calls == {"prepare": 0, "dispatch": 0, "poll": 0, "normalize": 0}


def test_different_platform_commit_is_binding_mismatch(tmp_path: Path) -> None:
    task = _task(
        task_id="merge:main",
        category="merge",
        backend="github-actions",
        automation_level="critical",
        auto_allowed=False,
        supports_scope="publish",
    )
    chain = _chain(task, level="publish", target="main")
    confirmation = create_confirmation(chain["request"], "2026-07-24T00:00:00Z")
    run = _complete_run(category="merge")
    run["commit_sha"] = "different"
    adapter = FakeGitHubAdapter(run)

    evidence = run_github_actions_task(
        task,
        adapter,
        tmp_path,
        "publish",
        confirmation=confirmation,
        **chain,
    )

    assert evidence["status"] == "blocked"
    assert "EVIDENCE_BINDING_MISMATCH" in evidence["blocker_codes"]


def test_platform_workflow_source_mismatch_is_rejected(tmp_path: Path) -> None:
    task = _task(
        task_id="ci:full",
        category="ci",
        backend="github-actions",
        automation_level="expensive",
        auto_allowed=False,
        supports_scope="full",
    )
    chain = _chain(task, level="full")
    confirmation = create_confirmation(
        chain["request"], "2026-07-24T00:00:00Z"
    )
    run = _complete_run(category="ci")
    run["workflow"] = ".github/workflows/different.yml"
    adapter = FakeGitHubAdapter(run)

    evidence = run_github_actions_task(
        task,
        adapter,
        tmp_path,
        "full",
        confirmation=confirmation,
        **chain,
    )

    assert evidence["status"] == "blocked"
    assert evidence["backend_calls"] == 1
    assert "EVIDENCE_BINDING_MISMATCH" in evidence["blocker_codes"]


def test_publish_platform_environment_mismatch_is_rejected(
    tmp_path: Path,
) -> None:
    task = _task(
        task_id="publish:package",
        category="publish",
        backend="github-actions",
        automation_level="critical",
        auto_allowed=False,
        supports_scope="publish",
    )
    artifact = canonical_digest({"artifact": "wheel"})
    chain = _chain(
        task,
        level="publish",
        target="pypi",
        environment="production",
        artifact=artifact,
    )
    confirmation = create_confirmation(
        chain["request"], "2026-07-24T00:00:00Z"
    )
    run = _complete_run(category="publish", artifact=artifact)
    run["protected_environment"] = "staging"
    adapter = FakeGitHubAdapter(run)

    evidence = run_github_actions_task(
        task,
        adapter,
        tmp_path,
        "publish",
        confirmation=confirmation,
        **chain,
    )

    assert evidence["status"] == "blocked"
    assert "EVIDENCE_BINDING_MISMATCH" in evidence["blocker_codes"]


def test_pipeline_readiness_and_finalize_are_separate(tmp_path: Path) -> None:
    validation_task = _task()
    chain = _chain(validation_task)
    validation_evidence = run_local_task(
        validation_task,
        [sys.executable, "-c", "print('ok')"],
        tmp_path,
        "contract",
        **chain,
    )
    merge_task = _task(
        task_id="merge:main",
        category="merge",
        backend="github-actions",
        automation_level="critical",
        auto_allowed=False,
        supports_scope="publish",
    )
    merge_request = create_task_request_artifact(
        merge_task,
        chain["grant"],
        chain["manifest"],
        chain["selection"],
        request_id="request:merge",
        target="main",
        commit_sha="commit123",
        pull_request_number=42,
        merge_method="squash",
    )
    confirmation = create_confirmation_artifact(
        merge_request, confirmed_at="2026-07-24T00:00:00Z"
    )
    pipeline = {
        "kind": "merge",
        "requires_independent_confirmation": True,
        "stages": [
            {
                "id": "validate",
                "tasks": ["test:unit"],
                "requires_evidence": True,
            }
        ],
    }

    readiness = evaluate_pipeline_readiness(
        pipeline, [validation_evidence], merge_request, confirmation
    )
    without_platform = finalize_pipeline(
        pipeline,
        [validation_evidence],
        merge_request,
        confirmation,
        None,
    )
    platform = create_platform_evidence_artifact(
        merge_request,
        workflow=".github/workflows/merge.yml",
        run_id="456",
        commit_sha="commit123",
        confirmation_status="confirmed",
        approval_status="approved",
        required_checks="passed",
        protected_environment=None,
        artifact_digest=None,
        source_ref="github://actions/runs/456",
        protected_ref="main",
    )
    finalized = finalize_pipeline(
        pipeline,
        [validation_evidence],
        merge_request,
        confirmation,
        platform,
    )

    assert readiness["status"] == "ready-for-dispatch"
    assert readiness["backend_calls"] == 0
    assert without_platform["status"] == "blocked"
    assert finalized["status"] == "passed"


def test_pipeline_dispatch_has_its_own_state_and_one_dispatch_call() -> None:
    task = _task(
        task_id="publish:package",
        category="publish",
        backend="github-actions",
        automation_level="critical",
        auto_allowed=False,
        supports_scope="publish",
    )
    artifact = canonical_digest({"artifact": "wheel"})
    chain = _chain(
        task,
        level="publish",
        target="pypi",
        environment="production",
        artifact=artifact,
    )
    confirmation = create_confirmation(
        chain["request"], "2026-07-24T00:00:00Z"
    )
    pipeline = {
        "kind": "publish",
        "requires_independent_confirmation": True,
        "stages": [
            {
                "id": "publish",
                "tasks": ["publish:package"],
                "requires_evidence": False,
            }
        ],
    }
    readiness = evaluate_pipeline_readiness(
        pipeline, [], chain["request"], confirmation
    )
    adapter = FakeGitHubAdapter(
        _complete_run(category="publish", artifact=artifact)
    )

    result = dispatch_pipeline(readiness, task, chain["request"], adapter)

    assert result["status"] == "dispatched"
    assert result["backend_calls"] == 1
    assert adapter.calls == {"prepare": 1, "dispatch": 1, "poll": 0, "normalize": 0}


def test_publish_readiness_requires_artifact_digest() -> None:
    task = _task(
        task_id="publish:package",
        category="publish",
        backend="github-actions",
        automation_level="critical",
        auto_allowed=False,
        supports_scope="publish",
    )
    chain = _chain(
        task,
        level="publish",
        target="pypi",
        environment="production",
        artifact=canonical_digest({"artifact": "wheel"}),
    )
    chain["request"]["artifact_digest"] = None
    chain["request"] = attach_digest(chain["request"], "request_digest")
    confirmation = create_confirmation(chain["request"], "2026-07-24T00:00:00Z")
    pipeline = {
        "kind": "publish",
        "requires_independent_confirmation": True,
        "stages": [
            {"id": "publish", "tasks": ["publish:package"], "requires_evidence": False}
        ],
    }

    result = evaluate_pipeline_readiness(
        pipeline, [], chain["request"], confirmation
    )

    assert result["status"] == "blocked"
    assert result["blocker_codes"] == ["EVIDENCE_INCOMPLETE"]


def test_pipeline_rejects_schema_incomplete_request_before_dispatch() -> None:
    task = _task(
        task_id="merge:default",
        category="merge",
        backend="github-actions",
        automation_level="critical",
        auto_allowed=False,
        supports_scope="publish",
    )
    chain = _chain(task, level="publish", target="refs/heads/main")
    request = dict(chain["request"])
    request.pop("policy_version")
    request = attach_digest(request, "request_digest")
    confirmation = {
        "artifact_type": "confirmation",
        "schema_version": "0.3.0",
        "request_digest": request["request_digest"],
        "confirmation_status": "confirmed",
        "confirmed_at": "2026-07-24T00:00:00Z",
    }
    pipeline = {
        "kind": "merge",
        "requires_independent_confirmation": True,
        "stages": [
            {"id": "merge", "tasks": [], "requires_evidence": False}
        ],
    }

    result = evaluate_pipeline_readiness(
        pipeline, [], request, confirmation
    )

    assert result["status"] == "blocked"
    assert result["backend_calls"] == 0
    assert result["blocker_codes"] == [
        "EVIDENCE_BINDING_MISMATCH",
        "HANDOFF_REQUIRED",
    ]


def test_route_and_external_event_remain_non_authorizing() -> None:
    examples = {
        "Adopt this repository with existing CI": "adopt",
        "接管这个已有 CI 的项目": "adopt",
        "Bootstrap a new Python repository": "bootstrap",
        "初始化一个新的 Python 项目": "bootstrap",
        "Audit the current Harness configuration": "audit",
        "审查当前 Harness 配置": "audit",
        "Repair Harness configuration drift": "update",
        "修复 Harness 配置漂移": "update",
        "Register this tool in the Tool Registry": "registry",
        "把这个命令登记到工具注册表": "registry",
        "Validate the GitHub platform evidence": "platform",
        "检查 GitHub 平台门禁 Evidence": "platform",
        "Implement the approved order change": "work",
        "请在已批准范围内实现订单状态修改": "work",
        "Verify the affected Python module": "verify",
        "验证这次 Python 改动需要哪些测试": "verify",
        "Is the current evidence merge ready?": "merge",
        "现有 Evidence 是否已经可以合并？": "merge",
        "Prepare release 1.2.3 for publish": "publish",
        "为版本 1.2.3 准备发布计划": "publish",
    }
    external = create_external_request(
        {"type": "push", "ref": "refs/heads/main"}, "merge:default"
    )

    assert {text: route_intent(text) for text in examples} == examples
    assert external["status"] == "blocked"
    assert external["backend_calls"] == 0
