from __future__ import annotations

import copy
import json
import tomllib
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

import harness_core
from harness_core.contracts import (
    validate_fixed_model_cells,
    validate_governance_artifact,
    validate_project_config,
)


EXPECTED_CELL_IDS = [
    "maintainer.generate.specification",
    "maintainer.generate.implementation",
    "maintainer.generate.verification",
    "maintainer.generate.delivery",
    "maintainer.enforce.specification",
    "maintainer.enforce.implementation",
    "maintainer.enforce.verification",
    "maintainer.enforce.delivery",
    "consumer.generate.specification",
    "consumer.generate.implementation",
    "consumer.generate.verification",
    "consumer.generate.delivery",
    "consumer.enforce.specification",
    "consumer.enforce.implementation",
    "consumer.enforce.verification",
    "consumer.enforce.delivery",
]


def minimal_config() -> dict:
    return {
        "schema_version": "3.0.0",
        "rule_instances": {
            "specification": [],
            "implementation": [],
            "verification": [],
            "delivery": [],
        },
    }


def rule(
    rule_id: str,
    *,
    directive: str = "Provide observable acceptance conditions.",
    scope: list[str] | None = None,
) -> dict:
    return {
        "rule_id": rule_id,
        "directive": directive,
        "scope": scope or ["docs/**", "src/**"],
    }


def issue_dicts(config: dict) -> list[dict]:
    return [item.as_dict() for item in validate_project_config(config)]


def test_minimal_config_requires_four_explicit_empty_domains() -> None:
    assert validate_project_config(minimal_config()) == []

    missing = minimal_config()
    del missing["rule_instances"]["delivery"]
    assert issue_dicts(missing) == [
        {
            "code": "GOVERNANCE_DOMAIN_MISSING",
            "path": "/rule_instances/delivery",
            "message": "governance domain must be explicit: delivery",
            "expected": [],
        }
    ]


def test_each_domain_accepts_zero_one_and_many_rules() -> None:
    config = minimal_config()
    config["rule_instances"]["specification"] = [rule("acceptance-first")]
    config["rule_instances"]["implementation"] = [
        rule("small-functions"),
        rule("typed-boundaries"),
    ]
    config["rule_instances"]["verification"] = [
        rule("nearest-test", scope=["tests/**"]),
    ]
    assert validate_project_config(config) == []


def test_rule_ids_are_globally_unique_across_domains() -> None:
    config = minimal_config()
    config["rule_instances"]["specification"] = [rule("acceptance-first")]
    config["rule_instances"]["verification"] = [rule("acceptance-first")]

    assert issue_dicts(config) == [
        {
            "code": "RULE_ID_DUPLICATE",
            "path": "/rule_instances/verification/0/rule_id",
            "message": "rule_id must be globally unique",
            "rule_id": "acceptance-first",
            "expected": "globally unique rule_id",
            "actual": "acceptance-first",
        }
    ]


@pytest.mark.parametrize(
    "rule_id",
    [
        "",
        "Acceptance-first",
        "acceptance_first",
        "-acceptance",
        "acceptance-",
        "acceptance--first",
        "a" * 65,
        "验收优先",
    ],
)
def test_rule_id_has_one_canonical_ascii_kebab_case(rule_id: str) -> None:
    config = minimal_config()
    config["rule_instances"]["specification"] = [rule(rule_id)]
    issues = issue_dicts(config)
    assert [item["code"] for item in issues] == ["RULE_ID_INVALID"]
    assert issues[0]["path"] == "/rule_instances/specification/0/rule_id"
    assert issues[0]["expected"] == "^[a-z0-9]+(?:-[a-z0-9]+)*$"


def test_directive_is_a_non_empty_trimmed_string() -> None:
    config = minimal_config()
    config["rule_instances"]["implementation"] = [
        rule("empty-directive", directive=" \t\n ")
    ]
    issues = issue_dicts(config)
    assert issues[0]["code"] == "RULE_DIRECTIVE_EMPTY"
    assert issues[0]["path"] == (
        "/rule_instances/implementation/0/directive"
    )

    config["rule_instances"]["implementation"][0]["directive"] = 7
    issues = issue_dicts(config)
    assert issues[0]["code"] == "RULE_DIRECTIVE_INVALID"
    assert issues[0]["actual"] == "int"


@pytest.mark.parametrize(
    "invalid_scope",
    [
        "/src/**",
        "C:/src/**",
        r"src\**",
        "src//**",
        "./src/**",
        "../src/**",
        "src/../docs/**",
        "src/a**b",
        "src/{a,b}",
        "src/@(a)",
        "src/[ab]",
        "源码/**",
    ],
)
def test_scope_rejects_non_portable_or_escaping_globs(
    invalid_scope: str,
) -> None:
    config = minimal_config()
    config["rule_instances"]["verification"] = [
        rule("portable-scope", scope=[invalid_scope])
    ]
    issues = issue_dicts(config)
    assert [item["code"] for item in issues] == ["RULE_SCOPE_INVALID"]
    assert issues[0]["path"] == "/rule_instances/verification/0/scope/0"


def test_scope_must_be_non_empty_and_unique() -> None:
    config = minimal_config()
    config["rule_instances"]["delivery"] = [
        {
            "rule_id": "release-notes",
            "directive": "Describe breaking changes.",
            "scope": [],
        }
    ]
    assert issue_dicts(config)[0]["code"] == "RULE_SCOPE_EMPTY"

    config["rule_instances"]["delivery"][0]["scope"] = [
        "docs/**",
        "docs/**",
    ]
    issues = issue_dicts(config)
    assert issues == [
        {
            "code": "RULE_SCOPE_DUPLICATE",
            "path": "/rule_instances/delivery/0/scope/1",
            "message": "scope entries must be unique",
            "rule_id": "release-notes",
            "expected": "unique scope entries",
            "actual": "docs/**",
        }
    ]


def test_unknown_domain_and_extra_root_field_are_located() -> None:
    config = minimal_config()
    config["mode"] = "adopt"
    config["rule_instances"]["security"] = []
    issues = issue_dicts(config)
    assert [(item["code"], item["path"]) for item in issues] == [
        ("CONFIG_ADDITIONAL_PROPERTY", "/mode"),
        ("GOVERNANCE_DOMAIN_UNKNOWN", "/rule_instances/security"),
    ]


@pytest.mark.parametrize(
    "field",
    [
        "audience",
        "responsibility",
        "kind",
        "blocking",
        "action_bindings",
        "preconditions",
        "postconditions",
        "failure",
        "coverage_status",
        "validation_level",
        "permission",
        "provider",
        "branch",
        "delivery",
    ],
)
def test_execution_and_authorization_fields_are_forbidden(
    field: str,
) -> None:
    config = minimal_config()
    value = rule("guidance-only")
    value[field] = True
    config["rule_instances"]["implementation"] = [value]
    issues = issue_dicts(config)
    assert [(item["code"], item["path"]) for item in issues] == [
        (
            "RULE_FIELD_FORBIDDEN",
            f"/rule_instances/implementation/0/{field}",
        )
    ]


def test_v2_input_is_rejected_without_writing_target(tmp_path: Path) -> None:
    target = tmp_path / "model.lock.json"
    target.write_bytes(b"sentinel-v2-lock\n")
    before = target.read_bytes()
    config = {
        "schema_version": "2.0.0",
        "mode": "adopt",
        "project_policy": {},
        "issue_planning": {},
        "branch_policy": {},
    }

    issues = issue_dicts(config)

    assert "SCHEMA_VERSION_UNSUPPORTED" in {
        item["code"] for item in issues
    }
    assert target.read_bytes() == before
    assert not any(
        word in item["message"].lower()
        for item in issues
        for word in ("migrate", "default", "fallback")
    )


def test_v2_artifact_is_rejected_without_writing_target(
    tmp_path: Path,
) -> None:
    target = tmp_path / "model.lock.json"
    target.write_bytes(b"existing-v3-lock\n")
    before = target.read_bytes()
    v2_artifact = {
        "artifact_type": "projection-lock",
        "schema_version": "2.0.0",
        "projection_id": "sha256:" + ("0" * 64),
        "ready": True,
    }

    issues = [
        item.as_dict()
        for item in validate_governance_artifact(v2_artifact)
    ]

    assert issues
    assert all(item["code"] == "SCHEMA_VALIDATION_FAILED" for item in issues)
    assert target.read_bytes() == before


def test_all_contract_rejections_leave_governance_bytes_unchanged(
    tmp_path: Path,
) -> None:
    target = tmp_path / "model.lock.json"
    target.write_bytes(b'{"existing":"lock"}\n')
    before = target.read_bytes()

    invalid_documents = []

    unknown = minimal_config()
    unknown["rule_instances"]["security"] = []
    invalid_documents.append(unknown)

    duplicate = minimal_config()
    duplicate["rule_instances"]["specification"] = [rule("same-id")]
    duplicate["rule_instances"]["delivery"] = [rule("same-id")]
    invalid_documents.append(duplicate)

    forbidden = minimal_config()
    forbidden_rule = rule("no-actions")
    forbidden_rule["provider"] = "github"
    forbidden["rule_instances"]["implementation"] = [forbidden_rule]
    invalid_documents.append(forbidden)

    escaping = minimal_config()
    escaping["rule_instances"]["verification"] = [
        rule("stay-in-repo", scope=["../outside/**"])
    ]
    invalid_documents.append(escaping)

    for document in invalid_documents:
        assert validate_project_config(document)
        assert target.read_bytes() == before


def literal_cells() -> list[dict]:
    cells = []
    for identifier in EXPECTED_CELL_IDS:
        audience, responsibility, domain = identifier.split(".")
        cells.append(
            {
                "cell_id": identifier,
                "audience": audience,
                "responsibility": responsibility,
                "domain": domain,
            }
        )
    return cells


def test_fixed_model_uses_exact_literal_axes_and_sixteen_ids() -> None:
    assert harness_core.AUDIENCES == ("maintainer", "consumer")
    assert harness_core.RESPONSIBILITIES == ("generate", "enforce")
    assert harness_core.DOMAINS == (
        "specification",
        "implementation",
        "verification",
        "delivery",
    )
    assert list(harness_core.CELL_IDS) == EXPECTED_CELL_IDS
    assert validate_fixed_model_cells(literal_cells()) == []


def test_cell_id_must_match_all_three_axis_fields() -> None:
    cells = literal_cells()
    cells[0]["cell_id"] = "consumer.generate.specification"
    issues = [
        item.as_dict() for item in validate_fixed_model_cells(cells)
    ]
    assert [(item["code"], item["path"]) for item in issues] == [
        ("FIXED_MODEL_CELL_SET_MISMATCH", "/cells"),
        ("FIXED_MODEL_CELL_ID_MISMATCH", "/cells/0/cell_id"),
    ]
    assert issues[1]["expected"] == "maintainer.generate.specification"


def test_public_schemas_are_closed_and_versioned_3_0() -> None:
    root = (
        Path(__file__).parents[2]
        / "src"
        / "harness_core"
        / "resources"
        / "schemas"
    )
    harness_schema = json.loads(
        (root / "harness.schema.json").read_text(encoding="utf-8")
    )
    governance_schema = json.loads(
        (root / "governance.schema.json").read_text(encoding="utf-8")
    )
    assert not (root / "common.schema.json").exists()
    assert not (root / "runtime.schema.json").exists()
    assert harness_schema["additionalProperties"] is False
    assert (
        harness_schema["properties"]["rule_instances"][
            "additionalProperties"
        ]
        is False
    )
    assert (
        harness_schema["$defs"]["ruleInstance"]["additionalProperties"]
        is False
    )
    assert governance_schema["properties"]["schema_version"] == {
        "const": "3.0.0"
    }
    Draft202012Validator.check_schema(harness_schema)
    Draft202012Validator.check_schema(governance_schema)
    assert not list(
        Draft202012Validator(harness_schema).iter_errors(minimal_config())
    )


def test_versions_and_public_exports_have_no_v2_aliases() -> None:
    project = tomllib.loads(
        (Path(__file__).parents[2] / "pyproject.toml").read_text(
            encoding="utf-8"
        )
    )
    assert project["project"]["version"] == "3.0.0"
    assert harness_core.__version__ == "3.0.0"
    assert harness_core.SCHEMA_VERSION == "3.0.0"
    assert harness_core.CONTRACT_VERSION == "3.0.0"
    assert harness_core.PROJECTION_COMPILER_VERSION == "3.0.0"
    assert not hasattr(harness_core, "file_digest")
    assert not hasattr(harness_core, "verify_digest")
    assert not hasattr(harness_core, "validate_config")
    assert not hasattr(harness_core, "runtime_artifact_is_valid")


def test_distributed_skill_declares_the_same_closed_v3_contract() -> None:
    skill = (
        Path(__file__).parents[2]
        / "src"
        / "harness_core"
        / "resources"
        / "repo_skill"
        / "harness"
        / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert "Contract version: `3.0.0`." in skill
    assert "exactly sixteen Cells" in skill
    assert "`kind: guidance`" in skill
    assert "grant permission" in skill
    assert "migrate" in skill


def test_diagnostics_are_deterministic_and_json_serializable() -> None:
    config = minimal_config()
    config["rule_instances"]["security"] = []
    config["rule_instances"]["specification"] = [
        {
            "rule_id": "Bad_ID",
            "directive": " ",
            "scope": ["../src/**"],
            "blocking": True,
        }
    ]
    first = issue_dicts(config)
    second = issue_dicts(copy.deepcopy(config))
    assert first == second
    assert first == sorted(
        first,
        key=lambda item: (item["path"], item["code"], item["message"]),
    )
    json.dumps(first, ensure_ascii=False)
