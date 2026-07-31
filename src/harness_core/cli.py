"""Harness 4 consumer bootstrap and typed governance CLI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from . import __version__
from .bootstrap import load_and_bootstrap
from .scaffold import GovernanceRepository, compile_governance_projection


def _print(value: dict[str, Any], *, compact: bool) -> None:
    print(
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":") if compact else None,
            indent=None if compact else 2,
        )
    )


def _repository_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "repository",
        nargs="?",
        type=Path,
        default=Path.cwd(),
        help="consumer repository directory (default: current directory)",
    )


def _json_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="emit compact JSON")


def _load(args: argparse.Namespace) -> int:
    result = load_and_bootstrap(args.repository)
    _print(result, compact=args.json)
    return 0 if result["status"] == "loaded" else 2


def _operate(args: argparse.Namespace) -> int:
    try:
        request = json.loads(args.request_json)
    except json.JSONDecodeError as exc:
        result = {
            "status": "rejected",
            "diagnostics": [
                {
                    "code": "OPERATION_JSON_INVALID",
                    "message": str(exc),
                }
            ],
        }
        _print(result, compact=args.json)
        return 2
    repository = GovernanceRepository(args.repository)
    registered = repository.register(request)
    if registered["status"] not in {"pending", "applied"}:
        _print(registered, compact=args.json)
        return 2
    operation_id = request.get("operation_id")
    result = repository.apply(operation_id)
    _print(result, compact=args.json)
    return 0 if result["status"] == "applied" else 2


def _cancel(args: argparse.Namespace) -> int:
    repository = GovernanceRepository(args.repository)
    result = repository.cancel(args.operation_id)
    _print(result, compact=args.json)
    return 0 if result["status"] == "cancelled" else 2


def _inspect(args: argparse.Namespace) -> int:
    repository = GovernanceRepository(args.repository)
    state = repository.read()
    projection = compile_governance_projection(state)
    result = {
        "status": "valid",
        "repository": str(args.repository.resolve()),
        "contract_version": __version__,
        "state_revision": state["state_revision"],
        "rule_counts": {
            "enabled": len(projection["rules"]),
            "disabled": len(projection["disabled_rules"]),
            "deleted": len(state["deleted_rules"]),
        },
        "pending_operations": sorted(
            operation_id
            for operation_id, operation in state["operations"].items()
            if operation["status"] == "pending"
        ),
        "projection_id": projection["projection_id"],
        "diagnostics": [],
    }
    _print(result, compact=args.json)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="harness",
        description="Harness 4 repository governance interface",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    load_parser = subparsers.add_parser(
        "load",
        help="discover, calibrate, persist, and bootstrap repository governance",
    )
    _repository_argument(load_parser)
    _json_argument(load_parser)
    load_parser.set_defaults(handler=_load)

    operate_parser = subparsers.add_parser(
        "operate",
        help="register and atomically apply a typed governance OperationRequest",
    )
    _repository_argument(operate_parser)
    operate_parser.add_argument(
        "--request-json",
        required=True,
        help="canonical OperationRequest JSON",
    )
    _json_argument(operate_parser)
    operate_parser.set_defaults(handler=_operate)

    cancel_parser = subparsers.add_parser(
        "cancel",
        help="cancel one authoritative pending operation",
    )
    _repository_argument(cancel_parser)
    cancel_parser.add_argument(
        "operation_id",
        nargs="?",
        help="pending operation_id; omit only when exactly one is pending",
    )
    _json_argument(cancel_parser)
    cancel_parser.set_defaults(handler=_cancel)

    inspect_parser = subparsers.add_parser(
        "inspect",
        help="inspect authoritative state and deterministic projection",
    )
    _repository_argument(inspect_parser)
    _json_argument(inspect_parser)
    inspect_parser.set_defaults(handler=_inspect)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        _print(
            {
                "status": "invalid",
                "diagnostics": [
                    {
                        "code": "CLI_INPUT_INVALID",
                        "message": str(exc),
                    }
                ],
            },
            compact=getattr(args, "json", False),
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
