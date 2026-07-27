from __future__ import annotations

import hashlib
from pathlib import Path
import re

import yaml


ROOT = Path(__file__).parents[2]
EVALS = ROOT / "evals"
RUN = EVALS / "runs" / "p3-forward-eval-20260724.yaml"


def _file_digest(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


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


def test_all_normative_specification_rules_have_automated_coverage() -> None:
    coverage = yaml.safe_load((EVALS / "coverage.yaml").read_text("utf-8"))
    specification = (ROOT / "docs" / "specification.md").read_text("utf-8")
    expected = set(re.findall(r"\*\*((?:GG|AG|GE|CF)-\d{3})\*\*", specification))

    assert set(coverage["specification_rules"]) == expected
    for rule_id, test_paths in coverage["specification_rules"].items():
        assert test_paths, rule_id
        for test_path in test_paths:
            assert (ROOT / test_path).is_file(), (rule_id, test_path)


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


def test_recorded_forward_eval_run_covers_manifest_and_passes() -> None:
    manifest = yaml.safe_load((EVALS / "manifest.yaml").read_text("utf-8"))
    run = yaml.safe_load(RUN.read_text("utf-8"))

    expected_cases = {item["id"] for item in manifest["cases"]}
    recorded_cases = {item["id"] for item in run["cases"]}

    assert recorded_cases == expected_cases
    assert run["isolation"] == {
        "independent_agent_per_case": True,
        "fresh_context": True,
        "evaluator_only_sections_withheld": True,
    }
    assert run["skill"]["digest"].startswith("sha256:")
    assert run["summary"]["total_cases"] == 7
    assert run["summary"]["passed_cases"] == 7
    assert run["summary"]["failed_cases"] == 0
    assert run["summary"]["mandatory_failures"] == 0
    assert run["summary"]["minimum_score"] >= run["rubric"]["passing_score"]
    assert run["summary"]["status"] == "passed"
    assert run["does_not_advance"] == [
        "P4 real GitHub platform acceptance",
        "P5 installation or release",
    ]
    result_root = ROOT / run["results_root"]
    case_paths = {
        item["id"]: EVALS / item["path"] for item in manifest["cases"]
    }
    for case in run["cases"]:
        assert case["passed"] is True
        assert case["score"] >= run["rubric"]["passing_score"]
        assert case["mandatory_failures"] == []
        assert case["case_digest"] == _file_digest(case_paths[case["id"]])
        assert case["fixture_digest"].startswith("sha256:")
        assert set(case["artifact_digests"]) == {
            "raw-output.md",
            "workspace.diff",
            "evidence.yaml",
            "score.yaml",
        }
        assert all(
            digest.startswith("sha256:")
            for digest in case["artifact_digests"].values()
        )
        artifact_dir = result_root / case["artifact_path"]
        if artifact_dir.is_dir():
            for name, expected_digest in case["artifact_digests"].items():
                assert _file_digest(artifact_dir / name) == expected_digest
