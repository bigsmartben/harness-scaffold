#!/usr/bin/env python3
"""Evaluate Merge Evidence or a declaration-bound Publish confirmation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from harness_core import evaluate_merge, execute_publish


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pipeline", type=Path)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--request", type=Path)
    parser.add_argument("--confirmation", type=Path)
    parser.add_argument("--platform", type=Path)
    args = parser.parse_args()
    pipeline = yaml.safe_load(args.pipeline.read_text("utf-8"))
    request = json.loads(args.request.read_text("utf-8")) if args.request else None
    confirmation = (
        json.loads(args.confirmation.read_text("utf-8"))
        if args.confirmation
        else None
    )
    platform = (
        json.loads(args.platform.read_text("utf-8"))
        if args.platform
        else None
    )
    if pipeline["kind"] == "merge":
        evidence = json.loads(args.evidence.read_text("utf-8")) if args.evidence else []
        result = evaluate_merge(
            pipeline, evidence, request, confirmation, platform
        )
    else:
        if request is None:
            raise SystemExit("--request is required for publish")
        result = execute_publish(
            pipeline,
            request,
            confirmation,
            lambda: {"dispatch": "approved"},
            platform,
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
