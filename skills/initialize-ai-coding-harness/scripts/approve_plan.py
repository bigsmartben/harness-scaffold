#!/usr/bin/env python3
"""Create a separate approval artifact for an explicitly confirmed plan."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from harness_core import create_plan_approval


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", type=Path)
    parser.add_argument("--confirmed-at")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    repository = Path(plan["repository_root"]).resolve()
    if args.output and args.output.resolve().is_relative_to(repository):
        parser.error("--output must be outside the target repository")
    approval = create_plan_approval(plan, args.confirmed_at)
    payload = json.dumps(approval, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
