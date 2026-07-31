"""Read immutable Harness resources shipped in the wheel."""

from __future__ import annotations

from importlib import resources


_RESOURCE_PACKAGE = "harness_core"


def resource_root():
    return resources.files(_RESOURCE_PACKAGE).joinpath("resources")


def schema_root():
    return resource_root().joinpath("schemas")


def repo_skill_root():
    return resource_root().joinpath("repo_skill", "harness")


def repo_skill_bytes() -> bytes:
    return repo_skill_root().joinpath("SKILL.md").read_bytes()
