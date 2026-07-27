"""Public sdd-harness compatibility CLI and internal adapter entrypoints."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from . import __version__
from .codex_adapter import handle_hook
from .initializer import apply_initialization_plan, build_initialization_plan
from .mcp_server import serve


def _print(value: dict, *, compact: bool = False) -> None:
    print(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":") if compact else None,
            indent=None if compact else 2,
        )
    )


def _init(args: argparse.Namespace) -> int:
    repository = args.repository.resolve()
    if not repository.is_dir():
        _print(
            {
                "status": "blocked",
                "blocker_codes": ["CONFIG_INVALID", "HANDOFF_REQUIRED"],
                "message": "target repository does not exist",
            },
            compact=args.json,
        )
        return 2
    plan = build_initialization_plan(repository)
    if plan["blocker_codes"]:
        _print(
            {
                "status": "blocked",
                "plan_digest": plan["plan_digest"],
                "write_scope": plan["write_scope"],
                "blocker_codes": plan["blocker_codes"],
            },
            compact=args.json,
        )
        return 2
    if not args.yes:
        _print(
            {
                "status": "confirmation-required",
                "mode": plan["mode"],
                "plan_digest": plan["plan_digest"],
                "projection_id": plan["projection_id"],
                "write_scope": plan["write_scope"],
                "blocker_codes": ["HANDOFF_REQUIRED"],
            },
            compact=args.json,
        )
        return 2
    result = apply_initialization_plan(repository, plan)
    _print(result, compact=args.json)
    return 0 if result["status"] == "applied" else 2


def _hook(args: argparse.Namespace) -> int:
    payload = json.load(sys.stdin)
    repository = Path(payload.get("cwd") or args.repository or ".").resolve()
    output = handle_hook(payload, repository)
    if output:
        print(json.dumps(output, ensure_ascii=False, separators=(",", ":")))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sdd-harness")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser(
        "init", help="compile and publish a repo-first governance projection"
    )
    init_parser.add_argument("repository", nargs="?", type=Path, default=Path.cwd())
    init_parser.add_argument(
        "--yes", action="store_true", help="confirm the exact generated Plan"
    )
    init_parser.add_argument("--json", action="store_true", help="emit compact JSON")
    init_parser.set_defaults(handler=_init)

    hook_parser = subparsers.add_parser("hook", help=argparse.SUPPRESS)
    hook_parser.add_argument("--repository", type=Path)
    hook_parser.set_defaults(handler=_hook)

    mcp_parser = subparsers.add_parser("mcp", help=argparse.SUPPRESS)
    mcp_parser.set_defaults(handler=lambda _args: serve())
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
