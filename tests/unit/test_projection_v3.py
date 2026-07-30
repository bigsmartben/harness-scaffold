from __future__ import annotations

import copy
import json
from pathlib import Path

import yaml

from harness_core.artifacts import canonical_digest
from harness_core.contracts import validate_governance_artifact
from harness_core.projection import (
    compile_model_lock,
    project_model_lock,
    render_model_lock,
    validate_model_lock,
)


EXPECTED_CELLS = [
    {
        "cell_id": "maintainer.generate.specification",
        "audience": "maintainer",
        "responsibility": "generate",
        "domain": "specification",
        "directive": (
            "Define and deterministically emit the canonical specification Cell."
        ),
    },
    {
        "cell_id": "maintainer.generate.implementation",
        "audience": "maintainer",
        "responsibility": "generate",
        "domain": "implementation",
        "directive": (
            "Define and deterministically emit the canonical implementation Cell."
        ),
    },
    {
        "cell_id": "maintainer.generate.verification",
        "audience": "maintainer",
        "responsibility": "generate",
        "domain": "verification",
        "directive": (
            "Define and deterministically emit the canonical verification Cell."
        ),
    },
    {
        "cell_id": "maintainer.generate.delivery",
        "audience": "maintainer",
        "responsibility": "generate",
        "domain": "delivery",
        "directive": (
            "Define and deterministically emit the canonical delivery Cell."
        ),
    },
    {
        "cell_id": "maintainer.enforce.specification",
        "audience": "maintainer",
        "responsibility": "enforce",
        "domain": "specification",
        "directive": (
            "Strictly validate the canonical specification Cell and reject model drift."
        ),
    },
    {
        "cell_id": "maintainer.enforce.implementation",
        "audience": "maintainer",
        "responsibility": "enforce",
        "domain": "implementation",
        "directive": (
            "Strictly validate the canonical implementation Cell and reject model drift."
        ),
    },
    {
        "cell_id": "maintainer.enforce.verification",
        "audience": "maintainer",
        "responsibility": "enforce",
        "domain": "verification",
        "directive": (
            "Strictly validate the canonical verification Cell and reject model drift."
        ),
    },
    {
        "cell_id": "maintainer.enforce.delivery",
        "audience": "maintainer",
        "responsibility": "enforce",
        "domain": "delivery",
        "directive": (
            "Strictly validate the canonical delivery Cell and reject model drift."
        ),
    },
    {
        "cell_id": "consumer.generate.specification",
        "audience": "consumer",
        "responsibility": "generate",
        "domain": "specification",
        "directive": (
            "Deterministically project validated specification guidance for the repository."
        ),
    },
    {
        "cell_id": "consumer.generate.implementation",
        "audience": "consumer",
        "responsibility": "generate",
        "domain": "implementation",
        "directive": (
            "Deterministically project validated implementation guidance for the repository."
        ),
    },
    {
        "cell_id": "consumer.generate.verification",
        "audience": "consumer",
        "responsibility": "generate",
        "domain": "verification",
        "directive": (
            "Deterministically project validated verification guidance for the repository."
        ),
    },
    {
        "cell_id": "consumer.generate.delivery",
        "audience": "consumer",
        "responsibility": "generate",
        "domain": "delivery",
        "directive": (
            "Deterministically project validated delivery guidance for the repository."
        ),
    },
    {
        "cell_id": "consumer.enforce.specification",
        "audience": "consumer",
        "responsibility": "enforce",
        "domain": "specification",
        "directive": (
            "Strictly validate repository specification guidance against the canonical contract."
        ),
    },
    {
        "cell_id": "consumer.enforce.implementation",
        "audience": "consumer",
        "responsibility": "enforce",
        "domain": "implementation",
        "directive": (
            "Strictly validate repository implementation guidance against the canonical contract."
        ),
    },
    {
        "cell_id": "consumer.enforce.verification",
        "audience": "consumer",
        "responsibility": "enforce",
        "domain": "verification",
        "directive": (
            "Strictly validate repository verification guidance against the canonical contract."
        ),
    },
    {
        "cell_id": "consumer.enforce.delivery",
        "audience": "consumer",
        "responsibility": "enforce",
        "domain": "delivery",
        "directive": (
            "Strictly validate repository delivery guidance against the canonical contract."
        ),
    },
]


def config() -> dict:
    return {
            "schema_version": "3.0.1",
        "rule_instances": {
            "specification": [],
            "implementation": [],
            "verification": [],
            "delivery": [],
        },
    }


def one_rule_config() -> dict:
    value = config()
    value["rule_instances"]["specification"] = [
        {
            "rule_id": "acceptance-before-code",
            "directive": "  Define observable acceptance conditions.  ",
            "scope": ["src/**", "docs/**"],
        }
    ]
    return value


def test_empty_model_lock_has_exact_fixed_cells_and_public_schema() -> None:
    lock = compile_model_lock(config())
    assert lock["artifact_type"] == "harness-model-lock"
    assert lock["schema_version"] == "3.0.1"
    assert lock["components"] == {
        "core_version": "3.0.1",
        "contract_version": "3.0.1",
        "compiler_version": "3.0.1",
    }
    assert lock["model"]["audiences"] == ["maintainer", "consumer"]
    assert lock["model"]["responsibilities"] == ["generate", "enforce"]
    assert lock["model"]["domains"] == [
        "specification",
        "implementation",
        "verification",
        "delivery",
    ]
    assert lock["model"]["cells"] == EXPECTED_CELLS
    assert len({cell["directive"] for cell in EXPECTED_CELLS}) == 16
    assert (
        EXPECTED_CELLS[0]["directive"]
        != EXPECTED_CELLS[8]["directive"]
    )
    assert lock["rules"] == []
    assert validate_governance_artifact(lock) == []
    assert validate_model_lock(config(), lock) == []


def test_rules_are_trimmed_sorted_guidance_with_stable_source_refs() -> None:
    value = config()
    value["rule_instances"]["specification"] = [
        {
            "rule_id": "z-last",
            "directive": "  Last. ",
            "scope": ["src/z/**", "docs/**"],
        },
        {
            "rule_id": "a-first",
            "directive": "\tFirst.\n",
            "scope": ["src/**"],
        },
    ]
    value["rule_instances"]["delivery"] = [
        {
            "rule_id": "release-notes",
            "directive": "Describe breaking changes.",
            "scope": ["docs/**"],
        }
    ]

    assert compile_model_lock(value)["rules"] == [
        {
            "domain": "specification",
            "kind": "guidance",
            "rule_id": "a-first",
            "directive": "First.",
            "scope": ["src/**"],
            "source_ref": (
                ".harness/harness.yaml#/rule_instances/"
                "specification/a-first"
            ),
        },
        {
            "domain": "specification",
            "kind": "guidance",
            "rule_id": "z-last",
            "directive": "Last.",
            "scope": ["docs/**", "src/z/**"],
            "source_ref": (
                ".harness/harness.yaml#/rule_instances/"
                "specification/z-last"
            ),
        },
        {
            "domain": "delivery",
            "kind": "guidance",
            "rule_id": "release-notes",
            "directive": "Describe breaking changes.",
            "scope": ["docs/**"],
            "source_ref": (
                ".harness/harness.yaml#/rule_instances/"
                "delivery/release-notes"
            ),
        },
    ]


def test_each_of_four_domains_projects_many_rules() -> None:
    value = config()
    for domain in (
        "specification",
        "implementation",
        "verification",
        "delivery",
    ):
        value["rule_instances"][domain] = [
            {
                "rule_id": f"{domain}-b",
                "directive": f"Second {domain} rule.",
                "scope": ["src/**"],
            },
            {
                "rule_id": f"{domain}-a",
                "directive": f"First {domain} rule.",
                "scope": ["docs/**"],
            },
        ]

    lock = compile_model_lock(value)
    assert len(lock["rules"]) == 8
    assert [
        (item["domain"], item["rule_id"]) for item in lock["rules"]
    ] == [
        ("specification", "specification-a"),
        ("specification", "specification-b"),
        ("implementation", "implementation-a"),
        ("implementation", "implementation-b"),
        ("verification", "verification-a"),
        ("verification", "verification-b"),
        ("delivery", "delivery-a"),
        ("delivery", "delivery-b"),
    ]
    assert validate_model_lock(value, lock) == []


def test_input_and_scope_reordering_do_not_change_bytes_or_digests() -> None:
    first = config()
    first["rule_instances"]["implementation"] = [
        {
            "rule_id": "z-rule",
            "directive": "Z.",
            "scope": ["src/z/**", "src/**"],
        },
        {
            "rule_id": "a-rule",
            "directive": "A.",
            "scope": ["docs/**"],
        },
    ]
    second = copy.deepcopy(first)
    second["rule_instances"]["implementation"].reverse()
    second["rule_instances"]["implementation"][1]["scope"].reverse()

    first_lock = compile_model_lock(first)
    second_lock = compile_model_lock(second)
    assert first_lock == second_lock
    assert render_model_lock(first_lock) == render_model_lock(second_lock)


def test_same_source_in_different_directories_is_byte_identical(
    tmp_path: Path,
) -> None:
    payload = yaml.safe_dump(
        one_rule_config(),
        allow_unicode=True,
        sort_keys=False,
    )
    paths = []
    for name in ("first", "second"):
        source = tmp_path / name / ".harness" / "harness.yaml"
        source.parent.mkdir(parents=True)
        source.write_text(payload, encoding="utf-8")
        (tmp_path / name / "unrelated.txt").write_text(
            name,
            encoding="utf-8",
        )
        paths.append(source)

    first = render_model_lock(compile_model_lock(paths[0]))
    second = render_model_lock(compile_model_lock(paths[1]))
    assert first == second


def test_each_rule_change_changes_both_digests() -> None:
    baseline = compile_model_lock(one_rule_config())
    variants = []

    directive = one_rule_config()
    directive["rule_instances"]["specification"][0][
        "directive"
    ] = "Define different acceptance conditions."
    variants.append(directive)

    scope = one_rule_config()
    scope["rule_instances"]["specification"][0]["scope"] = ["tests/**"]
    variants.append(scope)

    added = one_rule_config()
    added["rule_instances"]["verification"] = [
        {
            "rule_id": "nearest-test",
            "directive": "Run the nearest test.",
            "scope": ["tests/**"],
        }
    ]
    variants.append(added)

    removed = config()
    variants.append(removed)

    for variant in variants:
        lock = compile_model_lock(variant)
        assert lock["source_digest"] != baseline["source_digest"]
        assert lock["projection_digest"] != baseline["projection_digest"]


def test_digest_inputs_ignore_git_workflows_and_unrelated_files(
    tmp_path: Path,
) -> None:
    source = one_rule_config()
    baseline = compile_model_lock(source)
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text(
        "ref: refs/heads/other\n",
        encoding="utf-8",
    )
    workflow = tmp_path / ".github" / "workflows" / "ci.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("name: changed\n", encoding="utf-8")
    (tmp_path / "package.bin").write_bytes(b"unrelated")
    assert compile_model_lock(source) == baseline


def test_validator_detects_every_tampered_surface() -> None:
    source = one_rule_config()
    baseline = compile_model_lock(source)
    mutations = [
        (("model", "cells", 0, "audience"), "consumer"),
        (("model", "cells", 0, "directive"), "Tampered."),
        (("rules", 0, "directive"), "Tampered."),
        (("rules", 0, "scope"), ["other/**"]),
        (("components", "compiler_version"), "9.9.9"),
        (("source_digest",), "sha256:" + ("1" * 64)),
        (("projection_digest",), "sha256:" + ("2" * 64)),
    ]

    for path, replacement in mutations:
        tampered = copy.deepcopy(baseline)
        cursor = tampered
        for key in path[:-1]:
            cursor = cursor[key]
        cursor[path[-1]] = replacement
        assert validate_model_lock(source, tampered), path


def test_recomputed_self_digest_does_not_hide_cell_tampering() -> None:
    source = one_rule_config()
    tampered = compile_model_lock(source)
    tampered["model"]["cells"][0]["directive"] = "Forged directive."
    del tampered["projection_digest"]
    tampered["projection_digest"] = canonical_digest(tampered)

    issues = [
        item.as_dict() for item in validate_model_lock(source, tampered)
    ]
    assert any(item["code"] == "FIXED_MODEL_MISMATCH" for item in issues)
    assert any(
        item["path"] == "/model/cells/0/directive" for item in issues
    )


def test_old_lock_is_stale_after_source_rule_deletion() -> None:
    old_lock = compile_model_lock(one_rule_config())
    issues = [
        item.as_dict() for item in validate_model_lock(config(), old_lock)
    ]
    assert any(
        item["code"] == "PROJECTED_RULE_MISMATCH" for item in issues
    )


def test_projection_writes_one_lock_and_then_is_unchanged(
    tmp_path: Path,
) -> None:
    target = tmp_path / ".harness" / "governance" / "model.lock.json"
    first = project_model_lock(one_rule_config(), target)
    before = target.read_bytes()
    second = project_model_lock(one_rule_config(), target)

    assert first["status"] == "projected"
    assert second["status"] == "unchanged"
    assert target.read_bytes() == before
    assert json.loads(before) == compile_model_lock(one_rule_config())
    assert validate_model_lock(one_rule_config(), target) == []


def test_invalid_source_is_zero_write(tmp_path: Path) -> None:
    target = tmp_path / "model.lock.json"
    target.write_bytes(b"existing-lock\n")
    before = target.read_bytes()
    invalid = config()
    invalid["rule_instances"]["security"] = []

    result = project_model_lock(invalid, target)

    assert result["status"] == "blocked"
    assert result["diagnostics"][0]["code"] == "GOVERNANCE_DOMAIN_UNKNOWN"
    assert target.read_bytes() == before
    assert not list(tmp_path.glob("*.tmp"))


def test_atomic_replace_failure_preserves_existing_bytes(
    tmp_path: Path,
) -> None:
    target = tmp_path / "model.lock.json"
    target.write_bytes(b"existing-lock\n")
    before = target.read_bytes()

    def fail_replace(source: str | Path, destination: str | Path) -> None:
        raise OSError("simulated atomic replacement failure")

    result = project_model_lock(
        one_rule_config(),
        target,
        replace=fail_replace,
    )

    assert result["status"] == "blocked"
    assert result["diagnostics"][0]["code"] == "MODEL_LOCK_WRITE_FAILED"
    assert target.read_bytes() == before
    assert not list(tmp_path.glob("*.tmp"))


def test_output_has_no_action_authorization_or_provider_surface() -> None:
    serialized = render_model_lock(
        compile_model_lock(one_rule_config())
    ).decode("utf-8").lower()
    forbidden = [
        "action_graph",
        "action_bindings",
        "approval",
        "blocking",
        "branch",
        "coverage_status",
        "evidence",
        "failure",
        "permission",
        "postconditions",
        "preconditions",
        "provider",
        "validation_level",
        "workflow",
    ]
    for term in forbidden:
        assert term not in serialized
