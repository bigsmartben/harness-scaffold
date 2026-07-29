"""Read immutable resources shipped inside the Harness wheel."""

from __future__ import annotations

from importlib import resources
from typing import Iterator


_RESOURCE_PACKAGE = "harness_core"


def resource_root():
    return resources.files(_RESOURCE_PACKAGE).joinpath("resources")


def schema_root():
    return resource_root().joinpath("schemas")


def repo_skill_root():
    return resource_root().joinpath("repo_skill", "harness")


def repo_documentation_skill_root():
    return resource_root().joinpath(
        "repo_skill", "repo-documentation-maker"
    )


def iter_resource_files(root) -> Iterator[tuple[str, bytes]]:
    """Yield sorted relative file names and exact bytes."""

    entries: list[tuple[str, bytes]] = []

    def visit(node, prefix: str = "") -> None:
        for child in node.iterdir():
            relative = f"{prefix}/{child.name}".lstrip("/")
            if child.is_dir():
                visit(child, relative)
            else:
                entries.append((relative.replace("\\", "/"), child.read_bytes()))

    visit(root)
    yield from sorted(entries, key=lambda item: item[0])
