from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).parents[2]
EVALS = ROOT / "evals"


def test_forward_eval_manifest_has_all_planned_cases() -> None:
    manifest = yaml.safe_load((EVALS / "manifest.yaml").read_text("utf-8"))
    cases = {case["id"]: case for case in manifest["cases"]}

    assert set(cases) == {
        "bootstrap-empty-project",
        "adopt-existing-ci",
        "avoid-unnecessary-full-ci",
        "registry-is-not-authorization",
        "routine-test-auto-execution",
        "expensive-ci-requires-confirmation",
        "unconfirmed-critical-delivery",
    }
    assert manifest["isolation"]["independent_agent"] == "required"
    assert manifest["isolation"]["fresh_context"] == "required"
    for case in cases.values():
        assert (EVALS / case["path"]).is_file()


def test_agent_inputs_are_separated_from_evaluator_conclusions() -> None:
    manifest = yaml.safe_load((EVALS / "manifest.yaml").read_text("utf-8"))
    for item in manifest["cases"]:
        content = (EVALS / item["path"]).read_text("utf-8")
        visible = content.index("## Agent-visible input")
        hidden = content.index("## Evaluator-only rubric")
        expected = content.index("## Expected evidence")

        assert visible < hidden < expected
        agent_input = content[visible:hidden]
        assert "Expected evidence" not in agent_input
        assert "Mandatory failure" not in agent_input


def test_all_user_cases_have_automated_test_or_eval_coverage() -> None:
    coverage = yaml.safe_load((EVALS / "coverage.yaml").read_text("utf-8"))
    expected = {f"UC-{index:03d}" for index in range(1, 13)}

    assert set(coverage["use_cases"]) == expected
    for use_case, evidence in coverage["use_cases"].items():
        assert evidence.get("tests") or evidence.get("evals"), use_case
        for test_path in evidence.get("tests", []):
            assert (ROOT / test_path).is_file(), (use_case, test_path)


def test_eval_result_contract_retains_required_raw_artifacts() -> None:
    manifest = yaml.safe_load((EVALS / "manifest.yaml").read_text("utf-8"))

    assert set(manifest["artifacts"]["required"]) == {
        "raw-output.md",
        "workspace.diff",
        "evidence.yaml",
        "score.yaml",
    }
    ignored = [
        line
        for line in (EVALS / "results" / ".gitignore").read_text("utf-8").splitlines()
        if line
    ]
    assert ignored == ["*", "!.gitignore"]
