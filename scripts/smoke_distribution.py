#!/usr/bin/env python3
"""Build and exercise the public distribution in isolated uv tool directories."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).parents[1]
VERSION = "1.0.0"


def _run(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
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
        fixture = workspace / "fixture"
        fixture.mkdir()

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
        wheels = list(distribution.glob(f"sdd_harness-{VERSION}-*.whl"))
        if len(wheels) != 1:
            raise RuntimeError(f"expected one {VERSION} wheel, found {wheels}")

        install_command = ["uv", "tool", "install"]
        if not args.allow_network:
            install_command.append("--offline")
        install_command.append(str(wheels[0]))
        _run(install_command, cwd=ROOT, env=environment)
        executable = binaries / ("sdd-harness.exe" if os.name == "nt" else "sdd-harness")
        if not executable.is_file():
            raise RuntimeError(f"installed entrypoint is missing: {executable}")

        cli_version = _run(
            [str(executable), "--version"],
            cwd=fixture,
            env=environment,
        ).stdout.strip()
        if cli_version != f"sdd-harness {VERSION}":
            raise RuntimeError(f"unexpected version: {cli_version}")

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
            "cli_version": cli_version,
            "artifact_digest": artifact_digest,
            "checksums": checksums.name,
            "projection_id": first["projection_id"],
            "second_init_changed_paths": second["changed_paths"],
            "tree_digest": after_second,
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
