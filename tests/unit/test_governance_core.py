from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
import harness_core.initializer as initializer_module

from harness_core import (
    SUBDOMAINS,
    attach_digest,
    apply_initialization_plan,
    build_action_graph,
    build_initialization_plan,
    compile_governance_projection,
    create_action_request,
    create_confirmation_package,
    create_governance_work_grant,
    create_repository_snapshot,
    evaluate_gates,
    extract_source_facts,
    run_governed_action,
    validate_governance_artifact,
    validate_governance_bundle,
    validate_postconditions,
)
from harness_core.discovery import discover_repository


def _python_repository(tmp_path: Path) -> Path:
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "fixture"
version = "0.1.0"
dependencies = ["pytest>=8"]

[tool.ai-coding-harness.tasks]
test = ["python", "-m", "pytest"]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "tests").mkdir()
    return tmp_path


def _projection(repository: Path) -> tuple[dict, dict, dict, dict]:
    snapshot = create_repository_snapshot(repository)
    facts = extract_source_facts(discover_repository(repository), snapshot)
    graph = build_action_graph(facts)
    bundle = compile_governance_projection(snapshot, facts, graph)
    return snapshot, facts, graph, bundle


def test_snapshot_is_stable_and_ignores_runtime_reports(tmp_path: Path) -> None:
    repository = _python_repository(tmp_path)
    first = create_repository_snapshot(repository)
    report = repository / ".harness" / "reports" / "result.json"
    report.parent.mkdir(parents=True)
    report.write_text('{"status":"passed"}', encoding="utf-8")
    second = create_repository_snapshot(repository)

    assert second == first

    (repository / "pyproject.toml").write_text(
        (repository / "pyproject.toml").read_text(encoding="utf-8") + "\n# changed\n",
        encoding="utf-8",
    )
    assert create_repository_snapshot(repository)["snapshot_digest"] != first["snapshot_digest"]


def test_projection_is_deterministic_and_covers_two_by_six_matrix(
    tmp_path: Path,
) -> None:
    repository = _python_repository(tmp_path)
    snapshot, facts, graph, first = _projection(repository)
    second = compile_governance_projection(snapshot, facts, graph)

    assert len(SUBDOMAINS) == 6
    assert len(first["rules"]["matrix"]) == 12
    inherited = [
        rule for rule in first["rules"]["rules"] if rule["action_id"] is None
    ]
    assert len(inherited) == 12
    assert {
        (rule["audience"], rule["subdomains"][0]) for rule in inherited
    } == {
        (audience, subdomain)
        for audience in ("maintainer", "consumer")
        for subdomain in SUBDOMAINS
    }
    assert len(
        [
            fact
            for fact in facts["facts"]
            if fact["value"].get("kind") == "subdomain-specification"
        ]
    ) == 6
    assert first == second
    assert not validate_governance_bundle(first)
    assert first["projection_lock"]["ready"] is True


def test_governance_schema_rejects_unknown_enum_and_digest_tampering(
    tmp_path: Path,
) -> None:
    repository = _python_repository(tmp_path)
    _, _, _, bundle = _projection(repository)
    rule = deepcopy(bundle["rules"])
    rule["rules"][0]["audience"] = "administrator"
    assert any(issue.code == "SCHEMA_INVALID" for issue in validate_governance_artifact(rule))

    tampered = deepcopy(bundle["projection_lock"])
    tampered["ready"] = False
    assert any(issue.code == "DIGEST_INVALID" for issue in validate_governance_artifact(tampered))


def test_agent_exchange_candidate_and_reconciliation_artifacts_are_schema_bound(
    tmp_path: Path,
) -> None:
    repository = _python_repository(tmp_path)
    _, _, _, bundle = _projection(repository)
    projection_id = bundle["projection_lock"]["projection_id"]
    rule = next(
        item for item in bundle["rules"]["rules"] if item["action_id"] is None
    )
    artifacts = []
    agent_input = attach_digest(
        {
            "artifact_type": "agent-input",
            "schema_version": "1.0.0",
            "role": "governance_projector",
            "projection_id": projection_id,
            "audience": rule["audience"],
            "subdomain": rule["subdomains"][0],
            "payload": {"facts_digest": bundle["sources"]["facts_digest"]},
        },
        "input_digest",
    )
    artifacts.append(agent_input)
    agent_output = attach_digest(
        {
            "artifact_type": "agent-output",
            "schema_version": "1.0.0",
            "role": "governance_projector",
            "projection_id": projection_id,
            "status": "completed",
            "result": {"rule_ids": [rule["rule_id"]]},
            "blocker_codes": [],
        },
        "output_digest",
    )
    artifacts.append(agent_output)
    candidate = attach_digest(
        {
            "artifact_type": "rule-candidate",
            "schema_version": "1.0.0",
            "projection_id": projection_id,
            "audience": rule["audience"],
            "subdomain": rule["subdomains"][0],
            "rules": [rule],
            "blocker_codes": [],
        },
        "candidate_digest",
    )
    artifacts.append(candidate)
    reconciliation = attach_digest(
        {
            "artifact_type": "reconciliation-result",
            "schema_version": "1.0.0",
            "projection_id": projection_id,
            "candidate_digests": [candidate["candidate_digest"]],
            "rules": [rule],
            "conflicts": [],
            "blocker_codes": [],
        },
        "result_digest",
    )
    artifacts.append(reconciliation)

    assert all(not validate_governance_artifact(item) for item in artifacts)


def test_gates_return_all_blockers_and_routine_requests_need_no_confirmation(
    tmp_path: Path,
) -> None:
    repository = _python_repository(tmp_path)
    snapshot, _, graph, bundle = _projection(repository)
    lock = bundle["projection_lock"]
    action = graph["actions"][0]
    grant = create_governance_work_grant(
        lock["projection_id"], "run contract checks", ["."]
    )
    request = create_action_request(
        lock["projection_id"], grant, action["action_id"], scope=["tests"]
    )
    decision = evaluate_gates(
        projection_lock=lock,
        action_graph=graph,
        rules=bundle["rules"],
        grant=grant,
        request=request,
        current_snapshot_digest=snapshot["snapshot_digest"],
    )

    assert decision["status"] == "pending"
    assert decision["confirmation_required"] is False
    assert not decision["blocker_codes"]
    assert [gate["gate_id"] for gate in decision["gates"]] == [
        "G0",
        "G1",
        "G2",
        "G3",
        "G4",
        "G5",
        "G6",
        "G7",
    ]

    bypass = evaluate_gates(
        projection_lock=lock,
        action_graph=graph,
        rules=bundle["rules"],
        grant=grant,
        request=request,
        current_snapshot_digest="sha256:" + ("0" * 64),
        invocation_channel="shell",
    )
    assert "GOVERNANCE_PROJECTION_STALE" in bypass["blocker_codes"]
    assert "INVOCATION_BYPASS_ATTEMPT" in bypass["blocker_codes"]
    assert "HANDOFF_REQUIRED" in bypass["blocker_codes"]


def test_every_gate_has_a_stable_blocking_branch(tmp_path: Path) -> None:
    repository = _python_repository(tmp_path)
    snapshot, _, graph, bundle = _projection(repository)
    lock = bundle["projection_lock"]
    action = graph["actions"][0]
    grant = create_governance_work_grant(
        lock["projection_id"], "exercise every gate", ["tests"]
    )
    request = create_action_request(
        lock["projection_id"], grant, action["action_id"], scope=["tests"]
    )
    cases = {}

    stale_lock = deepcopy(lock)
    stale_lock["ready"] = False
    cases["G0"] = {"projection_lock": stale_lock}

    no_sources = deepcopy(bundle["rules"])
    action_rule = next(
        rule
        for rule in no_sources["rules"]
        if rule["action_id"] == action["action_id"]
        and rule["audience"] == request["audience"]
    )
    action_rule["source_refs"] = []
    cases["G1"] = {"rules": no_sources}

    incomplete_graph = deepcopy(graph)
    incomplete_graph["blockers"] = [{"code": "TOOL_ACTION_UNCLASSIFIED"}]
    cases["G2"] = {"action_graph": incomplete_graph}

    ambiguous_graph = deepcopy(graph)
    ambiguous_graph["actions"][0]["invocation"] = {}
    cases["G3"] = {"action_graph": ambiguous_graph}

    expanded_request = create_action_request(
        lock["projection_id"], grant, action["action_id"], scope=["src"]
    )
    cases["G4"] = {"request": expanded_request}
    cases["G5"] = {"invocation_channel": "shell"}
    cases["G6"] = {
        "postcondition_result": {
            "status": "blocked",
            "blocker_codes": ["GOVERNANCE_EVIDENCE_INCOMPLETE"],
        }
    }
    cases["G7"] = {
        "postcondition_result": {"status": "passed", "blocker_codes": []},
        "final_snapshot_digest": "sha256:" + "0" * 64,
    }
    expected = {
        "G0": "GOVERNANCE_PROJECTION_STALE",
        "G1": "GOVERNANCE_SOURCE_MISSING",
        "G2": "GOVERNANCE_COVERAGE_INCOMPLETE",
        "G3": "TOOL_BINDING_AMBIGUOUS",
        "G4": "GOVERNANCE_PRECONDITION_FAILED",
        "G5": "INVOCATION_BYPASS_ATTEMPT",
        "G6": "GOVERNANCE_EVIDENCE_INCOMPLETE",
        "G7": "GOVERNANCE_DRIFT_DETECTED",
    }

    for gate_id, overrides in cases.items():
        arguments = {
            "projection_lock": lock,
            "action_graph": graph,
            "rules": bundle["rules"],
            "grant": grant,
            "request": request,
            "current_snapshot_digest": snapshot["snapshot_digest"],
        }
        arguments.update(overrides)
        decision = evaluate_gates(**arguments)
        gate = next(item for item in decision["gates"] if item["gate_id"] == gate_id)
        assert gate["status"] == "blocked", gate_id
        assert expected[gate_id] in gate["blocker_codes"], gate_id


def test_action_request_rejects_binding_override_and_confirmation_is_aggregated(
    tmp_path: Path,
) -> None:
    repository = _python_repository(tmp_path)
    _, _, graph, bundle = _projection(repository)
    lock = bundle["projection_lock"]
    grant = create_governance_work_grant(lock["projection_id"], "change", ["src"])

    with pytest.raises(ValueError):
        create_action_request(
            lock["projection_id"],
            grant,
            graph["actions"][0]["action_id"],
            parameters={"command": "rm -rf ."},
        )
    tampered_grant = deepcopy(grant)
    tampered_grant["objective"] = "expanded without a new digest"
    with pytest.raises(ValueError):
        create_action_request(
            lock["projection_id"],
            tampered_grant,
            graph["actions"][0]["action_id"],
        )

    package = create_confirmation_package(
        lock["projection_id"],
        ["sha256:" + ("1" * 64), "sha256:" + ("2" * 64)],
        kind="change-set",
        scope=["src", "tests"],
        decision="approved",
    )
    assert len(package["request_digests"]) == 2
    assert package["kind"] == "change-set"


def test_test_exit_zero_without_parseable_report_is_not_accepted(
    tmp_path: Path,
) -> None:
    result = validate_postconditions(
        repository=tmp_path,
        semantics="test",
        exit_code=0,
    )
    assert result["status"] == "blocked"
    assert result["blocker_codes"] == ["GOVERNANCE_EVIDENCE_INCOMPLETE"]

    report = tmp_path / "report.json"
    report.write_text(json.dumps({"status": "passed"}), encoding="utf-8")
    accepted = validate_postconditions(
        repository=tmp_path,
        semantics="test",
        exit_code=0,
        required_reports=["report.json"],
    )
    assert accepted["status"] == "passed"


def test_real_minimal_test_action_runs_through_gates_and_evidence(
    tmp_path: Path,
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "runner-fixture"
version = "0.1.0"

[tool.ai-coding-harness.tasks.test]
argv = ["python", "-c", "from pathlib import Path; Path('.harness/reports').mkdir(parents=True, exist_ok=True); Path('.harness/reports/test.json').write_text('{\\"status\\":\\"passed\\"}')"]
required_reports = [".harness/reports/test.json"]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    snapshot, _, graph, bundle = _projection(tmp_path)
    lock = bundle["projection_lock"]
    action = graph["actions"][0]
    grant = create_governance_work_grant(
        lock["projection_id"], "run a source-backed test", ["."]
    )
    request = create_action_request(
        lock["projection_id"], grant, action["action_id"], scope=["."]
    )

    evidence = run_governed_action(
        repository=tmp_path,
        projection_lock=lock,
        action_graph=graph,
        rules=bundle["rules"],
        grant=grant,
        request=request,
    )

    assert snapshot["snapshot_digest"] == create_repository_snapshot(tmp_path)[
        "snapshot_digest"
    ]
    assert evidence["status"] == "passed"
    assert evidence["postconditions"]["status"] == "passed"
    assert evidence["blocker_codes"] == []
    assert evidence["evidence_digest"].startswith("sha256:")


def test_initialization_is_plan_bound_idempotent_and_preserves_agents_content(
    tmp_path: Path,
) -> None:
    repository = _python_repository(tmp_path)
    (repository / "AGENTS.md").write_text("# Team rules\n\nKeep this.\n", encoding="utf-8")
    before = {
        path.relative_to(repository).as_posix()
        for path in repository.rglob("*")
        if path.is_file()
    }
    plan = build_initialization_plan(repository)

    after_plan = {
        path.relative_to(repository).as_posix()
        for path in repository.rglob("*")
        if path.is_file()
    }
    assert before == after_plan
    assert not plan["blocker_codes"]

    applied = apply_initialization_plan(repository, plan)
    assert applied["status"] == "applied"
    agents = (repository / "AGENTS.md").read_text(encoding="utf-8")
    assert "# Team rules" in agents
    assert "Keep this." in agents
    assert "<!-- ai-coding-harness:start -->" in agents

    second = build_initialization_plan(repository)
    assert second["projection_id"] == plan["projection_id"]
    reapplied = apply_initialization_plan(repository, second)
    assert reapplied["status"] == "applied"
    assert reapplied["changed_paths"] == []


def test_initialization_rolls_back_files_and_temporary_paths_on_write_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _python_repository(tmp_path)
    config = repository / ".codex" / "config.toml"
    config.parent.mkdir(parents=True)
    config.write_text("[user]\nkeep = true\n", encoding="utf-8")
    before = {
        path.relative_to(repository).as_posix(): path.read_bytes()
        for path in repository.rglob("*")
        if path.is_file()
    }
    plan = build_initialization_plan(repository)
    real_replace = initializer_module.os.replace

    def fail_on_hooks(source: Path, target: Path) -> None:
        if Path(target).name == "hooks.json":
            raise OSError("simulated atomic replacement failure")
        real_replace(source, target)

    monkeypatch.setattr(initializer_module.os, "replace", fail_on_hooks)
    result = apply_initialization_plan(repository, plan)
    after = {
        path.relative_to(repository).as_posix(): path.read_bytes()
        for path in repository.rglob("*")
        if path.is_file()
    }

    assert result["status"] == "blocked"
    assert before == after
