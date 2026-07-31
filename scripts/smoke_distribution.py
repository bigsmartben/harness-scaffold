"""Isolated wheel/sdist smoke for the Harness 4 consumer contract."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]
DIST = ROOT / "dist"
VERSION = "4.0.0"


def run(
    arguments: list[str],
    *,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    return subprocess.run(
        arguments,
        cwd=cwd,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def require_success(result: subprocess.CompletedProcess[str]) -> None:
    if result.returncode:
        raise AssertionError(
            f"command failed ({result.returncode}):\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


def main() -> None:
    wheel = DIST / f"sdd_harness-{VERSION}-py3-none-any.whl"
    sdist = DIST / f"sdd_harness-{VERSION}.tar.gz"
    if not wheel.is_file() or not sdist.is_file():
        raise AssertionError("build the 4.0.0 wheel and sdist before smoke")

    required_resources = {
        "harness_core/resources/schemas/rule.schema.json",
        "harness_core/resources/schemas/operation.schema.json",
        "harness_core/resources/schemas/load.schema.json",
        "harness_core/resources/schemas/load-result.schema.json",
        "harness_core/resources/schemas/enforcement.schema.json",
        "harness_core/resources/schemas/state.schema.json",
        "harness_core/resources/schemas/projection.schema.json",
        "harness_core/resources/repo_skill/harness/SKILL.md",
    }
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        expected_skill = archive.read(
            "harness_core/resources/repo_skill/harness/SKILL.md"
        )
        if not required_resources.issubset(names):
            raise AssertionError("wheel is missing current contract resources")
        if any(
            name.endswith(("harness.schema.json", "governance.schema.json"))
            for name in names
        ):
            raise AssertionError("wheel contains superseded guidance-only schemas")
    with tarfile.open(sdist, "r:gz") as archive:
        names = archive.getnames()
        if not all(
            any(name.endswith(f"src/{resource}") for name in names)
            for resource in required_resources
        ):
            raise AssertionError("sdist is missing current contract resources")

    with tempfile.TemporaryDirectory(prefix="harness-v4-smoke-") as raw:
        root = Path(raw)
        environment = root / "venv"
        require_success(
            run(
                [
                    "uv",
                    "--no-config",
                    "venv",
                    "--python",
                    sys.executable,
                    "--system-site-packages",
                    str(environment),
                ]
            )
        )
        python = (
            environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        )
        require_success(
            run(
                [
                    "uv",
                    "--no-config",
                    "pip",
                    "install",
                    "--python",
                    str(python),
                    str(wheel),
                ]
            )
        )
        executable = (
            environment / ("Scripts/harness.exe" if os.name == "nt" else "bin/harness")
        )
        version = run([str(executable), "--version"])
        require_success(version)
        if version.stdout.strip() != "harness 4.0.0":
            raise AssertionError("installed entrypoint version mismatch")

        consumer = root / "consumer"
        (consumer / "src").mkdir(parents=True)
        (consumer / "src/main.py").write_text(
            "VALUE = 1\n", encoding="utf-8"
        )
        loaded = run([str(executable), "load", str(consumer), "--json"])
        require_success(loaded)
        load_result = json.loads(loaded.stdout)
        if load_result["status"] != "loaded":
            raise AssertionError("fresh consumer load did not complete")
        generated_skill = (
            consumer / ".agents/skills/harness/SKILL.md"
        ).read_bytes()
        if generated_skill != expected_skill:
            raise AssertionError(
                "generated consumer Skill differs from wheel resource"
            )
        inspected = run(
            [str(executable), "inspect", str(consumer), "--json"]
        )
        require_success(inspected)
        first_inspection = json.loads(inspected.stdout)
        if first_inspection["rule_counts"]["enabled"] != 4:
            raise AssertionError("fresh load did not project four domain baselines")
        state_path = consumer / ".harness/governance/state.json"
        first_state = state_path.read_bytes()
        repeated = run([str(executable), "load", str(consumer), "--json"])
        require_success(repeated)
        if json.loads(repeated.stdout)["changed"]:
            raise AssertionError("identical repeated load reported drift")
        if state_path.read_bytes() != first_state:
            raise AssertionError("identical repeated load rewrote authoritative state")

        (consumer / "src/main.py").write_text(
            "VALUE = 2\n", encoding="utf-8"
        )
        recalibrated = run(
            [str(executable), "load", str(consumer), "--json"]
        )
        require_success(recalibrated)
        recalibrated_result = json.loads(recalibrated.stdout)
        if not recalibrated_result["changed"]:
            raise AssertionError("repository fact change did not refresh governance")
        if (
            recalibrated_result["projection"]["projection_id"]
            == first_inspection["projection_id"]
        ):
            raise AssertionError("repository fact change left projection current")

        legacy = root / "legacy-consumer"
        config = legacy / ".harness/harness.yaml"
        config.parent.mkdir(parents=True)
        config.write_text(
            yaml.safe_dump(
                {
                    "schema_version": "3.0.1",
                    "rule_instances": {
                        "specification": [],
                        "implementation": [],
                        "verification": [
                            {
                                "rule_id": "contract-tests",
                                "directive": "Run contract tests.",
                                "scope": ["tests/**"],
                            }
                        ],
                        "delivery": [],
                    },
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        upgraded = run([str(executable), "load", str(legacy), "--json"])
        require_success(upgraded)
        if config.exists():
            raise AssertionError("legacy config remained a second current SSOT")
        if not (
            legacy / ".harness/legacy/3.0.1/harness.yaml"
        ).is_file():
            raise AssertionError("legacy source was not archived")

    if (ROOT / ".harness/governance/state.json").exists():
        raise AssertionError("distribution smoke polluted maintainer root")
    if (ROOT / ".agents/skills/harness/SKILL.md").exists():
        raise AssertionError("distribution smoke installed a consumer Skill at root")


if __name__ == "__main__":
    main()
