#!/usr/bin/env python3
"""Build and exercise the public distribution in isolated uv tool directories."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).parents[1]


def _run(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    input_text: str | None = None,
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
    if result.returncode != 0:
        raise RuntimeError(
            f"command failed ({result.returncode}): {command}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return f"sha256:{digest.hexdigest()}"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="sdd-harness-dist-smoke-") as raw:
        workspace = Path(raw)
        distribution = workspace / "dist"
        tools = workspace / "tools"
        binaries = workspace / "bin"
        fixture = workspace / "fixture"
        fixture.mkdir()
        (fixture / "pyproject.toml").write_text(
            """
[project]
name = "distribution-smoke-fixture"
version = "0.1.0"

[tool.ai-coding-harness.tasks]
test = ["python", "-c", "print('passed')"]
""".strip()
            + "\n",
            encoding="utf-8",
        )

        environment = os.environ.copy()
        environment.update(
            {
                "UV_TOOL_DIR": str(tools),
                "UV_TOOL_BIN_DIR": str(binaries),
                "UV_NO_PROGRESS": "1",
            }
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
        wheels = list(distribution.glob("sdd_harness-1.0.0-*.whl"))
        if len(wheels) != 1:
            raise RuntimeError(f"expected one 1.0.0 wheel, found {wheels}")

        _run(
            ["uv", "tool", "install", "--offline", str(wheels[0])],
            cwd=ROOT,
            env=environment,
        )
        executable = binaries / ("sdd-harness.exe" if os.name == "nt" else "sdd-harness")
        if not executable.is_file():
            raise RuntimeError(f"installed entrypoint is missing: {executable}")

        version = _run(
            [str(executable), "--version"],
            cwd=fixture,
            env=environment,
        ).stdout.strip()
        if version != "sdd-harness 1.0.0":
            raise RuntimeError(f"unexpected version: {version}")

        first = json.loads(
            _run(
                [str(executable), "init", "--yes", "--json"],
                cwd=fixture,
                env=environment,
            ).stdout
        )
        after_first = _tree_digest(fixture)
        second = json.loads(
            _run(
                [str(executable), "init", "--yes", "--json"],
                cwd=fixture,
                env=environment,
            ).stdout
        )
        after_second = _tree_digest(fixture)

        if first["status"] != "applied" or not first["changed_paths"]:
            raise RuntimeError(f"first init did not publish a projection: {first}")
        if second["status"] != "applied" or second["changed_paths"]:
            raise RuntimeError(f"second init was not an empty diff: {second}")
        if first["projection_id"] != second["projection_id"]:
            raise RuntimeError("projection_id changed without an input change")
        if after_first != after_second:
            raise RuntimeError("repository bytes changed during idempotent init")

        session_start = json.loads(
            _run(
                [str(executable), "hook"],
                cwd=fixture,
                env=environment,
                input_text=json.dumps(
                    {
                        "hook_event_name": "SessionStart",
                        "cwd": str(fixture),
                    }
                ),
            ).stdout
        )
        bypass = json.loads(
            _run(
                [str(executable), "hook"],
                cwd=fixture,
                env=environment,
                input_text=json.dumps(
                    {
                        "hook_event_name": "PreToolUse",
                        "tool_name": "shell_command",
                        "tool_input": {
                            "command": "python -m pytest"
                        },
                        "cwd": str(fixture),
                    }
                ),
            ).stdout
        )
        missing_evidence = json.loads(
            _run(
                [str(executable), "hook"],
                cwd=fixture,
                env=environment,
                input_text=json.dumps(
                    {
                        "hook_event_name": "Stop",
                        "cwd": str(fixture),
                    }
                ),
            ).stdout
        )
        if "is active" not in session_start.get("systemMessage", ""):
            raise RuntimeError(f"Codex adapter did not load projection: {session_start}")
        if (
            bypass.get("hookSpecificOutput", {}).get("permissionDecision")
            != "deny"
        ):
            raise RuntimeError(f"raw Action bypass was not denied: {bypass}")
        if missing_evidence.get("stopReason") != "GOVERNANCE_EVIDENCE_INCOMPLETE":
            raise RuntimeError(
                f"missing Evidence did not fail closed: {missing_evidence}"
            )

        print(
            json.dumps(
                {
                    "status": "passed",
                    "wheel": wheels[0].name,
                    "version": version,
                    "projection_id": first["projection_id"],
                    "second_init_changed_paths": second["changed_paths"],
                    "codex_adapter": "active",
                    "raw_action_bypass": "denied",
                    "missing_evidence": "blocked",
                    "tree_digest": after_second,
                },
                indent=2,
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
