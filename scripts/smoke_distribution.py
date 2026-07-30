"""Clean-environment distribution and negative-surface smoke for Harness 3.0."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Sequence


VERSION = "3.0.0"
ROOT = Path(__file__).parents[1]
DIST = ROOT / "dist"

EXPECTED_MODULES = {
    "__init__.py",
    "artifacts.py",
    "cli.py",
    "contracts.py",
    "initializer.py",
    "model.py",
    "package_resources.py",
    "projection.py",
}

EXPECTED_INITIALIZED_FILES = {
    ".agents/skills/harness/SKILL.md",
    ".harness/governance/model.lock.json",
    ".harness/harness.yaml",
}

FORBIDDEN_PATH_FRAGMENTS = {
    ".codex-plugin",
    ".mcp.json",
    "/action_graph.py",
    "/branching.py",
    "/codex_adapter.py",
    "/commit.py",
    "/decisions.py",
    "/delivery.py",
    "/discovery.py",
    "/facts.py",
    "/hooks/",
    "/issues.py",
    "/mcp_server.py",
    "/plugins/",
    "/policy.py",
    "/push.py",
    "/repo-documentation-maker/",
    "/runner.py",
    "/runtime.schema.json",
    "/selection.py",
    "/snapshot.py",
    "/templates.py",
    "/workspace.py",
}

FORBIDDEN_COMMANDS = {
    "commit-plan",
    "decision",
    "delivery-plan",
    "hook",
    "issue-plan",
    "mcp",
    "policy-plan",
    "projection-plan",
    "push-plan",
    "run-action",
    "run-task",
}

FORBIDDEN_EXPORTS = {
    "apply_push_plan",
    "build_action_graph",
    "build_controlled_delivery_plan",
    "create_task_decision",
    "file_digest",
    "handle_hook",
    "runtime_artifact_is_valid",
    "select_validation",
    "validate_config",
    "validate_runtime_artifact",
    "verify_digest",
}

FORBIDDEN_ARTIFACTS = {
    ".harness/governance/action-graph.json",
    ".harness/governance/compatibility.json",
    ".harness/governance/projection.lock.json",
    ".harness/governance/rules.json",
    ".harness/governance/sources.lock.json",
}

FORBIDDEN_NODE_SUFFIXES = {".cjs", ".js", ".mjs", ".ts"}
FORBIDDEN_NODE_MANIFESTS = {
    "npm-shrinkwrap.json",
    "package-lock.json",
    "package.json",
    "pnpm-lock.yaml",
    "yarn.lock",
}

LEGAL_CONFIG = """\
schema_version: 3.0.0
rule_instances:
  specification:
    - rule_id: acceptance-before-code
      directive: Define observable acceptance conditions.
      scope:
        - docs/**
        - src/**
  implementation: []
  verification: []
  delivery: []
"""

ILLEGAL_CONFIG = """\
schema_version: 3.0.0
rule_instances:
  specification: []
  implementation:
    - rule_id: no-provider
      directive: Remain local guidance.
      scope:
        - src/**
      provider: github
  verification: []
  delivery: []
"""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(
    arguments: Sequence[str | os.PathLike[str]],
    *,
    cwd: Path | None = None,
    expected: int = 0,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONNOUSERSITE"] = "1"
    result = subprocess.run(
        [str(value) for value in arguments],
        cwd=cwd,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != expected:
        raise AssertionError(
            f"command returned {result.returncode}, expected {expected}: "
            f"{result.args!r}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def archive_names(path: Path) -> list[str]:
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            return archive.namelist()
    with tarfile.open(path, "r:gz") as archive:
        return archive.getnames()


def assert_no_forbidden_paths(names: list[str], label: str) -> None:
    normalized = [f"/{name.replace(chr(92), '/').lower()}" for name in names]
    matches = [
        (name, fragment)
        for name in normalized
        for fragment in FORBIDDEN_PATH_FRAGMENTS
        if fragment in name
    ]
    if matches:
        raise AssertionError(f"{label} contains forbidden paths: {matches}")
    node_assets = [
        name
        for name in normalized
        if Path(name).suffix in FORBIDDEN_NODE_SUFFIXES
        or Path(name).name in FORBIDDEN_NODE_MANIFESTS
    ]
    if node_assets:
        raise AssertionError(f"{label} contains Node.js assets: {node_assets}")


def inspect_wheel(wheel: Path) -> dict[str, Any]:
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        assert_no_forbidden_paths(names, "wheel")
        modules = {
            Path(name).name
            for name in names
            if name.startswith("harness_core/")
            and name.count("/") == 1
            and name.endswith(".py")
        }
        if modules != EXPECTED_MODULES:
            raise AssertionError(
                f"wheel modules differ: expected {EXPECTED_MODULES}, got {modules}"
            )
        metadata_name = next(
            name for name in names if name.endswith(".dist-info/METADATA")
        )
        metadata = archive.read(metadata_name).decode("utf-8")
        if f"Version: {VERSION}" not in metadata:
            raise AssertionError("wheel metadata version is not 3.0.0")
        packaged_skill = archive.read(
            "harness_core/resources/repo_skill/harness/SKILL.md"
        )
    source_skill = (
        ROOT
        / "src"
        / "harness_core"
        / "resources"
        / "repo_skill"
        / "harness"
        / "SKILL.md"
    ).read_bytes()
    if packaged_skill != source_skill:
        raise AssertionError("wheel Skill differs from the source resource")
    return {"entries": len(names), "sha256": sha256(wheel)}


def inspect_sdist(sdist: Path) -> dict[str, Any]:
    names = archive_names(sdist)
    assert_no_forbidden_paths(names, "sdist")
    if any("/evals/results/" in f"/{name.lower()}" for name in names):
        raise AssertionError("sdist contains ignored evaluation results")
    return {"entries": len(names), "sha256": sha256(sdist)}


def venv_python(venv: Path) -> Path:
    if os.name == "nt":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def cli(python: Path, *arguments: str, expected: int = 0) -> subprocess.CompletedProcess[str]:
    return run(
        [python, "-m", "harness_core.cli", *arguments],
        expected=expected,
    )


def installed_surface(python: Path) -> dict[str, Any]:
    probe = (
        "import json,harness_core;"
        "print(json.dumps({"
        "'version':harness_core.__version__,"
        "'exports':sorted(harness_core.__all__)"
        "},sort_keys=True))"
    )
    payload = json.loads(run([python, "-c", probe]).stdout)
    if payload["version"] != VERSION:
        raise AssertionError("installed package version is not 3.0.0")
    if FORBIDDEN_EXPORTS.intersection(payload["exports"]):
        raise AssertionError("installed package exposes legacy capability")
    return payload


def assert_initialized_surface(repository: Path) -> None:
    files = {
        path.relative_to(repository).as_posix()
        for path in repository.rglob("*")
        if path.is_file()
    }
    if files != EXPECTED_INITIALIZED_FILES:
        raise AssertionError(
            f"initialized files differ: expected {EXPECTED_INITIALIZED_FILES}, "
            f"got {files}"
        )
    if files.intersection(FORBIDDEN_ARTIFACTS):
        raise AssertionError("initialized repository contains old artifacts")
    if (repository / ".codex").exists() or (repository / "plugins").exists():
        raise AssertionError("initialized repository contains Plugin/Hook/MCP")


def clean_install_smoke(wheel: Path) -> dict[str, Any]:
    uv = shutil.which("uv")
    if uv is None:
        raise AssertionError("uv is required for the clean-install smoke")

    with tempfile.TemporaryDirectory(prefix="harness-wheel-smoke-") as temporary:
        root = Path(temporary)
        venv = root / "venv"
        repository = root / "repository"
        repository.mkdir()
        run([uv, "venv", "--python", "3.12", venv])
        python = venv_python(venv)
        run([uv, "pip", "install", "--python", python, wheel.resolve()])

        version = cli(python, "--version").stdout.strip()
        if version != f"sdd-harness {VERSION}":
            raise AssertionError(f"unexpected CLI version: {version}")

        help_text = cli(python, "--help").stdout
        if "{init,project,validate,inspect}" not in help_text:
            raise AssertionError("CLI does not expose the exact four commands")
        if any(command in help_text for command in FORBIDDEN_COMMANDS):
            raise AssertionError("CLI help exposes a legacy command")

        init_payload = json.loads(
            cli(python, "init", str(repository), "--json").stdout
        )
        if init_payload["status"] != "initialized":
            raise AssertionError(f"init failed: {init_payload}")
        assert_initialized_surface(repository)

        valid_payload = json.loads(
            cli(python, "validate", str(repository), "--json").stdout
        )
        inspect_payload = json.loads(
            cli(python, "inspect", str(repository), "--json").stdout
        )
        if valid_payload["status"] != "valid":
            raise AssertionError(f"initial validate failed: {valid_payload}")
        if inspect_payload["schema_version"] != VERSION:
            raise AssertionError("inspect did not report version 3.0.0")

        config = repository / ".harness" / "harness.yaml"
        lock = repository / ".harness" / "governance" / "model.lock.json"
        config.write_text(LEGAL_CONFIG, encoding="utf-8")
        project_payload = json.loads(
            cli(python, "project", str(repository), "--json").stdout
        )
        if project_payload["status"] != "projected":
            raise AssertionError(f"legal project failed: {project_payload}")
        valid_after_rule = json.loads(
            cli(python, "validate", str(repository), "--json").stdout
        )
        if valid_after_rule["status"] != "valid":
            raise AssertionError(f"rule validate failed: {valid_after_rule}")

        before = lock.read_bytes()
        config.write_text(ILLEGAL_CONFIG, encoding="utf-8")
        blocked_payload = json.loads(
            cli(
                python,
                "project",
                str(repository),
                "--json",
                expected=2,
            ).stdout
        )
        if blocked_payload["status"] != "blocked":
            raise AssertionError("illegal project was not blocked")
        diagnostic = blocked_payload["diagnostics"][0]
        if (
            diagnostic["code"] != "RULE_FIELD_FORBIDDEN"
            or diagnostic["path"]
            != "/rule_instances/implementation/0/provider"
            or diagnostic["rule_id"] != "no-provider"
        ):
            raise AssertionError(f"unexpected diagnostic: {diagnostic}")
        if lock.read_bytes() != before:
            raise AssertionError("illegal projection changed the model lock")

        surface = installed_surface(python)
        return {
            "cli_version": version,
            "exports": len(surface["exports"]),
            "initialized_files": sorted(EXPECTED_INITIALIZED_FILES),
            "invalid_projection_exit_code": 2,
            "lock_unchanged_after_invalid_input": True,
        }


def locate_artifact(explicit: Path | None, pattern: str) -> Path:
    if explicit is not None:
        path = explicit.resolve()
        if not path.is_file():
            raise AssertionError(f"artifact does not exist: {path}")
        return path
    matches = sorted(DIST.glob(pattern))
    if len(matches) != 1:
        raise AssertionError(
            f"expected exactly one artifact matching {pattern}, got {matches}"
        )
    return matches[0].resolve()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wheel", type=Path)
    parser.add_argument("--sdist", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    wheel = locate_artifact(arguments.wheel, f"sdd_harness-{VERSION}-*.whl")
    sdist = locate_artifact(arguments.sdist, f"sdd_harness-{VERSION}.tar.gz")
    result = {
        "status": "passed",
        "version": VERSION,
        "wheel": inspect_wheel(wheel),
        "sdist": inspect_sdist(sdist),
        "clean_install": clean_install_smoke(wheel),
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
