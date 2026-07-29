from __future__ import annotations

import re
from pathlib import Path

import yaml


ROOT = Path(__file__).parents[2]
SKILL = (
    ROOT
    / "src/harness_core/resources/repo_skill"
    / "repo-documentation-maker"
)
DOCUMENTS = (
    "README",
    "QUICKSTART",
    "DEVELOPMENT",
    "MAINTAINER",
    "HARNESS",
    "UC",
    "TECH-SELECTION",
    "ARCHITECTURE",
)


def _frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert match is not None, path
    value = yaml.safe_load(match.group(1))
    assert isinstance(value, dict)
    return value


def test_skill_has_eight_independent_contract_template_pairs() -> None:
    assert SKILL.is_dir()
    for name in DOCUMENTS:
        contract = SKILL / "contracts" / f"{name}.contract.md"
        template = SKILL / "templates" / f"{name}.template.md"
        assert contract.is_file()
        assert template.is_file()
        metadata = _frontmatter(contract)
        assert metadata["schema_version"] == 1
        assert metadata["document"] == f"{name}.md"
        assert metadata["required_sections"]
        assert metadata["forbidden_topics"]


def test_skill_paths_variables_and_ids_use_english_ascii() -> None:
    variable = re.compile(r"\{\{([^}]+)\}\}")
    identifier = re.compile(r"^[a-z0-9][a-z0-9-]*$")
    for path in SKILL.rglob("*"):
        relative = path.relative_to(SKILL).as_posix()
        assert relative.isascii(), relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for name in variable.findall(text):
            assert name.isascii()
            assert re.fullmatch(r"[a-z][a-z0-9_]*", name)
        if path.parent.name == "contracts":
            assert identifier.fullmatch(_frontmatter(path)["id"])


def test_skill_is_self_contained_and_has_no_external_project_association() -> None:
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in SKILL.rglob("*")
        if path.is_file()
    )
    assert "pre-sdd" not in combined.lower()
    assert "templates/workspace" not in combined
    assert "C:\\Users" not in combined
    assert "DOCUMENT_FACTS_MISSING" in combined
    assert "DOCUMENT_TEMPLATE_MISSING" in combined


def test_workflows_and_quality_checks_are_complete() -> None:
    for name in ("create", "update", "refactor"):
        assert (SKILL / "workflows" / f"{name}.md").is_file()
    quality = (
        SKILL / "checklists/document-quality.md"
    ).read_text(encoding="utf-8")
    for term in (
        "Contract",
        "Consistency",
        "Links and commands",
        "Quickstart",
    ):
        assert term in quality
