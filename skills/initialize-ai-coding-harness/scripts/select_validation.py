#!/usr/bin/env python3
"""Select the lowest sufficient registered validation set."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from harness_core import select_validation


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repository", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("diff", type=Path, help="JSON array of actual changed paths")
    parser.add_argument("--facts", type=Path)
    args = parser.parse_args()
    config = args.repository / ".harness"
    manifest = json.loads(args.manifest.read_text("utf-8"))
    actual_diff = json.loads(args.diff.read_text("utf-8"))
    facts = json.loads(args.facts.read_text("utf-8")) if args.facts else {}
    impact = yaml.safe_load((config / "impact.yaml").read_text("utf-8"))
    tasks = yaml.safe_load((config / "tasks.yaml").read_text("utf-8"))
    result = select_validation(manifest, actual_diff, impact, tasks, facts)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "selected" else 1


if __name__ == "__main__":
    raise SystemExit(main())
