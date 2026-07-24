#!/usr/bin/env python3
"""Build a deterministic Harness plan from discovery JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from harness_core import build_plan


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("discovery", type=Path)
    parser.add_argument("--mode", required=True, choices=("adopt", "bootstrap", "audit", "update"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    facts = json.loads(args.discovery.read_text(encoding="utf-8"))
    payload = json.dumps(build_plan(facts, args.mode), indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

