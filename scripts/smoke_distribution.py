#!/usr/bin/env python3
"""Build, install, and exercise the public Harness 2.0 distribution."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).parents[1]
CANONICAL_SKILL = (
    ROOT / "src" / "harness_core" / "resources" / "repo_skill" / "harness"
)
CANONICAL_DOCUMENTATION_SKILL = (
    ROOT
    / "src"
    / "harness_core"
    / "resources"
    / "repo_skill"
    / "repo-documentation-maker"
)
VERSION = "2.0.0"


def _run(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    input_text: str | None = None,
    expected: tuple[int, ...] = (0,),
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        input=input_text,
    )
    if result.returncode not in expected:
        raise RuntimeError(
            f"command failed ({result.returncode}): {command}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if ".git" in path.parts:
            continue
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return f"sha256:{digest.hexdigest()}"


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build and smoke-test the public sdd-harness wheel"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="persist the verified wheel and SHA256SUMS in this directory",
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="write the machine-readable result to this JSON file",
    )
    parser.add_argument(
        "--allow-network",
        action="store_true",
        help="allow dependency downloads for the isolated tool install",
    )
    return parser.parse_args()


def _git(repository: Path, env: dict[str, str], *arguments: str) -> None:
    _run(["git", *arguments], cwd=repository, env=env)


def _fixture(path: Path, env: dict[str, str]) -> None:
    path.mkdir()
    (path / "pyproject.toml").write_text(
        "[project]\n"
        'name = "distribution-smoke-fixture"\n'
        'version = "0.1.0"\n',
        encoding="utf-8",
    )
    _git(path, env, "init")
    _git(path, env, "checkout", "-b", "codex/smoke")
    _git(path, env, "config", "user.name", "Harness Smoke")
    _git(path, env, "config", "user.email", "harness@example.invalid")
    _git(path, env, "add", "pyproject.toml")
    _git(path, env, "commit", "-m", "fixture")


def _assert_skill_exact(repository: Path) -> None:
    expected = {
        path.relative_to(CANONICAL_SKILL).as_posix(): path.read_bytes()
        for path in CANONICAL_SKILL.rglob("*")
        if path.is_file()
    }
    published = repository / ".agents" / "skills" / "harness"
    actual = {
        path.relative_to(published).as_posix(): path.read_bytes()
        for path in published.rglob("*")
        if path.is_file()
    }
    if actual != expected:
        raise RuntimeError("published repository Skill differs from wheel source")
    if "agents/openai.yaml" not in actual:
        raise RuntimeError("published Skill lacks agents/openai.yaml")

    expected_documentation = {
        path.relative_to(CANONICAL_DOCUMENTATION_SKILL).as_posix(): (
            path.read_bytes()
        )
        for path in CANONICAL_DOCUMENTATION_SKILL.rglob("*")
        if path.is_file()
    }
    published_documentation = (
        repository / ".agents" / "skills" / "repo-documentation-maker"
    )
    actual_documentation = {
        path.relative_to(published_documentation).as_posix(): path.read_bytes()
        for path in published_documentation.rglob("*")
        if path.is_file() and path.name != ".scaffold-manifest.json"
    }
    if actual_documentation != expected_documentation:
        raise RuntimeError(
            "published documentation Skill differs from wheel source"
        )
    manifest = json.loads(
        (
            published_documentation / ".scaffold-manifest.json"
        ).read_text(encoding="utf-8")
    )
    if (
        manifest.get("skill_name") != "repo-documentation-maker"
        or manifest.get("skill_version") != "1.0.0"
    ):
        raise RuntimeError("documentation Skill manifest is invalid")
    combined = b"\n".join(actual_documentation.values()).lower()
    if b"pre-sdd" in combined:
        raise RuntimeError("documentation Skill retains an external association")


def main() -> int:
    args = _arguments()
    with tempfile.TemporaryDirectory(prefix="sdd-harness-dist-smoke-") as raw:
        workspace = Path(raw)
        distribution = (
            args.output_dir.resolve()
            if args.output_dir is not None
            else workspace / "dist"
        )
        distribution.mkdir(parents=True, exist_ok=True)
        tools = workspace / "tools"
        binaries = workspace / "bin"
        invalid_tools = workspace / "invalid-tools"
        invalid_binaries = workspace / "invalid-bin"
        empty = workspace / "empty"
        fixture = workspace / "fixture"
        hooks_fixture = workspace / "hooks-fixture"
        unsupported = workspace / "unsupported"
        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        environment.pop("PYTHONHOME", None)
        environment.pop("VIRTUAL_ENV", None)
        environment.update(
            {
                "UV_TOOL_DIR": str(tools),
                "UV_TOOL_BIN_DIR": str(binaries),
                "UV_NO_PROGRESS": "1",
            }
        )
        _fixture(fixture, environment)
        _fixture(hooks_fixture, environment)
        _fixture(unsupported, environment)
        empty.mkdir()
        unsupported_harness = unsupported / ".harness"
        unsupported_harness.mkdir()
        (unsupported_harness / "harness.yaml").write_text(
            "schema_version: 1.0.0\n"
            "mode: adopt\n"
            "standing_policy: {}\n",
            encoding="utf-8",
        )

        _run(
            [
                "uv",
                "build",
                "--offline",
                "--wheel",
                "--out-dir",
                str(distribution),
            ],
            cwd=ROOT,
            env=environment,
        )
        wheels = list(distribution.glob(f"sdd_harness-{VERSION}-*.whl"))
        if len(wheels) != 1:
            raise RuntimeError(f"expected one {VERSION} wheel, found {wheels}")
        invalid_environment = {
            **environment,
            "UV_TOOL_DIR": str(invalid_tools),
            "UV_TOOL_BIN_DIR": str(invalid_binaries),
        }
        unavailable = _run(
            [
                "uv",
                "tool",
                "install",
                "--offline",
                str(workspace / "missing-source.whl"),
            ],
            cwd=empty,
            env=invalid_environment,
            expected=(1, 2),
        )
        if unavailable.returncode == 0 or (
            invalid_binaries.exists()
            and any(invalid_binaries.iterdir())
        ):
            raise RuntimeError(
                "unavailable installation source left a runnable entrypoint"
            )
        install_command = ["uv", "tool", "install"]
        if not args.allow_network:
            install_command.append("--offline")
        install_command.append(str(wheels[0]))
        _run(install_command, cwd=ROOT, env=environment)
        executable = binaries / (
            "sdd-harness.exe" if os.name == "nt" else "sdd-harness"
        )
        if not executable.is_file():
            raise RuntimeError(f"installed entrypoint is missing: {executable}")
        resolved_entries = [
            path
            for path in binaries.iterdir()
            if path.name.lower().startswith("sdd-harness")
        ]
        if resolved_entries != [executable]:
            raise RuntimeError(
                f"PATH does not contain exactly one Harness runtime: {resolved_entries}"
            )
        resolved = shutil.which(
            "sdd-harness",
            path=os.pathsep.join(
                (str(binaries), environment.get("PATH", ""))
            ),
        )
        if resolved is None or Path(resolved).resolve() != executable.resolve():
            raise RuntimeError(
                f"PATH resolved an unexpected Harness runtime: {resolved}"
            )
        empty_before = _tree_digest(empty)
        runtime_command = [str(executable)]
        runtime_execution = "entrypoint"
        try:
            version_result = _run(
                [*runtime_command, "--version"],
                cwd=empty,
                env=environment,
            )
        except OSError as exc:
            if os.name != "nt" or getattr(exc, "winerror", None) != 4551:
                raise
            tool_python = tools / "sdd-harness" / "Scripts" / "python.exe"
            if not tool_python.is_file():
                raise RuntimeError(
                    "application control blocked the entrypoint and the "
                    "isolated tool Python is missing"
                ) from exc
            runtime_command = [
                str(tool_python),
                "-m",
                "harness_core.cli",
            ]
            runtime_execution = "isolated-python-app-control-fallback"
            version_result = _run(
                [*runtime_command, "--version"],
                cwd=empty,
                env=environment,
            )
        version = version_result.stdout.strip()
        if version != f"sdd-harness {VERSION}":
            raise RuntimeError(f"unexpected version: {version}")
        if _tree_digest(empty) != empty_before:
            raise RuntimeError("version check wrote repository entrypoint files")

        first = json.loads(
            _run(
                [*runtime_command, "init", ".", "--yes", "--json"],
                cwd=fixture,
                env=environment,
            ).stdout
        )
        after_first = _tree_digest(fixture)
        second = json.loads(
            _run(
                [*runtime_command, "init", ".", "--yes", "--json"],
                cwd=fixture,
                env=environment,
            ).stdout
        )
        if first["status"] != "applied" or not first["changed_paths"]:
            raise RuntimeError(f"first init did not publish: {first}")
        if second["status"] != "applied" or second["changed_paths"]:
            raise RuntimeError(f"second init was not empty: {second}")
        if first["projection_id"] is not None or second["projection_id"] is not None:
            raise RuntimeError("first-phase init must not generate a projection")
        if after_first != _tree_digest(fixture):
            raise RuntimeError("idempotent init changed repository bytes")
        _assert_skill_exact(fixture)
        if (
            (fixture / ".codex" / "hooks.json").exists()
            or (fixture / ".codex" / "agents").exists()
            or list(fixture.rglob("dispatch.py"))
        ):
            raise RuntimeError("base init published an optional runtime surface")
        inspect = json.loads(
            _run(
                [*runtime_command, "inspect", ".", "--json"],
                cwd=fixture,
                env=environment,
                expected=(2,),
            ).stdout
        )
        if (
            inspect["status"] != "entrypoint-ready"
            or inspect["mode"] != "projection-pending"
            or inspect["hook_defense"] != "disabled"
        ):
            raise RuntimeError(f"first-phase entrypoint is not ready: {inspect}")

        projection_plan = json.loads(
            _run(
                [*runtime_command, "projection-plan", ".", "--json"],
                cwd=fixture,
                env=environment,
            ).stdout
        )
        plan_file = workspace / "projection-plan.json"
        plan_file.write_text(
            json.dumps(projection_plan),
            encoding="utf-8",
        )
        projection = json.loads(
            _run(
                [
                    *runtime_command,
                    "projection-apply",
                    ".",
                    "--plan",
                    str(plan_file),
                    "--approve-plan",
                    projection_plan["plan_digest"],
                    "--json",
                ],
                cwd=fixture,
                env=environment,
            ).stdout
        )
        if projection["status"] != "applied" or len(
            projection["changed_paths"]
        ) != 5:
            raise RuntimeError(f"second-phase projection failed: {projection}")
        repeated_plan = json.loads(
            _run(
                [*runtime_command, "projection-plan", ".", "--json"],
                cwd=fixture,
                env=environment,
            ).stdout
        )
        if (
            repeated_plan["write_scope"]
            or repeated_plan["projection_id"] != projection["projection_id"]
        ):
            raise RuntimeError("idempotent projection produced changes")
        inspect = json.loads(
            _run(
                [*runtime_command, "inspect", ".", "--json"],
                cwd=fixture,
                env=environment,
            ).stdout
        )
        if inspect["status"] != "active":
            raise RuntimeError(f"second-phase projection is not active: {inspect}")

        hooks = json.loads(
            _run(
                [
                    *runtime_command,
                    "init",
                    ".",
                    "--with-hooks",
                    "--yes",
                    "--json",
                ],
                cwd=hooks_fixture,
                env=environment,
            ).stdout
        )
        if not hooks["with_hooks"] or not (
            hooks_fixture / ".codex" / "hooks.json"
        ).is_file():
            raise RuntimeError("explicit Hook initialization did not configure hooks")
        hook_state = json.loads(
            _run(
                [*runtime_command, "inspect", ".", "--json"],
                cwd=hooks_fixture,
                env=environment,
                expected=(2,),
            ).stdout
        )
        if (
            hook_state["status"] != "entrypoint-ready"
            or hook_state["hook_defense"] != "configured"
        ):
            raise RuntimeError("Hook defense changed entrypoint readiness")

        before_unsupported = _tree_digest(unsupported)
        rejected = json.loads(
            _run(
                [*runtime_command, "init", ".", "--yes", "--json"],
                cwd=unsupported,
                env=environment,
                expected=(2,),
            ).stdout
        )
        if rejected["status"] != "blocked" or rejected[
            "blocker_codes"
        ] != ["HARNESS_RUNTIME_INCOMPATIBLE"]:
            raise RuntimeError(
                f"unsupported configuration was not rejected: {rejected}"
            )
        if before_unsupported != _tree_digest(unsupported):
            raise RuntimeError("unsupported configuration changed repository files")

        python_path = _run(
            ["uv", "python", "find", "3.12"],
            cwd=fixture,
            env=environment,
        ).stdout.strip()
        probe_environment = {
            key: value
            for key, value in environment.items()
            if key.upper() not in {"PYTHONPATH", "PYTHONHOME"}
        }
        probe = _run(
            [
                python_path,
                "-I",
                "-c",
                (
                    "import importlib.util;"
                    "print(importlib.util.find_spec('harness_core'))"
                ),
            ],
            cwd=fixture,
            env=probe_environment,
        ).stdout.strip()
        if probe != "None":
            raise RuntimeError("target project Python can import isolated harness_core")

        artifact_digest = _file_digest(wheels[0])
        checksums = distribution / "SHA256SUMS"
        checksums.write_text(
            f"{artifact_digest.removeprefix('sha256:')}  {wheels[0].name}\n",
            encoding="utf-8",
        )
        result = {
            "status": "passed",
            "wheel": wheels[0].name,
            "version": VERSION,
            "cli_version": version,
            "artifact_digest": artifact_digest,
            "checksums": checksums.name,
            "projection_id": projection["projection_id"],
            "second_init_changed_paths": second["changed_paths"],
            "tree_digest": after_first,
            "skill_bytes": "exact",
            "base_hooks": "disabled",
            "optional_hooks": "configured",
            "historical_config": "rejected-without-write",
            "unavailable_source": "rejected-without-entrypoint",
            "target_python_import": "unavailable",
            "runtime_execution": runtime_execution,
        }
        rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
        if args.report is not None:
            report = args.report.resolve()
            report.parent.mkdir(parents=True, exist_ok=True)
            report.write_text(rendered, encoding="utf-8")
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
