from __future__ import annotations

import copy
import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

import harness_core
from harness_core.artifacts import canonical_digest


ROOT = Path(__file__).parents[2]


def file_snapshot(repository: Path) -> dict[str, bytes]:
    return {
        path.relative_to(repository).as_posix(): path.read_bytes()
        for path in repository.rglob("*")
        if path.is_file()
    }


def test_load_request_schema_and_core_do_not_require_repository_skill(
    tmp_path: Path,
) -> None:
    schema = json.loads(
        (
            ROOT
            / "src/harness_core/resources/schemas/load.schema.json"
        ).read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)
    request = harness_core.build_load_request(tmp_path)
    assert not list(Draft202012Validator(schema).iter_errors(request))
    assert not (tmp_path / ".agents/skills/harness/SKILL.md").exists()

    result = harness_core.load_repository(request)

    assert result["status"] == "ready"
    assert not (tmp_path / ".agents/skills/harness/SKILL.md").exists()
    result_schema = json.loads(
        (
            ROOT
            / "src/harness_core/resources/schemas/load-result.schema.json"
        ).read_text(encoding="utf-8")
    )
    validator = Draft202012Validator(result_schema)
    assert not list(validator.iter_errors(result))
    for blocked in (
        harness_core.load_repository({}),
        harness_core.load_repository(
            {
                "contract_version": "3.0.1",
                "repository": str(tmp_path),
            }
        ),
        harness_core.load_repository(
            harness_core.build_load_request(tmp_path / "missing")
        ),
    ):
        assert blocked["status"] == "blocked"
        assert not list(validator.iter_errors(blocked))


def test_blank_repository_gets_four_absence_backed_domain_candidates(
    tmp_path: Path,
) -> None:
    before = file_snapshot(tmp_path)
    result = harness_core.load_repository(
        harness_core.build_load_request(tmp_path)
    )

    assert result["status"] == "ready"
    assert [fact["kind"] for fact in result["facts"]] == ["absent"] * 4
    assert [candidate["domain"] for candidate in result["candidates"]] == [
        "specification",
        "implementation",
        "verification",
        "delivery",
    ]
    assert all(
        candidate["sources"][0]["reference"].startswith("snapshot:")
        for candidate in result["candidates"]
    )
    assert file_snapshot(tmp_path) == before


def test_app_and_cli_load_adapters_reach_the_same_core_result(
    tmp_path: Path,
) -> None:
    context = {
        "repository": str(tmp_path),
        "repository_digest": "sha256:" + ("9" * 64),
        "rules": [],
        "pending_operations": [],
    }
    app = harness_core.adapt_app_intent("$harness load", context)
    cli = harness_core.adapt_cli_intent("$harness load", context)

    assert app == cli
    assert harness_core.load_repository(
        app["envelope"]["request"]
    ) == harness_core.load_repository(cli["envelope"]["request"])


def test_typical_repository_rules_trace_to_discovered_surfaces(
    tmp_path: Path,
) -> None:
    (tmp_path / "README.md").write_text("# API\n", encoding="utf-8")
    source = tmp_path / "src" / "api.py"
    source.parent.mkdir()
    source.write_text("def get(): return 1\n", encoding="utf-8")
    test = tmp_path / "tests" / "test_api.py"
    test.parent.mkdir()
    test.write_text("def test_get(): assert True\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname='demo'\nversion='1.0.0'\n",
        encoding="utf-8",
    )

    result = harness_core.load_repository(
        harness_core.build_load_request(tmp_path)
    )
    candidates = {
        item["domain"]: item
        for item in result["candidates"]
        if item["rule_id"].startswith("repo-")
    }

    assert result["status"] == "ready"
    assert candidates["specification"]["scope"] == ["README.md"]
    assert candidates["implementation"]["scope"] == ["src/api.py"]
    assert candidates["verification"]["scope"] == ["tests/test_api.py"]
    assert candidates["delivery"]["scope"] == ["pyproject.toml"]


def test_existing_v3_governance_is_read_and_preserved_with_source(
    tmp_path: Path,
) -> None:
    harness = tmp_path / ".harness" / "harness.yaml"
    harness.parent.mkdir()
    harness.write_text(
        yaml.safe_dump(
            {
                "schema_version": "3.0.1",
                "rule_instances": {
                    "specification": [],
                    "implementation": [],
                    "verification": [
                        {
                            "rule_id": "contract-tests",
                            "directive": "Run contract tests.",
                            "scope": ["tests/**"],
                        }
                    ],
                    "delivery": [],
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    result = harness_core.load_repository(
        harness_core.build_load_request(tmp_path)
    )
    rule = next(
        item
        for item in result["candidates"]
        if item["rule_id"] == "contract-tests"
    )

    assert result["status"] == "ready"
    assert rule["domain"] == "verification"
    assert rule["directive"] == "Run contract tests."
    assert rule["sources"][0]["source_type"] == "governance_source"
    assert rule["sources"][0]["reference"].startswith(
        ".harness/harness.yaml#"
    )


def test_recognizable_legacy_rules_are_read_instead_of_rejected_by_version(
    tmp_path: Path,
) -> None:
    harness = tmp_path / ".harness" / "harness.yaml"
    harness.parent.mkdir()
    harness.write_text(
        yaml.safe_dump(
            {
                "schema_version": "2.0.0",
                "rule_instances": {
                    "specification": [
                        {
                            "rule_id": "acceptance-first",
                            "directive": "Define acceptance first.",
                            "scope": ["docs/**"],
                        }
                    ],
                    "implementation": [],
                    "verification": [],
                    "delivery": [],
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    result = harness_core.load_repository(
        harness_core.build_load_request(tmp_path)
    )

    assert result["status"] == "ready"
    assert any(
        item["rule_id"] == "acceptance-first"
        for item in result["candidates"]
    )
    assert not any(
        item["code"] == "CONTRACT_VERSION_UNSUPPORTED"
        for item in result["diagnostics"]
    )


def test_conflicting_existing_rule_blocks_without_writes(tmp_path: Path) -> None:
    harness = tmp_path / ".harness" / "harness.yaml"
    harness.parent.mkdir()
    harness.write_text(
        yaml.safe_dump(
            {
                "schema_version": "3.0.1",
                "rule_instances": {
                    "specification": [
                        {
                            "rule_id": "repo-specification-baseline",
                            "directive": "Conflicting specification.",
                            "scope": ["other/**"],
                        }
                    ],
                    "implementation": [],
                    "verification": [],
                    "delivery": [],
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    before = file_snapshot(tmp_path)

    result = harness_core.load_repository(
        harness_core.build_load_request(tmp_path)
    )

    assert result["status"] == "blocked"
    assert result["diagnostics"][0]["code"] == "RULE_CANDIDATE_CONFLICT"
    assert file_snapshot(tmp_path) == before


def test_unclassifiable_existing_governance_blocks_without_guessing(
    tmp_path: Path,
) -> None:
    (tmp_path / "AGENTS.md").write_text(
        "- Always be thoughtful.\n",
        encoding="utf-8",
    )
    before = file_snapshot(tmp_path)

    result = harness_core.load_repository(
        harness_core.build_load_request(tmp_path)
    )

    assert result["status"] == "blocked"
    assert result["diagnostics"][0]["code"] == (
        "GOVERNANCE_SOURCE_UNCLASSIFIED"
    )
    assert result["diagnostics"][0]["source"] == "AGENTS.md#L1"
    assert file_snapshot(tmp_path) == before


def test_malformed_existing_rule_returns_diagnostic_instead_of_crashing(
    tmp_path: Path,
) -> None:
    harness = tmp_path / ".harness/harness.yaml"
    harness.parent.mkdir()
    harness.write_text(
        yaml.safe_dump(
            {
                "schema_version": "3.0.1",
                "rule_instances": {
                    **{domain: [] for domain in harness_core.DOMAINS},
                    "verification": [
                        {
                            "rule_id": "broken-rule",
                            "directive": "Run tests.",
                            "scope": "tests/**",
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    result = harness_core.load_repository(
        harness_core.build_load_request(tmp_path)
    )

    assert result["status"] == "blocked"
    assert result["diagnostics"][0]["code"] == "GOVERNANCE_SOURCE_INVALID"


def test_same_snapshot_is_deterministic_and_fact_change_invalidates_result(
    tmp_path: Path,
) -> None:
    source = tmp_path / "src" / "main.py"
    source.parent.mkdir()
    source.write_text("VALUE = 1\n", encoding="utf-8")
    request = harness_core.build_load_request(tmp_path)

    first = harness_core.load_repository(request)
    second = harness_core.load_repository(copy.deepcopy(request))
    source.write_text("VALUE = 2\n", encoding="utf-8")
    changed = harness_core.load_repository(request)

    assert first == second
    assert first["snapshot_digest"] != changed["snapshot_digest"]
    assert first["result_digest"] != changed["result_digest"]
    assert canonical_digest(first["candidates"]) != canonical_digest(
        changed["candidates"]
    )


def test_governance_sources_are_reported_in_explicit_priority_order(
    tmp_path: Path,
) -> None:
    (tmp_path / "AGENTS.md").write_text(
        "- Run tests for verification evidence.\n",
        encoding="utf-8",
    )
    harness = tmp_path / ".harness" / "harness.yaml"
    harness.parent.mkdir()
    harness.write_text(
        yaml.safe_dump(
            {
                "schema_version": "3.0.1",
                "rule_instances": {domain: [] for domain in harness_core.DOMAINS},
            }
        ),
        encoding="utf-8",
    )
    repository = harness_core.GovernanceRepository(tmp_path)
    repository.ingest(
        harness_core.load_repository(harness_core.build_load_request(tmp_path))
    )

    result = harness_core.load_repository(
        harness_core.build_load_request(tmp_path)
    )

    assert [
        (source["path"], source["priority"])
        for source in result["governance_sources"]
    ] == [
        (".harness/governance/state.json", 400),
        (".harness/harness.yaml", 300),
        ("AGENTS.md", 250),
    ]


def test_exact_duplicate_rule_merges_sources_deterministically(
    tmp_path: Path,
) -> None:
    harness = tmp_path / ".harness" / "harness.yaml"
    harness.parent.mkdir()
    rule = {
        "rule_id": "contract-tests",
        "directive": "Run contract tests.",
        "scope": ["tests/**"],
    }
    harness.write_text(
        yaml.safe_dump(
            {
                "schema_version": "3.0.1",
                "rule_instances": {
                    **{domain: [] for domain in harness_core.DOMAINS},
                    "verification": [rule],
                },
            }
        ),
        encoding="utf-8",
    )
    first = harness_core.load_repository(harness_core.build_load_request(tmp_path))
    harness_core.GovernanceRepository(tmp_path).ingest(first)

    reloaded = harness_core.load_repository(
        harness_core.build_load_request(tmp_path)
    )
    merged = next(
        candidate
        for candidate in reloaded["candidates"]
        if candidate["rule_id"] == "contract-tests"
    )

    assert reloaded["status"] == "ready"
    assert len(merged["sources"]) == 1
    assert merged["sources"][0]["reference"].startswith(
        ".harness/harness.yaml#"
    )


def test_current_v4_state_reloads_and_fact_baselines_are_refreshed(
    tmp_path: Path,
) -> None:
    source = tmp_path / "src" / "main.py"
    source.parent.mkdir()
    source.write_text("VALUE = 1\n", encoding="utf-8")
    repository = harness_core.GovernanceRepository(tmp_path)
    first = harness_core.load_repository(harness_core.build_load_request(tmp_path))
    repository.ingest(first)
    source.write_text("VALUE = 2\n", encoding="utf-8")

    reloaded = harness_core.load_repository(
        harness_core.build_load_request(tmp_path)
    )

    assert reloaded["status"] == "ready"
    assert {
        calibration["rule_id"]
        for calibration in reloaded["calibrations"]
    } == {
        "repo-implementation-baseline",
    }
    assert not reloaded["diagnostics"]


def test_current_v4_tombstone_suppresses_regeneration_of_retired_baseline(
    tmp_path: Path,
) -> None:
    loaded = harness_core.load_and_bootstrap(tmp_path)
    assert loaded["status"] == "loaded"
    repository = harness_core.GovernanceRepository(tmp_path)
    request = harness_core.build_operation_request(
        "op-delete-repo-delivery-baseline",
        "delete",
        "repo-delivery-baseline",
        base_revision=1,
    )
    repository.register(request)
    deleted = repository.apply(request["operation_id"])
    assert deleted["status"] == "applied"

    reloaded = harness_core.load_repository(
        harness_core.build_load_request(tmp_path)
    )
    ingested = repository.ingest(reloaded)

    assert reloaded["status"] == "ready"
    assert not any(
        candidate["rule_id"] == "repo-delivery-baseline"
        for candidate in reloaded["candidates"]
    )
    assert ingested["status"] == "loaded"
    assert ingested["changed"] is False
    assert "repo-delivery-baseline" in ingested["state"]["deleted_rules"]
