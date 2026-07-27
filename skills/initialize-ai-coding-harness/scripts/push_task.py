#!/usr/bin/env python3
"""Run one confirmed git-remote Push Task and print bound Evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from harness_core import run_git_remote_push_task


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repository", type=Path)
    parser.add_argument("task_id")
    parser.add_argument("--level", required=True)
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--grant", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--confirmation", type=Path, required=True)
    args = parser.parse_args()

    catalog = yaml.safe_load(
        (args.repository / ".harness" / "tasks.yaml").read_text("utf-8")
    )
    boundaries = yaml.safe_load(
        (args.repository / ".harness" / "boundaries.yaml").read_text("utf-8")
    )
    task = next(item for item in catalog["tasks"] if item["id"] == args.task_id)
    adapter = yaml.safe_load(args.adapter.read_text("utf-8"))
    evidence = run_git_remote_push_task(
        task,
        adapter,
        args.repository,
        args.level,
        grant=json.loads(args.grant.read_text("utf-8")),
        manifest=json.loads(args.manifest.read_text("utf-8")),
        selection=json.loads(args.selection.read_text("utf-8")),
        request=json.loads(args.request.read_text("utf-8")),
        confirmation=json.loads(args.confirmation.read_text("utf-8")),
        branch_gate=boundaries["branch_gate"],
    )
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0 if evidence["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
