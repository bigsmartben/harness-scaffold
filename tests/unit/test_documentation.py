from __future__ import annotations

import json
from pathlib import Path

import yaml


ROOT = Path(__file__).parents[2]
CANONICAL = ROOT / "src/harness_core/resources/repo_skill/harness"
PLUGIN = ROOT / "plugins/harness/skills/harness"


def test_plugin_skill_is_exact_generated_copy() -> None:
    expected = {
        path.relative_to(CANONICAL).as_posix(): path.read_bytes()
        for path in CANONICAL.rglob("*")
        if path.is_file()
    }
    actual = {
        path.relative_to(PLUGIN).as_posix(): path.read_bytes()
        for path in PLUGIN.rglob("*")
        if path.is_file()
    }
    assert actual == expected
    assert "agents/openai.yaml" in actual


def test_skill_metadata_supports_implicit_repository_use() -> None:
    metadata = yaml.safe_load(
        (CANONICAL / "agents/openai.yaml").read_text(encoding="utf-8")
    )
    assert metadata["policy"]["allow_implicit_invocation"] is True
    skill = (CANONICAL / "SKILL.md").read_text(encoding="utf-8")
    for intent in (
        "$harness",
        "git commit",
        "Issue",
        "Test",
        "Build",
        "Pull Request",
        "Release",
    ):
        assert intent in skill


def test_package_and_docs_have_one_2_0_runtime_story() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'packages = ["src/harness_core"]' in pyproject
    assert "skills/initialize-ai-coding-harness/scripts" not in pyproject
    legacy = ROOT / "skills/initialize-ai-coding-harness"
    assert not legacy.exists() or not any(
        path.is_file() for path in legacy.rglob("*")
    )
    manifest = json.loads(
        (
            ROOT / "plugins/harness/.codex-plugin/plugin.json"
        ).read_text(encoding="utf-8")
    )
    assert manifest["version"] == "2.0.0"
    user_docs = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            ROOT / "README.md",
            ROOT / "docs/quickstart.md",
            CANONICAL / "SKILL.md",
        )
    )
    assert "Work Grant" not in user_docs
    assert "G0–G7" not in user_docs
    assert "项目策略" in user_docs
    assert "本次决定" in user_docs
