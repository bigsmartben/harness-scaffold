from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).parents[2]

EXPECTED_SCENARIOS = [
    "M-G01",
    "M-G02",
    "M-G03",
    "M-G04",
    "C-G01",
    "C-G02",
    "C-G03",
    "C-G04",
    "C-G05",
]


def test_issue_40_manifest_maps_every_scenario_to_pytest_and_ci() -> None:
    manifest = yaml.safe_load(
        (ROOT / "evals" / "manifest.yaml").read_text(encoding="utf-8")
    )
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )
    traceability = (
        ROOT / "docs" / "acceptance-traceability.md"
    ).read_text(encoding="utf-8")

    assert manifest["schema_version"] == "3.0.1"
    assert manifest["source_issue"].endswith("/issues/40")
    assert manifest["ci_job"] == "contracts"
    assert "  contracts:" in workflow
    assert [
        item["scenario_id"] for item in manifest["scenarios"]
    ] == EXPECTED_SCENARIOS

    for item in manifest["scenarios"]:
        path_text, test_name = item["test"].split("::", maxsplit=1)
        test_source = (ROOT / path_text).read_text(encoding="utf-8")
        assert f"def {test_name}(" in test_source
        assert item["scenario_id"] in traceability


def test_v3_documents_and_skill_copies_have_one_current_contract() -> None:
    document_paths = [
        ROOT / "README.md",
        ROOT / "docs" / "specification.md",
        ROOT / "docs" / "quickstart.md",
        ROOT / "docs" / "repository-structure.md",
    ]
    documents = "\n".join(
        path.read_text(encoding="utf-8") for path in document_paths
    )
    obsolete_current_claims = [
        "当前契约版本为 `2.0.0`",
        "# Harness 2.0",
        "## 2.0 架构",
        "生成 5 个治理投影文件",
        "$repo-documentation-maker",
    ]

    assert all("3.0.1" in path.read_text(encoding="utf-8") for path in document_paths)
    assert all(
        term in documents
        for term in ("Audience", "Responsibility", "Governance Domain")
    )
    assert not any(term in documents for term in obsolete_current_claims)

    source_skill = (
        ROOT
        / "src"
        / "harness_core"
        / "resources"
        / "repo_skill"
        / "harness"
        / "SKILL.md"
    ).read_bytes()
    repository_skill = (
        ROOT / ".agents" / "skills" / "harness" / "SKILL.md"
    ).read_bytes()
    assert repository_skill == source_skill


def test_release_workflow_is_pinned_to_the_v3_contract() -> None:
    release = (
        ROOT / ".github" / "workflows" / "release.yml"
    ).read_text(encoding="utf-8")

    assert "tags:\n      - v3.0.1" in release
    assert 'test "$GITHUB_REF_NAME" = "v3.0.1"' in release
    assert "sdd-harness 3.0.1" in release
    assert "scripts/smoke_distribution.py" in release
    assert 'gh release create "$GITHUB_REF_NAME"' in release
    assert "--notes-file docs/release-notes-3.0.1.md" in release
