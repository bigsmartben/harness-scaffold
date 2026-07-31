from __future__ import annotations

import json
import tomllib
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

import harness_core


ROOT = Path(__file__).parents[2]


def test_traceability_manifest_points_to_real_tests_and_ci() -> None:
    manifest = yaml.safe_load(
        (ROOT / "evals/manifest.yaml").read_text(encoding="utf-8")
    )
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(
        encoding="utf-8"
    )
    traceability = (
        ROOT / "docs/acceptance-traceability.md"
    ).read_text(encoding="utf-8")

    assert manifest["schema_version"] == "4.0.0"
    assert manifest["source_issue"].endswith("/issues/49")
    assert manifest["ci_job"] == "contracts"
    assert "  contracts:" in workflow
    assert "uv run python -m pytest" in workflow
    assert "scripts/smoke_distribution.py" in workflow
    for scenario in manifest["scenarios"]:
        path_text, test_name = scenario["test"].split("::", maxsplit=1)
        source = (ROOT / path_text).read_text(encoding="utf-8")
        assert f"def {test_name}(" in source
        assert f"#{scenario['owner_issue']}" in traceability


def test_current_version_resources_and_entrypoints_are_aligned() -> None:
    project = tomllib.loads(
        (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    lock = (ROOT / "uv.lock").read_text(encoding="utf-8")
    release = (
        ROOT / ".github/workflows/release.yml"
    ).read_text(encoding="utf-8")

    assert project["project"]["version"] == "4.0.0"
    assert project["project"]["scripts"] == {
        "sdd-harness": "harness_core.cli:main",
        "harness": "harness_core.cli:main",
    }
    assert harness_core.__version__ == "4.0.0"
    assert 'name = "sdd-harness"\nversion = "4.0.0"' in lock
    assert "v4.0.0" in release
    assert "sdd_harness-4.0.0-py3-none-any.whl" in release
    assert "docs/release-notes-4.0.0.md" in release

    schemas = ROOT / "src/harness_core/resources/schemas"
    assert {path.name for path in schemas.glob("*.json")} == {
        "rule.schema.json",
        "operation.schema.json",
        "load.schema.json",
        "load-result.schema.json",
        "enforcement.schema.json",
        "state.schema.json",
        "projection.schema.json",
    }
    for path in schemas.glob("*.json"):
        Draft202012Validator.check_schema(
            json.loads(path.read_text(encoding="utf-8"))
        )


def test_no_superseded_guidance_only_runtime_contract_remains() -> None:
    source_root = ROOT / "src/harness_core"
    assert {path.name for path in source_root.glob("*.py")} == {
        "__init__.py",
        "artifacts.py",
        "bootstrap.py",
        "cli.py",
        "lifecycle.py",
        "load_core.py",
        "model.py",
        "package_resources.py",
        "scaffold.py",
        "skill_adapter.py",
    }
    current_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            ROOT / "README.md",
            ROOT / "docs/specification.md",
            ROOT / "docs/quickstart.md",
            ROOT / "docs/repository-structure.md",
            ROOT
            / "src/harness_core/resources/repo_skill/harness/SKILL.md",
        ]
    )
    assert "enforce`（契约约束）只表示严格校验固定模型" not in current_sources
    assert "init/project/validate/inspect" not in current_sources
    assert "authoritative" in current_sources
    assert "垂直业务执行者" in current_sources


def test_maintainer_root_has_no_consumer_artifacts() -> None:
    assert not (ROOT / ".harness/governance/state.json").exists()
    assert not (ROOT / ".agents/skills/harness/SKILL.md").exists()
