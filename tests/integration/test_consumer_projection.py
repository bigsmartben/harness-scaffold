from __future__ import annotations

import json
from pathlib import Path

from harness_core.codex_adapter import load_projection_bundle, runtime_state
from harness_core.initializer import (
    apply_initialization_plan,
    apply_projection_plan,
    build_initialization_plan,
    build_projection_plan,
)


def _publish_entrypoint(repository: Path) -> dict:
    plan = build_initialization_plan(repository)
    assert plan["blocker_codes"] == []
    result = apply_initialization_plan(
        repository,
        plan,
        approved_plan_digest=plan["plan_digest"],
    )
    assert result["status"] == "applied"
    return plan


def _publish_projection(repository: Path) -> dict:
    plan = build_projection_plan(repository)
    assert plan["blocker_codes"] == []
    result = apply_projection_plan(
        repository,
        plan,
        approved_plan_digest=plan["plan_digest"],
    )
    assert result["status"] == "applied"
    return plan


def _write_gray_node(repository: Path) -> None:
    (repository / "AGENTS.md").write_text(
        "# User instructions\n\nKeep this line.\n",
        encoding="utf-8",
    )
    (repository / "package.json").write_text(
        json.dumps(
            {
                "name": "orders-api",
                "scripts": {
                    "test": "node --test tests/parser.test.ts",
                    "build": "node --check src/parser.ts",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    workflow = repository / ".github" / "workflows"
    workflow.mkdir(parents=True)
    (workflow / "ci.yml").write_text(
        "name: CI\n"
        "on: [push]\n"
        "jobs:\n"
        "  test:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - run: npm test\n",
        encoding="utf-8",
    )
    (repository / "src").mkdir()
    (repository / "tests").mkdir()
    (repository / "src" / "parser.ts").write_text(
        "export const parse = (query = '') => query.trim();\n",
        encoding="utf-8",
    )
    (repository / "tests" / "parser.test.ts").write_text(
        "import assert from 'node:assert/strict';\n"
        "import test from 'node:test';\n"
        "import { parse } from '../src/parser.ts';\n"
        "test('empty query', () => assert.equal(parse(''), ''));\n",
        encoding="utf-8",
    )


def test_gray_projection_reuses_local_and_controlled_sources(
    private_repository: Path,
) -> None:
    _write_gray_node(private_repository)
    protected = {
        path: (private_repository / path).read_bytes()
        for path in (
            "package.json",
            "src/parser.ts",
            "tests/parser.test.ts",
            ".github/workflows/ci.yml",
        )
    }
    entrypoint = _publish_entrypoint(private_repository)
    assert entrypoint["repository_model"] == "Gray"
    assert entrypoint["mode"] == "adopt"
    assert "Keep this line." in (
        private_repository / "AGENTS.md"
    ).read_text(encoding="utf-8")

    projection = _publish_projection(private_repository)
    assert projection["repository_model"] == "Gray"
    assert projection["classification_mode"] == "Adopt"
    assert all(
        (private_repository / path).read_bytes() == expected
        for path, expected in protected.items()
    )
    bundle = load_projection_bundle(private_repository)
    assert bundle is not None
    actions = {
        action["action_id"]: action
        for action in bundle["action_graph"]["actions"]
    }
    assert actions["test:node-root:test"]["binding"] == {
        "adapter": "local",
        "argv": ["npm", "run", "test"],
        "cwd": ".",
    }
    assert actions["build:node-root:build"]["boundary"] == "local"
    assert actions["ci:workflow:test:test"]["boundary"] == "controlled"
    assert actions["ci:workflow:test:test"]["source_refs"] == [
        ".github/workflows/ci.yml#jobs.test"
    ]


def test_monorepo_preserves_distinct_working_directories(
    private_repository: Path,
) -> None:
    (private_repository / "package.json").write_text(
        '{"name":"commerce","workspaces":["apps/*"]}\n',
        encoding="utf-8",
    )
    web = private_repository / "apps" / "web"
    web.mkdir(parents=True)
    (web / "package.json").write_text(
        '{"name":"web","scripts":{"test":"node --test"}}\n',
        encoding="utf-8",
    )
    api = private_repository / "services" / "api"
    (api / "tests").mkdir(parents=True)
    (api / "pyproject.toml").write_text(
        "[project]\n"
        "name='api'\n"
        "version='0.1.0'\n"
        "dependencies=['pytest>=8']\n",
        encoding="utf-8",
    )
    (private_repository / "pyproject.toml").write_text(
        "[project]\nname='commerce-root'\nversion='0.1.0'\n"
        "[tool.uv.workspace]\nmembers=['services/*']\n",
        encoding="utf-8",
    )
    workflow = private_repository / ".github" / "workflows"
    workflow.mkdir(parents=True)
    (workflow / "ci.yml").write_text(
        "name: CI\non: [push]\njobs:\n"
        "  verify:\n    runs-on: ubuntu-latest\n"
        "    steps:\n      - run: npm test\n",
        encoding="utf-8",
    )

    _publish_entrypoint(private_repository)
    _publish_projection(private_repository)
    bundle = load_projection_bundle(private_repository)
    assert bundle is not None
    local_tests = {
        action["binding"]["cwd"]: action
        for action in bundle["action_graph"]["actions"]
        if action["semantics"] == "test"
        and action["binding"].get("adapter") == "local"
    }
    assert {"apps/web", "services/api"} <= set(local_tests)
    assert (
        local_tests["apps/web"]["source_refs"]
        == ["apps/web/package.json#scripts.test"]
    )
    assert (
        local_tests["services/api"]["source_refs"]
        == ["services/api/pyproject.toml#pytest-dependency"]
    )


def test_conflicting_ci_bindings_fail_closed_with_both_sources(
    private_repository: Path,
) -> None:
    _write_gray_node(private_repository)
    (private_repository / ".github" / "workflows" / "verify.yml").write_text(
        "name: Verify\n"
        "on: [push]\n"
        "jobs:\n"
        "  test:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - run: npm test\n",
        encoding="utf-8",
    )
    _publish_entrypoint(private_repository)
    plan = build_projection_plan(private_repository)
    assert plan["blocker_codes"] == ["TOOL_BINDING_AMBIGUOUS"]
    result = apply_projection_plan(
        private_repository,
        plan,
        approved_plan_digest=plan["plan_digest"],
    )
    assert result["status"] == "blocked"
    assert not (private_repository / ".harness/governance").exists()
    graph = json.loads(
        next(
            item["content"]
            for item in plan["actions"]
            if item["path"].endswith("action-graph.json")
        )
    )
    assert graph["blockers"] == [
        {
            "action_id": "ci:workflow:test:test",
            "code": "TOOL_BINDING_AMBIGUOUS",
            "source_refs": [
                ".github/workflows/ci.yml#jobs.test",
                ".github/workflows/verify.yml#jobs.test",
            ],
        }
    ]


def test_status_reports_current_artifacts_and_exact_stale_source(
    private_repository: Path,
) -> None:
    _write_gray_node(private_repository)
    _publish_entrypoint(private_repository)
    _publish_projection(private_repository)
    current = runtime_state(private_repository)
    assert current["status"] == "active"
    assert current["repository_model"] == "Gray / Adopt"
    assert current["coverage"] == {"total": 16, "missing": []}
    assert {
        item["status"] for item in current["projection_artifacts"]
    } == {"current"}

    package = json.loads(
        (private_repository / "package.json").read_text(encoding="utf-8")
    )
    package["scripts"]["test"] = (
        "node --test --experimental-test-coverage tests/parser.test.ts"
    )
    (private_repository / "package.json").write_text(
        json.dumps(package) + "\n",
        encoding="utf-8",
    )
    stale = runtime_state(private_repository)
    assert stale["status"] == "blocked"
    assert "GOVERNANCE_PROJECTION_STALE" in stale["blocker_codes"]
    assert stale["stale_sources"] == ["package.json"]
