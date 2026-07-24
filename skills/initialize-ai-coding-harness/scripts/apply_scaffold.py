#!/usr/bin/env python3
"""Apply only actions listed in an approved Harness plan."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from harness_core import apply_plan


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", type=Path)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    assets = Path(__file__).parents[1] / "assets"
    print(json.dumps(apply_plan(plan, assets), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

