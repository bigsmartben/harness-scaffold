from __future__ import annotations

import re
import tomllib
from pathlib import Path


ROOT = Path(__file__).parents[2]
WORKFLOWS = (
    ROOT / ".github" / "workflows" / "ci.yml",
    ROOT / ".github" / "workflows" / "release.yml",
)

APPROVED_ACTIONS = {
    "actions/checkout": {
        "sha": "3d3c42e5aac5ba805825da76410c181273ba90b1",
        "version": "v7.0.1",
        "runtime": "node24",
    },
    "astral-sh/setup-uv": {
        "sha": "c771a70e6277c0a99b617c7a806ffedaca235ff9",
        "version": "v9.0.0",
        "runtime": "node24",
    },
}

ACTION_REFERENCE = re.compile(
    r"^\s*-\s+uses:\s+"
    r"(?P<action>[^@\s]+)@(?P<sha>[0-9a-f]{40})"
    r"\s+#\s+(?P<version>v[0-9.]+)\s*$",
    re.MULTILINE,
)

IGNORED_DIRECTORIES = {
    ".git",
    ".pytest_cache",
    ".tmp",
    ".venv",
    "__pycache__",
    "dist",
}
NODE_SOURCE_SUFFIXES = {".js", ".ts", ".mjs", ".cjs"}
NODE_MANIFESTS = {
    "package.json",
    "package-lock.json",
    "npm-shrinkwrap.json",
    "pnpm-lock.yaml",
    "yarn.lock",
}


def test_workflows_use_only_audited_node24_actions_by_full_sha() -> None:
    for workflow in WORKFLOWS:
        source = workflow.read_text(encoding="utf-8")
        uses_lines = [line for line in source.splitlines() if "uses:" in line]
        references = list(ACTION_REFERENCE.finditer(source))

        assert len(references) == len(uses_lines)
        assert {match["action"] for match in references} == set(APPROVED_ACTIONS)

        for match in references:
            approved = APPROVED_ACTIONS[match["action"]]
            assert match["sha"] == approved["sha"]
            assert match["version"] == approved["version"]
            assert approved["runtime"] == "node24"


def test_uv_is_the_only_python_bootstrap_path() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert project["tool"]["uv"]["required-version"] == "==0.11.20"

    for workflow in WORKFLOWS:
        source = workflow.read_text(encoding="utf-8")

        assert "actions/setup-python" not in source
        assert 'python-version: "3.12"' in source
        assert "uv python install 3.12" in source


def test_repository_has_no_node_project_assets() -> None:
    node_assets: list[str] = []

    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in IGNORED_DIRECTORIES for part in path.parts):
            continue
        if path.suffix.lower() in NODE_SOURCE_SUFFIXES or path.name in NODE_MANIFESTS:
            node_assets.append(path.relative_to(ROOT).as_posix())

    assert node_assets == []
