"""The four-command Harness 3.0 local CLI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from . import __version__
from .contracts import validate_project_config
from .initializer import CONFIG_RELATIVE_PATH, initialize_repository
from .model import (
    CONTRACT_VERSION,
    CORE_VERSION,
    DOMAINS,
    PROJECTION_COMPILER_VERSION,
    SCHEMA_VERSION,
)
from .projection import (
    compile_model_lock,
    default_model_lock_path,
    project_model_lock,
    validate_model_lock,
)


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


def _paths(repository: Path) -> tuple[Path, Path]:
    root = repository.resolve()
    return root / CONFIG_RELATIVE_PATH, default_model_lock_path(root)


def _init(args: argparse.Namespace) -> int:
    result = initialize_repository(args.repository)
    _print(result, compact=args.json)
    return 0 if result["status"] == "initialized" else 2


def _project(args: argparse.Namespace) -> int:
    config_path, lock_path = _paths(args.repository)
    result = project_model_lock(config_path, lock_path)
    _print(result, compact=args.json)
    return 0 if result["status"] in {"projected", "unchanged"} else 2


def _validate(args: argparse.Namespace) -> int:
    config_path, lock_path = _paths(args.repository)
    config_issues = validate_project_config(config_path)
    issues = (
        config_issues
        if config_issues
        else validate_model_lock(config_path, lock_path)
    )
    result = {
        "status": "valid" if not issues else "invalid",
        "repository": str(args.repository.resolve()),
        "diagnostics": [issue.as_dict() for issue in issues],
    }
    _print(result, compact=args.json)
    return 0 if not issues else 2


def _inspect(args: argparse.Namespace) -> int:
    config_path, lock_path = _paths(args.repository)
    config_issues = validate_project_config(config_path)
    if config_issues:
        result = {
            "status": "invalid",
            "repository": str(args.repository.resolve()),
            "schema_version": SCHEMA_VERSION,
            "core_version": CORE_VERSION,
            "contract_version": CONTRACT_VERSION,
            "compiler_version": PROJECTION_COMPILER_VERSION,
            "rule_counts": {domain: 0 for domain in DOMAINS},
            "source_digest": None,
            "projection_digest": None,
            "diagnostics": [
                issue.as_dict() for issue in config_issues
            ],
        }
        _print(result, compact=args.json)
        return 2

    expected = compile_model_lock(config_path)
    lock_issues = validate_model_lock(config_path, lock_path)
    counts = {domain: 0 for domain in DOMAINS}
    for rule in expected["rules"]:
        counts[rule["domain"]] += 1
    result = {
        "status": "valid" if not lock_issues else "invalid",
        "repository": str(args.repository.resolve()),
        "schema_version": SCHEMA_VERSION,
        "core_version": CORE_VERSION,
        "contract_version": CONTRACT_VERSION,
        "compiler_version": PROJECTION_COMPILER_VERSION,
        "rule_counts": counts,
        "source_digest": expected["source_digest"],
        "projection_digest": expected["projection_digest"],
        "diagnostics": [
            issue.as_dict() for issue in lock_issues
        ],
    }
    _print(result, compact=args.json)
    return 0 if not lock_issues else 2


def _repository_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "repository",
        nargs="?",
        type=Path,
        default=Path.cwd(),
        help="repository directory (default: current directory)",
    )


def _json_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="emit compact JSON")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sdd-harness",
        description="Harness 3.0 fixed specification governance scaffold",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser(
        "init",
        help="create the minimal v3 config, Skill, and model lock",
    )
    _repository_argument(init_parser)
    _json_argument(init_parser)
    init_parser.set_defaults(handler=_init)

    project_parser = subparsers.add_parser(
        "project",
        help="atomically rebuild the deterministic model lock",
    )
    _repository_argument(project_parser)
    _json_argument(project_parser)
    project_parser.set_defaults(handler=_project)

    validate_parser = subparsers.add_parser(
        "validate",
        help="read-only validation of config and model lock",
    )
    _repository_argument(validate_parser)
    _json_argument(validate_parser)
    validate_parser.set_defaults(handler=_validate)

    inspect_parser = subparsers.add_parser(
        "inspect",
        help="read-only version, digest, rule count, and diagnostic summary",
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
                        "path": "",
                        "message": str(exc),
                    }
                ],
            },
            compact=getattr(args, "json", False),
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
