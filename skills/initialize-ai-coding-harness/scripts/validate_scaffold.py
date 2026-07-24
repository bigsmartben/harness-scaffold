#!/usr/bin/env python3
"""Validate Harness YAML against schemas and cross-file references."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from harness_core import validate_config


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repository", type=Path)
    args = parser.parse_args()
    skill_root = Path(__file__).parents[1]
    issues = validate_config(
        args.repository / ".harness", skill_root / "assets" / "schemas"
    )
    print(json.dumps([asdict(issue) for issue in issues], indent=2, sort_keys=True))
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())

