#!/usr/bin/env python3
"""Assess GitHub CI/CD platform facts without claiming live verification."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from harness_core import assess_github_platform


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("facts", type=Path)
    parser.add_argument("--required-check", action="append", default=[])
    parser.add_argument("--protected-environment")
    args = parser.parse_args()

    facts = yaml.safe_load(args.facts.read_text("utf-8"))
    if not isinstance(facts, dict):
        raise SystemExit("platform facts must be a YAML or JSON object")

    result = assess_github_platform(
        facts,
        required_checks=args.required_check,
        protected_environment=args.protected_environment,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
