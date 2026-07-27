from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote

import yaml


ROOT = Path(__file__).parents[2]
SPEC = ROOT / "docs" / "specification.md"
USER_CASES = ROOT / "uc.md"
SKILL = ROOT / "skills" / "initialize-ai-coding-harness"
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$", re.MULTILINE)
RULE = re.compile(r"\b(?:WB|TR|DM|HF|EV)-\d{3}\b")
USER_CASE = re.compile(r"^## (UC-\d{3})[：:]", re.MULTILINE)


def _documentation_files() -> list[Path]:
    return [
        ROOT / "README.md",
        ROOT / "plan.md",
        USER_CASES,
        *sorted((ROOT / "docs").glob("*.md")),
        ROOT / "evals" / "README.md",
    ]


def _anchor(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("`", "").strip().lower()
    text = "".join(
        character
        for character in text
        if character.isalnum() or character in {" ", "-", "_"}
    )
    return re.sub(r"[\s-]+", "-", text).strip("-")


def _anchors(document: Path) -> set[str]:
    anchors: set[str] = set()
    counts: dict[str, int] = {}
    for heading in HEADING.findall(document.read_text("utf-8")):
        base = _anchor(heading)
        index = counts.get(base, 0)
        counts[base] = index + 1
        anchors.add(base if index == 0 else f"{base}-{index}")
    return anchors


def test_all_internal_markdown_links_resolve() -> None:
    failures: list[str] = []
    for document in _documentation_files():
        content = document.read_text("utf-8")
        for raw_target in MARKDOWN_LINK.findall(content):
            target = raw_target.strip()
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            path_part, _, fragment = target.partition("#")
            relative = unquote(path_part)
            resolved = (
                document
                if not relative
                else (document.parent / relative).resolve()
            )
            if not resolved.exists():
                failures.append(
                    f"{document.relative_to(ROOT).as_posix()} -> {target}"
                )
                continue
            if fragment and resolved.suffix.lower() == ".md":
                expected = unquote(fragment).lower()
                if expected not in _anchors(resolved):
                    failures.append(
                        f"{document.relative_to(ROOT).as_posix()} -> "
                        f"{target} (missing anchor)"
                    )
    assert failures == []


def test_every_normative_rule_is_covered_by_a_user_case() -> None:
    normative_rules = set(RULE.findall(SPEC.read_text("utf-8")))
    user_case_text = USER_CASES.read_text("utf-8")
    covered_rules = set(RULE.findall(user_case_text))

    assert normative_rules
    assert normative_rules <= covered_rules
    assert set(USER_CASE.findall(user_case_text)) == {
        f"UC-{index:03d}" for index in range(1, 13)
    }

    sections = USER_CASE.split(user_case_text)
    for index in range(1, len(sections), 2):
        case_id = sections[index]
        body = sections[index + 1]
        assert RULE.search(body), case_id


def test_public_status_projections_match_plan() -> None:
    plan = (ROOT / "plan.md").read_text("utf-8")
    readme = (ROOT / "README.md").read_text("utf-8")
    quickstart = (ROOT / "docs" / "quickstart.md").read_text("utf-8")

    assert "P0–P4 Available" in plan
    assert "P5 In Progress" in plan
    assert "P0–P4 Available" in readme
    assert "P5 In Progress" in readme
    assert "P4 平台契约 Available" in quickstart
    assert "P5 In Progress" in quickstart


def test_skill_metadata_matches_skill_identity() -> None:
    skill_text = (SKILL / "SKILL.md").read_text("utf-8")
    frontmatter = yaml.safe_load(skill_text.split("---", 2)[1])
    metadata = yaml.safe_load(
        (SKILL / "agents" / "openai.yaml").read_text("utf-8")
    )["interface"]

    assert frontmatter["name"] == "initialize-ai-coding-harness"
    assert metadata["display_name"] == "Initialize AI Coding Harness"
    assert "$initialize-ai-coding-harness" in metadata["default_prompt"]
    assert "AI Coding Harness" in frontmatter["description"]
    assert "Merge" in frontmatter["description"]
    assert "Publish" in frontmatter["description"]
    assert "CI/CD" in metadata["short_description"]


def test_skill_routes_load_every_reference_directly_and_only_one_layer() -> None:
    skill_text = (SKILL / "SKILL.md").read_text("utf-8")
    references = SKILL / "references"
    reference_names = {path.name for path in references.glob("*.md")}
    routed_names = {
        Path(target).name
        for target in MARKDOWN_LINK.findall(skill_text)
        if target.startswith("references/")
    }

    assert routed_names == reference_names
    for reference in references.glob("*.md"):
        nested_targets = {
            Path(target).name
            for target in MARKDOWN_LINK.findall(reference.read_text("utf-8"))
            if Path(target).name in reference_names
        }
        assert nested_targets == set(), reference.name


def test_skill_source_has_release_safe_structure() -> None:
    assert {item.name for item in SKILL.iterdir() if item.name != "__pycache__"} == {
        "SKILL.md",
        "agents",
        "assets",
        "references",
        "scripts",
    }

    forbidden_names = {
        "README.md",
        "quickstart.md",
        "CHANGELOG.md",
        "plan.md",
    }
    release_files = [
        path
        for path in SKILL.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
    ]
    assert release_files
    assert not any(path.name in forbidden_names for path in release_files)
    assert not any(
        part in {"evals", "tests", ".pytest_cache", ".git"}
        for path in release_files
        for part in path.parts
    )
