#!/usr/bin/env python3
"""Build, install, and exercise the public Harness 2.0 distribution."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).parents[1]
CANONICAL_SKILL = (
    ROOT / "src" / "harness_core" / "resources" / "repo_skill" / "harness"
)


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


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="sdd-harness-dist-smoke-") as raw:
        workspace = Path(raw)
        distribution = workspace / "dist"
        tools = workspace / "tools"
        binaries = workspace / "bin"
        fixture = workspace / "fixture"
        migration = workspace / "migration"
        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        environment.pop("PYTHONHOME", None)
        environment.update(
            {
                "UV_TOOL_DIR": str(tools),
                "UV_TOOL_BIN_DIR": str(binaries),
                "UV_NO_PROGRESS": "1",
            }
        )
        _fixture(fixture, environment)
        _fixture(migration, environment)
        legacy = migration / ".harness"
        legacy.mkdir()
        (legacy / "harness.yaml").write_text(
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
        wheels = list(distribution.glob("sdd_harness-2.0.0-*.whl"))
        if len(wheels) != 1:
            raise RuntimeError(f"expected one 2.0.0 wheel, found {wheels}")
        _run(
            ["uv", "tool", "install", "--offline", str(wheels[0])],
            cwd=ROOT,
            env=environment,
        )
        executable = binaries / (
            "sdd-harness.exe" if os.name == "nt" else "sdd-harness"
        )
        if not executable.is_file():
            raise RuntimeError(f"installed entrypoint is missing: {executable}")
        version = _run(
            [str(executable), "--version"], cwd=fixture, env=environment
        ).stdout.strip()
        if version != "sdd-harness 2.0.0":
            raise RuntimeError(f"unexpected version: {version}")

        first = json.loads(
            _run(
                [str(executable), "init", ".", "--yes", "--json"],
                cwd=fixture,
                env=environment,
            ).stdout
        )
        after_first = _tree_digest(fixture)
        second = json.loads(
            _run(
                [str(executable), "init", ".", "--yes", "--json"],
                cwd=fixture,
                env=environment,
            ).stdout
        )
        if first["status"] != "applied" or not first["changed_paths"]:
            raise RuntimeError(f"first init did not publish: {first}")
        if second["status"] != "applied" or second["changed_paths"]:
            raise RuntimeError(f"second init was not empty: {second}")
        if first["projection_id"] != second["projection_id"]:
            raise RuntimeError("projection_id changed without a source change")
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
                [str(executable), "inspect", ".", "--json"],
                cwd=fixture,
                env=environment,
            ).stdout
        )
        if inspect["status"] != "active" or inspect["hook_defense"] != "disabled":
            raise RuntimeError(f"Skill-first runtime is not active: {inspect}")

        hooks = json.loads(
            _run(
                [
                    str(executable),
                    "init",
                    ".",
                    "--with-hooks",
                    "--yes",
                    "--json",
                ],
                cwd=fixture,
                env=environment,
            ).stdout
        )
        if not hooks["with_hooks"] or not (
            fixture / ".codex" / "hooks.json"
        ).is_file():
            raise RuntimeError("explicit Hook initialization did not configure hooks")
        hook_state = json.loads(
            _run(
                [str(executable), "inspect", ".", "--json"],
                cwd=fixture,
                env=environment,
            ).stdout
        )
        if hook_state["status"] != "active":
            raise RuntimeError("Hook defense changed governance authority")

        before_migration = _tree_digest(migration)
        required = json.loads(
            _run(
                [str(executable), "init", ".", "--yes", "--json"],
                cwd=migration,
                env=environment,
                expected=(2,),
            ).stdout
        )
        if required["status"] != "migration-required":
            raise RuntimeError("legacy --yes did not require an exact plan")
        if before_migration != _tree_digest(migration):
            raise RuntimeError("legacy migration planning wrote repository files")
        migrated = json.loads(
            _run(
                [
                    str(executable),
                    "init",
                    ".",
                    "--approve-plan",
                    required["plan_digest"],
                    "--json",
                ],
                cwd=migration,
                env=environment,
            ).stdout
        )
        if migrated["status"] != "applied":
            raise RuntimeError(f"approved migration failed: {migrated}")

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

        print(
            json.dumps(
                {
                    "status": "passed",
                    "wheel": wheels[0].name,
                    "version": version,
                    "projection_id": first["projection_id"],
                    "skill_bytes": "exact",
                    "base_hooks": "disabled",
                    "optional_hooks": "configured",
                    "migration": "digest-approved",
                    "target_python_import": "unavailable",
                },
                indent=2,
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
