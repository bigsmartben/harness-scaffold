from __future__ import annotations

import copy
import json
from itertools import product
from pathlib import Path

from harness_core.artifacts import attach_digest
from harness_core.codex_adapter import load_projection_bundle
from harness_core.contracts import (
    AUDIENCES,
    DOMAINS,
    RESPONSIBILITIES,
    blocker_codes,
    validate_governance_bundle,
    validate_runtime_artifact,
)
from harness_core.initializer import (
    apply_initialization_plan,
    apply_projection_plan,
    build_initialization_plan,
    build_projection_plan,
)
from harness_core.projection import COVERAGE_STATUSES
from harness_core.snapshot import governance_relevant_paths


def _initialized_bundle(tmp_path: Path) -> dict:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname='fixture'\nversion='0.1.0'\n",
        encoding="utf-8",
    )
    plan = build_initialization_plan(tmp_path)
    assert plan["blocker_codes"] == []
    assert apply_initialization_plan(
        tmp_path, plan, approved_plan_digest=plan["plan_digest"]
    )["status"] == "applied"
    projection_plan = build_projection_plan(tmp_path)
    assert projection_plan["blocker_codes"] == []
    assert apply_projection_plan(
        tmp_path,
        projection_plan,
        approved_plan_digest=projection_plan["plan_digest"],
    )["status"] == "applied"
    bundle = load_projection_bundle(tmp_path)
    assert bundle is not None
    return bundle


def test_four_domain_projection_has_exactly_sixteen_records(
    tmp_path: Path,
) -> None:
    bundle = _initialized_bundle(tmp_path)
    cells = bundle["rules"]["cells"]
    expected = {
        f"{audience}.{responsibility}.{domain}"
        for audience, responsibility, domain in product(
            AUDIENCES, RESPONSIBILITIES, DOMAINS
        )
    }
    assert len(cells) == 16
    assert {cell["cell_id"] for cell in cells} == expected
    assert all(
        cell["coverage_status"] in COVERAGE_STATUSES for cell in cells
    )
    assert validate_governance_bundle(bundle) == []


def test_duplicate_and_unsourced_not_applicable_fail_closed(
    tmp_path: Path,
) -> None:
    duplicate = copy.deepcopy(_initialized_bundle(tmp_path))
    duplicate["rules"]["cells"][1]["cell_id"] = (
        duplicate["rules"]["cells"][0]["cell_id"]
    )
    duplicate["rules"] = attach_digest(duplicate["rules"], "rules_digest")
    duplicate["projection_lock"]["rules_digest"] = duplicate["rules"][
        "rules_digest"
    ]
    duplicate["projection_lock"] = attach_digest(
        duplicate["projection_lock"], "projection_lock_digest"
    )
    assert "GOVERNANCE_COVERAGE_INCOMPLETE" in {
        issue.code for issue in validate_governance_bundle(duplicate)
    }

    not_applicable = copy.deepcopy(_initialized_bundle(tmp_path / "other"))
    cell = not_applicable["rules"]["cells"][0]
    cell["coverage_status"] = "not_applicable"
    cell["source_refs"] = []
    cell["not_applicable_reason"] = None
    not_applicable["rules"] = attach_digest(
        not_applicable["rules"], "rules_digest"
    )
    not_applicable["projection_lock"]["rules_digest"] = not_applicable[
        "rules"
    ]["rules_digest"]
    not_applicable["projection_lock"] = attach_digest(
        not_applicable["projection_lock"], "projection_lock_digest"
    )
    assert "GOVERNANCE_COVERAGE_INCOMPLETE" in {
        issue.code for issue in validate_governance_bundle(not_applicable)
    }


def test_runtime_schema_and_blockers_use_explicit_2_0_contract(
    tmp_path: Path,
) -> None:
    bundle = _initialized_bundle(tmp_path)
    impact = {
        "artifact_type": "impact-analysis",
        "schema_version": "2.0.0",
        "base_commit": "unborn",
        "workspace_digest": bundle["sources"]["snapshot_digest"],
        "changed_paths": [],
        "domains": [],
        "validation_level": "T0",
        "reasons": [],
    }
    impact = attach_digest(impact, "impact_digest")
    assert validate_runtime_artifact(impact) == []
    assert {
        "missing",
        "documented",
        "verified",
        "enforced",
        "not_applicable",
    } == set(COVERAGE_STATUSES)
    assert "GOVERNANCE_PRECONDITION_FAILED" in blocker_codes()


def test_snapshot_ignores_nested_acceptance_and_temporary_fixtures(
    tmp_path: Path,
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname='root'\nversion='0.1.0'\n",
        encoding="utf-8",
    )
    (tmp_path / ".tmp").mkdir()
    (tmp_path / ".tmp" / "package.json").write_text("{}\n", encoding="utf-8")
    fixture = tmp_path / "tests" / "fixtures" / "nested"
    fixture.mkdir(parents=True)
    (fixture / "package.json").write_text("{}\n", encoding="utf-8")
    assert governance_relevant_paths(tmp_path) == ("pyproject.toml",)
    assert json.loads(
        (
            Path(__file__).parents[2]
            / "src/harness_core/resources/schemas/common.schema.json"
        ).read_text(encoding="utf-8")
    )["x-harness-schema-version"] == "2.0.0"
