#!/usr/bin/env python3
"""Evaluate Merge Evidence or a declaration-bound Publish confirmation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from harness_core import evaluate_pipeline_readiness, finalize_pipeline


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
    evidence = json.loads(args.evidence.read_text("utf-8")) if args.evidence else []
    result = (
        finalize_pipeline(
            pipeline, evidence, request, confirmation, platform
        )
        if platform is not None
        else evaluate_pipeline_readiness(
            pipeline, evidence, request, confirmation
        )
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] in {"ready-for-dispatch", "passed"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
