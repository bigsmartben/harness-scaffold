"""Public bootstrap CLI and machine-oriented Harness 2.0 adapters."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from . import __version__
from .codex_adapter import handle_hook, runtime_state
from .commit import apply_commit_plan, build_commit_plan
from .decisions import (
    DecisionStateError,
    create_task_decision,
    end_task_decision,
    load_task_decision,
    save_task_decision,
)
from .delivery import (
    build_platform_gate_evidence,
    build_controlled_delivery_plan,
    prepare_controlled_delivery_request,
    validate_controlled_delivery_receipt,
)
from .initializer import (
    apply_initialization_plan,
    apply_projection_plan,
    build_initialization_plan,
    build_projection_plan,
)
from .issues import (
    apply_local_issue_plan,
    build_issue_plan,
    prepare_remote_issue_request,
    validate_remote_issue_receipt,
)
from .mcp_server import serve
from .runner import run_local_action, run_local_task_ref
from .push import apply_push_plan, build_push_plan
from .policy import apply_project_policy_plan, build_project_policy_plan
from .selection import analyze_workspace_impact
from .workspace import workspace_state


def _print(value: dict[str, Any], *, compact: bool = False) -> None:
    print(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":") if compact else None,
            indent=None if compact else 2,
        )
    )


def _load_document(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _init(args: argparse.Namespace) -> int:
    repository = args.repository.resolve()
    if not repository.is_dir():
        _print(
            {
                "status": "blocked",
                "blocker_codes": ["CONFIG_INVALID", "HANDOFF_REQUIRED"],
                "summary": "The target repository does not exist.",
            },
            compact=args.json,
        )
        return 2
    plan = build_initialization_plan(
        repository, with_hooks=args.with_hooks
    )
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
    approval = args.approve_plan or (
        plan["plan_digest"] if args.yes else None
    )
    if approval is None:
        _print(
            {
                "status": "confirmation-required",
                "mode": plan["mode"],
                "repository_model": plan["repository_model"],
                "phase": plan["phase"],
                "plan_digest": plan["plan_digest"],
                "write_scope": plan["write_scope"],
                "preserved_paths": plan["preserved_paths"],
                "with_hooks": plan["with_hooks"],
                "blocker_codes": ["HANDOFF_REQUIRED"],
            },
            compact=args.json,
        )
        return 2
    if approval != plan["plan_digest"]:
        _print(
            {
                "status": "blocked",
                "plan_digest": plan["plan_digest"],
                "blocker_codes": ["INITIALIZATION_PLAN_STALE"],
            },
            compact=args.json,
        )
        return 2
    result = apply_initialization_plan(
        repository, plan, approved_plan_digest=approval
    )
    if result["status"] == "applied" and plan["phase"] == "entrypoint":
        result["next_step"] = (
            "Use $harness to plan and generate the current repository "
            "governance projection."
        )
    _print(result, compact=args.json)
    return 0 if result["status"] == "applied" else 2


def _inspect(args: argparse.Namespace) -> int:
    result = runtime_state(args.repository.resolve())
    _print(result, compact=args.json)
    return 0 if result["status"] == "active" else 2


def _projection_plan(args: argparse.Namespace) -> int:
    plan = build_projection_plan(args.repository.resolve())
    _print(plan, compact=args.json)
    return 0 if not plan["blocker_codes"] else 2


def _projection_apply(args: argparse.Namespace) -> int:
    result = apply_projection_plan(
        args.repository.resolve(),
        _load_document(args.plan),
        approved_plan_digest=args.approve_plan,
    )
    _print(result, compact=args.json)
    return 0 if result["status"] in {"applied", "unchanged"} else 2


def _impact(args: argparse.Namespace) -> int:
    _print(analyze_workspace_impact(args.repository.resolve()), compact=args.json)
    return 0


def _decision(args: argparse.Namespace) -> int:
    repository = args.repository.resolve()
    state = runtime_state(repository)
    if state["status"] != "active":
        _print(state, compact=args.json)
        return 2
    target = (
        _load_document(args.target_file)
        if args.target_file
        else json.loads(args.target_json)
    )
    if not isinstance(target, dict):
        raise ValueError("decision target must be a JSON object")
    workspace = workspace_state(repository)
    decision = create_task_decision(
        task_id=args.task_id,
        projection_id=state["projection_id"],
        workspace_digest=workspace["workspace_digest"],
        exact_action=args.action,
        target=target,
    )
    try:
        path = save_task_decision(repository, decision)
    except DecisionStateError as exc:
        _print(
            {"status": "blocked", "blocker_codes": exc.blocker_codes},
            compact=args.json,
        )
        return 2
    _print(
        {
            "status": "created",
            "path": path.relative_to(repository).as_posix(),
            "decision": decision,
            "blocker_codes": [],
        },
        compact=args.json,
    )
    return 0


def _decision_end(args: argparse.Namespace) -> int:
    result = end_task_decision(args.repository.resolve(), args.task_id)
    _print(result, compact=args.json)
    return 0 if result["status"] == "expired" else 2


def _policy_plan(args: argparse.Namespace) -> int:
    changes = (
        _load_document(args.changes_file)
        if args.changes_file
        else json.loads(args.changes_json)
    )
    if not isinstance(changes, dict):
        raise ValueError("project policy changes must be a JSON object")
    plan = build_project_policy_plan(
        args.repository.resolve(),
        changes=changes,
    )
    _print(plan, compact=args.json)
    return 0 if not plan["blocker_codes"] else 2


def _policy_apply(args: argparse.Namespace) -> int:
    plan = _load_document(args.plan)
    result = apply_project_policy_plan(
        args.repository.resolve(),
        plan,
        approved_plan_digest=args.approve_plan,
    )
    _print(result, compact=args.json)
    return 0 if result["status"] == "applied" else 2


def _commit_plan(args: argparse.Namespace) -> int:
    repository = args.repository.resolve()
    state = workspace_state(repository)
    plan = build_commit_plan(
        repository,
        commit_scope=args.path,
        message=args.message,
        workspace_impact_scope=(
            state["changed_paths"] if args.analyze_all else args.path
        ),
    )
    _print(plan, compact=args.json)
    return 0 if not plan["blocker_codes"] else 2


def _commit_apply(args: argparse.Namespace) -> int:
    repository = args.repository.resolve()
    plan = _load_document(args.plan)
    decision = load_task_decision(repository, args.task_id)
    result = apply_commit_plan(repository, plan, decision=decision)
    _print(result, compact=args.json)
    return 0 if result["status"] == "committed" else 2


def _issue_plan(args: argparse.Namespace) -> int:
    plan = build_issue_plan(
        args.repository.resolve(),
        title=args.title,
        body=args.body,
        provider=args.provider,
        remote_repository=args.remote_repository,
        labels=args.label,
        assignee=args.assignee,
        local_path=args.local_path,
    )
    _print(plan, compact=args.json)
    return 0


def _issue_apply_local(args: argparse.Namespace) -> int:
    result = apply_local_issue_plan(
        args.repository.resolve(), _load_document(args.plan)
    )
    _print(result, compact=args.json)
    return 0 if result["status"] == "created" else 2


def _issue_prepare_remote(args: argparse.Namespace) -> int:
    repository = args.repository.resolve()
    state = runtime_state(repository)
    if state["status"] != "active":
        _print(state, compact=args.json)
        return 2
    result = prepare_remote_issue_request(
        repository,
        _load_document(args.plan),
        decision=load_task_decision(repository, args.task_id),
        projection_id=state["projection_id"],
    )
    _print(result, compact=args.json)
    return 0 if result["status"] == "provider-required" else 2


def _issue_validate_receipt(args: argparse.Namespace) -> int:
    blockers = validate_remote_issue_receipt(
        _load_document(args.plan), _load_document(args.receipt)
    )
    result = {
        "status": "accepted" if not blockers else "blocked",
        "blocker_codes": blockers,
    }
    _print(result, compact=args.json)
    return 0 if not blockers else 2


def _push_plan(args: argparse.Namespace) -> int:
    plan = build_push_plan(
        args.repository.resolve(),
        remote=args.remote,
        branch=args.branch,
        commit_sha=args.commit,
    )
    _print(plan, compact=args.json)
    return 0 if not plan["blocker_codes"] else 2


def _push_apply(args: argparse.Namespace) -> int:
    repository = args.repository.resolve()
    result = apply_push_plan(
        repository,
        _load_document(args.plan),
        decision=load_task_decision(repository, args.task_id),
    )
    _print(result, compact=args.json)
    return 0 if result["status"] == "pushed" else 2


def _delivery_plan(args: argparse.Namespace) -> int:
    target = (
        _load_document(args.target_file)
        if args.target_file
        else json.loads(args.target_json)
    )
    if not isinstance(target, dict):
        raise ValueError("controlled delivery target must be a JSON object")
    plan = build_controlled_delivery_plan(
        args.repository.resolve(),
        action_id=args.action,
        target=target,
        platform_evidence=_load_document(args.gate_file),
    )
    _print(plan, compact=args.json)
    return 0 if not plan["blocker_codes"] else 2


def _gate_evidence(args: argparse.Namespace) -> int:
    target = _load_document(args.target_file)
    checks_document = _load_document(args.checks_file)
    checks = checks_document.get("checks")
    if not isinstance(checks, list):
        raise ValueError("platform gate checks must be a JSON array")
    evidence = build_platform_gate_evidence(
        action_id=args.action,
        target=target,
        checks=checks,
    )
    _print(evidence, compact=args.json)
    return 0


def _delivery_prepare(args: argparse.Namespace) -> int:
    repository = args.repository.resolve()
    result = prepare_controlled_delivery_request(
        repository,
        _load_document(args.plan),
        decision=load_task_decision(repository, args.task_id),
    )
    _print(result, compact=args.json)
    return 0 if result["status"] == "provider-required" else 2


def _delivery_validate_receipt(args: argparse.Namespace) -> int:
    blockers = validate_controlled_delivery_receipt(
        _load_document(args.plan),
        _load_document(args.receipt),
    )
    result = {
        "status": "accepted" if not blockers else "blocked",
        "blocker_codes": blockers,
    }
    _print(result, compact=args.json)
    return 0 if not blockers else 2


def _hook(args: argparse.Namespace) -> int:
    payload = json.load(sys.stdin)
    repository = Path(payload.get("cwd") or args.repository or ".").resolve()
    output = handle_hook(payload, repository)
    if output:
        print(json.dumps(output, ensure_ascii=False, separators=(",", ":")))
    return 0


def _run_task(args: argparse.Namespace) -> int:
    report = run_local_task_ref(
        args.repository.resolve(),
        args.task_ref,
        scope=args.scope,
    )
    if report["stdout"]:
        print(report["stdout"], end="")
    if report["stderr"]:
        print(report["stderr"], end="", file=sys.stderr)
    _print(
        {
            "status": report["status"],
            "task_ref": report["task_ref"],
            "evidence_digest": report["evidence_digest"],
            "blocker_codes": report["blocker_codes"],
        },
        compact=args.json,
    )
    return 0 if report["status"] == "passed" else 2


def _run_action(args: argparse.Namespace) -> int:
    try:
        report = run_local_action(
            args.repository.resolve(),
            args.action_id,
            validation_level=args.validation_level,
        )
    except ValueError as exc:
        code = str(exc).split(":", 1)[0]
        _print(
            {
                "status": "blocked",
                "action_id": args.action_id,
                "validation_level": args.validation_level,
                "blocker_codes": [code],
                "summary": str(exc),
            },
            compact=args.json,
        )
        return 2
    if report["stdout"]:
        print(report["stdout"], end="")
    if report["stderr"]:
        print(report["stderr"], end="", file=sys.stderr)
    _print(
        {
            "status": report["status"],
            "action_id": args.action_id,
            "validation_level": args.validation_level,
            "cwd": report["cwd"],
            "source_refs": report["source_refs"],
            "returncode": report["returncode"],
            "evidence_digest": report["evidence_digest"],
            "blocker_codes": report["blocker_codes"],
        },
        compact=args.json,
    )
    return 0 if report["status"] == "passed" else 2


def _repository_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("repository", nargs="?", type=Path, default=Path.cwd())


def _json_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="emit compact JSON")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sdd-harness")
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser(
        "init", help="plan or publish the repository Harness control plane"
    )
    _repository_argument(init_parser)
    init_parser.add_argument("--yes", action="store_true")
    init_parser.add_argument("--approve-plan")
    init_parser.add_argument("--with-hooks", action="store_true")
    _json_argument(init_parser)
    init_parser.set_defaults(handler=_init)

    projection_plan_parser = subparsers.add_parser(
        "projection-plan",
        help="plan the second-phase repository governance projection",
    )
    _repository_argument(projection_plan_parser)
    _json_argument(projection_plan_parser)
    projection_plan_parser.set_defaults(handler=_projection_plan)

    projection_apply_parser = subparsers.add_parser(
        "projection-apply",
        help="apply one exact second-phase governance projection plan",
    )
    _repository_argument(projection_apply_parser)
    projection_apply_parser.add_argument("--plan", type=Path, required=True)
    projection_apply_parser.add_argument("--approve-plan", required=True)
    _json_argument(projection_apply_parser)
    projection_apply_parser.set_defaults(handler=_projection_apply)

    inspect_parser = subparsers.add_parser(
        "inspect", help="inspect runtime and projection compatibility"
    )
    _repository_argument(inspect_parser)
    _json_argument(inspect_parser)
    inspect_parser.set_defaults(handler=_inspect)

    impact_parser = subparsers.add_parser(
        "impact", help="analyze the uncommitted workspace without writes"
    )
    _repository_argument(impact_parser)
    _json_argument(impact_parser)
    impact_parser.set_defaults(handler=_impact)

    decision_parser = subparsers.add_parser(
        "decision", help="record one ephemeral exact-action task decision"
    )
    _repository_argument(decision_parser)
    decision_parser.add_argument("--task-id", required=True)
    decision_parser.add_argument("--action", required=True)
    target_group = decision_parser.add_mutually_exclusive_group(required=True)
    target_group.add_argument("--target-json")
    target_group.add_argument("--target-file", type=Path)
    _json_argument(decision_parser)
    decision_parser.set_defaults(handler=_decision)

    decision_end_parser = subparsers.add_parser(
        "decision-end", help="expire one exact ephemeral task decision"
    )
    _repository_argument(decision_end_parser)
    decision_end_parser.add_argument("--task-id", required=True)
    _json_argument(decision_end_parser)
    decision_end_parser.set_defaults(handler=_decision_end)

    policy_plan_parser = subparsers.add_parser(
        "policy-plan", help="plan a versioned project-policy update"
    )
    _repository_argument(policy_plan_parser)
    policy_changes = policy_plan_parser.add_mutually_exclusive_group(
        required=True
    )
    policy_changes.add_argument("--changes-json")
    policy_changes.add_argument("--changes-file", type=Path)
    _json_argument(policy_plan_parser)
    policy_plan_parser.set_defaults(handler=_policy_plan)

    policy_apply_parser = subparsers.add_parser(
        "policy-apply", help="atomically apply an approved project-policy plan"
    )
    _repository_argument(policy_apply_parser)
    policy_apply_parser.add_argument("--plan", type=Path, required=True)
    policy_apply_parser.add_argument("--approve-plan", required=True)
    _json_argument(policy_apply_parser)
    policy_apply_parser.set_defaults(handler=_policy_apply)

    commit_plan_parser = subparsers.add_parser(
        "commit-plan", help="create a selective commit plan without writes"
    )
    _repository_argument(commit_plan_parser)
    commit_plan_parser.add_argument("--path", action="append", required=True)
    commit_plan_parser.add_argument("--message", required=True)
    commit_plan_parser.add_argument("--analyze-all", action="store_true")
    _json_argument(commit_plan_parser)
    commit_plan_parser.set_defaults(handler=_commit_plan)

    commit_apply_parser = subparsers.add_parser(
        "commit-apply", help="apply an exact commit plan"
    )
    _repository_argument(commit_apply_parser)
    commit_apply_parser.add_argument("--plan", type=Path, required=True)
    commit_apply_parser.add_argument("--task-id", required=True)
    _json_argument(commit_apply_parser)
    commit_apply_parser.set_defaults(handler=_commit_apply)

    issue_plan_parser = subparsers.add_parser(
        "issue-plan", help="create a provider-neutral Issue plan"
    )
    _repository_argument(issue_plan_parser)
    issue_plan_parser.add_argument("--title", required=True)
    issue_plan_parser.add_argument("--body", required=True)
    issue_plan_parser.add_argument("--provider", choices=("local", "github"))
    issue_plan_parser.add_argument("--remote-repository")
    issue_plan_parser.add_argument("--local-path")
    issue_plan_parser.add_argument("--label", action="append", default=[])
    issue_plan_parser.add_argument("--assignee")
    _json_argument(issue_plan_parser)
    issue_plan_parser.set_defaults(handler=_issue_plan)

    local_parser = subparsers.add_parser(
        "issue-apply-local", help="write one exact local Issue plan"
    )
    _repository_argument(local_parser)
    local_parser.add_argument("--plan", type=Path, required=True)
    _json_argument(local_parser)
    local_parser.set_defaults(handler=_issue_apply_local)

    remote_parser = subparsers.add_parser(
        "issue-prepare-remote", help="validate an exact remote Issue request"
    )
    _repository_argument(remote_parser)
    remote_parser.add_argument("--plan", type=Path, required=True)
    remote_parser.add_argument("--task-id", required=True)
    _json_argument(remote_parser)
    remote_parser.set_defaults(handler=_issue_prepare_remote)

    receipt_parser = subparsers.add_parser(
        "issue-validate-receipt", help="validate remote provider evidence"
    )
    receipt_parser.add_argument("--plan", type=Path, required=True)
    receipt_parser.add_argument("--receipt", type=Path, required=True)
    _json_argument(receipt_parser)
    receipt_parser.set_defaults(handler=_issue_validate_receipt)

    push_plan_parser = subparsers.add_parser(
        "push-plan", help="create an exact non-force branch push plan"
    )
    _repository_argument(push_plan_parser)
    push_plan_parser.add_argument("--remote", required=True)
    push_plan_parser.add_argument("--branch", required=True)
    push_plan_parser.add_argument("--commit")
    _json_argument(push_plan_parser)
    push_plan_parser.set_defaults(handler=_push_plan)

    push_apply_parser = subparsers.add_parser(
        "push-apply", help="apply an exact decision-bound branch push"
    )
    _repository_argument(push_apply_parser)
    push_apply_parser.add_argument("--plan", type=Path, required=True)
    push_apply_parser.add_argument("--task-id", required=True)
    _json_argument(push_apply_parser)
    push_apply_parser.set_defaults(handler=_push_apply)

    delivery_plan_parser = subparsers.add_parser(
        "delivery-plan",
        help="plan one exact source-backed controlled delivery action",
    )
    _repository_argument(delivery_plan_parser)
    delivery_plan_parser.add_argument("--action", required=True)
    delivery_target = delivery_plan_parser.add_mutually_exclusive_group(
        required=True
    )
    delivery_target.add_argument("--target-json")
    delivery_target.add_argument("--target-file", type=Path)
    delivery_plan_parser.add_argument(
        "--gate-file",
        type=Path,
        required=True,
        help="digest-bound upstream platform-gate evidence",
    )
    _json_argument(delivery_plan_parser)
    delivery_plan_parser.set_defaults(handler=_delivery_plan)

    gate_evidence_parser = subparsers.add_parser(
        "gate-evidence",
        help="bind queried upstream platform checks to one exact target",
    )
    gate_evidence_parser.add_argument("--action", required=True)
    gate_evidence_parser.add_argument(
        "--target-file", type=Path, required=True
    )
    gate_evidence_parser.add_argument(
        "--checks-file", type=Path, required=True
    )
    _json_argument(gate_evidence_parser)
    gate_evidence_parser.set_defaults(handler=_gate_evidence)

    delivery_prepare_parser = subparsers.add_parser(
        "delivery-prepare",
        help="validate a controlled delivery plan before provider execution",
    )
    _repository_argument(delivery_prepare_parser)
    delivery_prepare_parser.add_argument("--plan", type=Path, required=True)
    delivery_prepare_parser.add_argument("--task-id", required=True)
    _json_argument(delivery_prepare_parser)
    delivery_prepare_parser.set_defaults(handler=_delivery_prepare)

    delivery_receipt_parser = subparsers.add_parser(
        "delivery-validate-receipt",
        help="validate exact controlled delivery provider evidence",
    )
    delivery_receipt_parser.add_argument("--plan", type=Path, required=True)
    delivery_receipt_parser.add_argument(
        "--receipt", type=Path, required=True
    )
    _json_argument(delivery_receipt_parser)
    delivery_receipt_parser.set_defaults(handler=_delivery_validate_receipt)

    run_parser = subparsers.add_parser(
        "run-task", help="run one registered routine local task_ref"
    )
    _repository_argument(run_parser)
    run_parser.add_argument("task_ref")
    run_parser.add_argument("--scope", required=True)
    _json_argument(run_parser)
    run_parser.set_defaults(handler=_run_task)

    run_action_parser = subparsers.add_parser(
        "run-action", help="run one source-bound local projection action"
    )
    _repository_argument(run_action_parser)
    run_action_parser.add_argument("action_id")
    run_action_parser.add_argument(
        "--validation-level",
        choices=("T0", "T1", "T2", "T3"),
        required=True,
    )
    _json_argument(run_action_parser)
    run_action_parser.set_defaults(handler=_run_action)

    hook_parser = subparsers.add_parser("hook", help=argparse.SUPPRESS)
    hook_parser.add_argument("--repository", type=Path)
    hook_parser.set_defaults(handler=_hook)

    mcp_parser = subparsers.add_parser("mcp", help=argparse.SUPPRESS)
    mcp_parser.set_defaults(handler=lambda _args: serve())
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        _print(
            {
                "status": "blocked",
                "blocker_codes": ["CONFIG_INVALID"],
                "summary": str(exc),
            }
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
