#!/usr/bin/env python3
"""Run one selected Local task and print summarized Evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from harness_core import run_local_task


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
    parser.add_argument("--confirmation", type=Path)
    args = parser.parse_args()
    catalog = yaml.safe_load(
        (args.repository / ".harness" / "tasks.yaml").read_text("utf-8")
    )
    task = next(item for item in catalog["tasks"] if item["id"] == args.task_id)
    adapter = yaml.safe_load(args.adapter.read_text("utf-8"))
    if adapter.get("type") != "local" or task.get("backend") != "local":
        raise SystemExit("run_task.py currently requires a registered Local adapter")
    command = task.get("command")
    if not isinstance(command, list) or not all(isinstance(item, str) for item in command):
        raise SystemExit("Local Task must define command as an argument array")
    evidence = run_local_task(
        task,
        command,
        args.repository,
        args.level,
        grant=json.loads(args.grant.read_text("utf-8")),
        manifest=json.loads(args.manifest.read_text("utf-8")),
        selection=json.loads(args.selection.read_text("utf-8")),
        request=json.loads(args.request.read_text("utf-8")),
        confirmation=(
            json.loads(args.confirmation.read_text("utf-8"))
            if args.confirmation
            else None
        ),
    )
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0 if evidence["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
