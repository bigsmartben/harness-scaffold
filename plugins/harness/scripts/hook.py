"""Compatibility wrapper that calls the isolated Harness executable on PATH."""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    completed = subprocess.run(
        ["sdd-harness", "hook"],
        input=sys.stdin.buffer.read(),
        stdout=sys.stdout.buffer,
        stderr=sys.stderr.buffer,
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
