#!/usr/bin/env python3
"""Discover repository facts without writing to the target."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from harness_core import discover_repository


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repository", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = discover_repository(args.repository)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

