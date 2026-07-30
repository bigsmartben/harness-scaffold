from __future__ import annotations

import copy
import json
import socket
import urllib.request
from pathlib import Path
from typing import Any

import pytest
import yaml

import harness_core
from harness_core.cli import main
from harness_core.contracts import (
    validate_governance_artifact,
    validate_project_config,
)
from harness_core.initializer import initialize_repository
from harness_core.projection import (
    compile_model_lock,
    project_model_lock,
    render_model_lock,
    validate_model_lock,
)


EXPECTED_CELLS = [
    ("maintainer.generate.specification", "maintainer", "generate", "specification", "Define and deterministically emit the canonical specification Cell."),
    ("maintainer.generate.implementation", "maintainer", "generate", "implementation", "Define and deterministically emit the canonical implementation Cell."),
    ("maintainer.generate.verification", "maintainer", "generate", "verification", "Define and deterministically emit the canonical verification Cell."),
    ("maintainer.generate.delivery", "maintainer", "generate", "delivery", "Define and deterministically emit the canonical delivery Cell."),
    ("maintainer.enforce.specification", "maintainer", "enforce", "specification", "Strictly validate the canonical specification Cell and reject model drift."),
    ("maintainer.enforce.implementation", "maintainer", "enforce", "implementation", "Strictly validate the canonical implementation Cell and reject model drift."),
    ("maintainer.enforce.verification", "maintainer", "enforce", "verification", "Strictly validate the canonical verification Cell and reject model drift."),
    ("maintainer.enforce.delivery", "maintainer", "enforce", "delivery", "Strictly validate the canonical delivery Cell and reject model drift."),
    ("consumer.generate.specification", "consumer", "generate", "specification", "Deterministically project validated specification guidance for the repository."),
    ("consumer.generate.implementation", "consumer", "generate", "implementation", "Deterministically project validated implementation guidance for the repository."),
    ("consumer.generate.verification", "consumer", "generate", "verification", "Deterministically project validated verification guidance for the repository."),
    ("consumer.generate.delivery", "consumer", "generate", "delivery", "Deterministically project validated delivery guidance for the repository."),
    ("consumer.enforce.specification", "consumer", "enforce", "specification", "Strictly validate repository specification guidance against the canonical contract."),
    ("consumer.enforce.implementation", "consumer", "enforce", "implementation", "Strictly validate repository implementation guidance against the canonical contract."),
    ("consumer.enforce.verification", "consumer", "enforce", "verification", "Strictly validate repository verification guidance against the canonical contract."),
    ("consumer.enforce.delivery", "consumer", "enforce", "delivery", "Strictly validate repository delivery guidance against the canonical contract."),
]

FORBIDDEN_CAPABILITIES = {
    "action_graph",
    "apply_push_plan",
    "build_action_graph",
    "build_controlled_delivery_plan",
    "commit_plan",
    "create_task_decision",
    "delivery_plan",
    "handle_hook",
    "issue_plan",
    "mcp_server",
    "permission",
    "provider",
    "push_plan",
    "run_action",
    "run_task",
}


def minimal_config() -> dict[str, Any]:
    return {
        "schema_version": "3.0.1",
        "rule_instances": {
            "specification": [],
            "implementation": [],
            "verification": [],
            "delivery": [],
        },
    }


def guidance_rule(
    rule_id: str = "acceptance-before-code",
    *,
    directive: str = "Define observable acceptance conditions.",
    scope: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "directive": directive,
        "scope": scope or ["docs/**", "src/**"],
    }


def write_config(repository: Path, value: dict[str, Any]) -> Path:
    path = repository / ".harness" / "harness.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(value, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return path


def snapshot(repository: Path) -> dict[str, bytes]:
    return {
        path.relative_to(repository).as_posix(): path.read_bytes()
        for path in repository.rglob("*")
        if path.is_file()
    }


def block_external_calls(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []

    def blocked(*args: Any, **kwargs: Any) -> None:
        calls.append("external")
        raise AssertionError("Harness attempted an external call")

    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(urllib.request, "urlopen", blocked)
    return calls


def test_m_g01_fixed_model_is_exactly_sixteen_differentiated_cells() -> None:
    lock = compile_model_lock(minimal_config())
    actual = [
        (
            cell["cell_id"],
            cell["audience"],
            cell["responsibility"],
            cell["domain"],
            cell["directive"],
        )
        for cell in lock["model"]["cells"]
    ]

    assert lock["model"]["audiences"] == ["maintainer", "consumer"]
    assert lock["model"]["responsibilities"] == ["generate", "enforce"]
    assert lock["model"]["domains"] == [
        "specification",
        "implementation",
        "verification",
        "delivery",
    ]
    assert actual == EXPECTED_CELLS
    assert len({cell[0] for cell in EXPECTED_CELLS}) == 16
    assert len({cell[4] for cell in EXPECTED_CELLS}) == 16


@pytest.mark.parametrize(
    ("path", "replacement", "expected_code"),
    [
        (("model", "domains"), ["specification"], "MODEL_LOCK_MISMATCH"),
        (("model", "audiences", 0), "operator", "MODEL_LOCK_MISMATCH"),
        (("model", "responsibilities", 0), "author", "MODEL_LOCK_MISMATCH"),
        (("model", "cells", 0, "cell_id"), "forged.cell.id", "FIXED_MODEL_MISMATCH"),
        (("model", "cells", 0, "directive"), "Forged directive.", "FIXED_MODEL_MISMATCH"),
    ],
)
def test_m_g02_fixed_model_tampering_is_read_only_and_rejected(
    tmp_path: Path,
    path: tuple[str | int, ...],
    replacement: Any,
    expected_code: str,
) -> None:
    source = minimal_config()
    target = tmp_path / "model.lock.json"
    lock = compile_model_lock(source)
    cursor: Any = lock
    for part in path[:-1]:
        cursor = cursor[part]
    cursor[path[-1]] = replacement
    target.write_bytes(render_model_lock(lock))
    before = target.read_bytes()

    issues = validate_model_lock(source, target)

    assert any(issue.code == expected_code for issue in issues)
    assert target.read_bytes() == before


def test_m_g03_public_and_generated_surfaces_are_guidance_only(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = block_external_calls(monkeypatch)
    source = minimal_config()
    source["rule_instances"]["implementation"] = [guidance_rule()]
    lock = compile_model_lock(source)
    result = initialize_repository(tmp_path)
    with pytest.raises(SystemExit) as help_exit:
        main(["--help"])
    help_text = capsys.readouterr().out.lower().replace("-", "_")
    public = {name.lower() for name in harness_core.__all__}
    generated = {
        path.relative_to(tmp_path).as_posix()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }

    assert lock["rules"][0] == {
        "domain": "implementation",
        "kind": "guidance",
        "rule_id": "acceptance-before-code",
        "directive": "Define observable acceptance conditions.",
        "scope": ["docs/**", "src/**"],
        "source_ref": (
            ".harness/harness.yaml#/rule_instances/"
            "implementation/acceptance-before-code"
        ),
    }
    assert help_exit.value.code == 0
    assert "{init,project,validate,inspect}" in help_text
    assert all(term not in help_text for term in FORBIDDEN_CAPABILITIES)
    assert public.isdisjoint(FORBIDDEN_CAPABILITIES)
    assert result["status"] == "initialized"
    assert generated == {
        ".agents/skills/harness/SKILL.md",
        ".harness/governance/model.lock.json",
        ".harness/harness.yaml",
    }
    assert calls == []


@pytest.mark.parametrize("version", ["1.0.0", "2.0.0"])
def test_m_g04_legacy_inputs_are_rejected_before_any_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    version: str,
) -> None:
    calls = block_external_calls(monkeypatch)
    config_path = tmp_path / ".harness" / "harness.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        f"schema_version: {version}\nmode: adopt\n",
        encoding="utf-8",
    )
    consumer = tmp_path / "consumer.txt"
    consumer.write_bytes(b"keep-consumer-bytes\n")
    legacy_artifact = tmp_path / ".harness" / "governance" / "rules.json"
    legacy_artifact.parent.mkdir()
    legacy_artifact.write_bytes(b'{"artifact_type":"rules"}\n')
    before = snapshot(tmp_path)

    result = initialize_repository(tmp_path)
    artifact_issues = validate_governance_artifact(
        {
            "artifact_type": "projection-lock",
            "schema_version": version,
        }
    )

    assert result["status"] == "blocked"
    assert result["created_paths"] == []
    assert any(
        item["code"] == "SCHEMA_VERSION_UNSUPPORTED"
        for item in result["diagnostics"]
    )
    assert artifact_issues
    assert snapshot(tmp_path) == before
    assert calls == []


def test_c_g01_rules_project_to_guidance_without_external_side_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = block_external_calls(monkeypatch)
    unrelated = tmp_path / "consumer.txt"
    unrelated.write_bytes(b"unchanged\n")
    config = minimal_config()
    config["rule_instances"]["delivery"] = [
        guidance_rule(
            "release-notes",
            directive="  Describe breaking changes.  ",
            scope=["src/**", "docs/**"],
        )
    ]
    target = tmp_path / ".harness" / "governance" / "model.lock.json"

    result = project_model_lock(config, target)
    lock = json.loads(target.read_text(encoding="utf-8"))

    assert result["status"] == "projected"
    assert lock["rules"] == [
        {
            "domain": "delivery",
            "kind": "guidance",
            "rule_id": "release-notes",
            "directive": "Describe breaking changes.",
            "scope": ["docs/**", "src/**"],
            "source_ref": (
                ".harness/harness.yaml#/rule_instances/"
                "delivery/release-notes"
            ),
        }
    ]
    assert unrelated.read_bytes() == b"unchanged\n"
    assert calls == []


def test_c_g02_cardinality_order_and_digest_rules_are_deterministic() -> None:
    base = minimal_config()
    first = copy.deepcopy(base)
    first["rule_instances"]["implementation"] = [
        guidance_rule("z-rule", scope=["src/z/**", "src/**"]),
        guidance_rule("a-rule", scope=["tests/**"]),
    ]
    second = copy.deepcopy(first)
    second["rule_instances"]["implementation"].reverse()
    second["rule_instances"]["implementation"][1]["scope"].reverse()
    changed = copy.deepcopy(first)
    changed["rule_instances"]["implementation"][0]["directive"] = "Changed."

    assert validate_project_config(base) == []
    assert validate_project_config(first) == []
    assert render_model_lock(compile_model_lock(first)) == render_model_lock(
        compile_model_lock(second)
    )
    assert (
        compile_model_lock(first)["source_digest"]
        != compile_model_lock(changed)["source_digest"]
    )
    assert (
        compile_model_lock(first)["projection_digest"]
        != compile_model_lock(changed)["projection_digest"]
    )


def invalid_consumer_configs() -> list[tuple[dict[str, Any], str, str]]:
    cases: list[tuple[dict[str, Any], str, str]] = []

    missing = minimal_config()
    del missing["rule_instances"]["delivery"]
    cases.append((missing, "GOVERNANCE_DOMAIN_MISSING", "/rule_instances/delivery"))

    fifth = minimal_config()
    fifth["rule_instances"]["security"] = []
    cases.append((fifth, "GOVERNANCE_DOMAIN_UNKNOWN", "/rule_instances/security"))

    extra = minimal_config()
    extra["extra"] = True
    cases.append((extra, "CONFIG_ADDITIONAL_PROPERTY", "/extra"))

    empty = minimal_config()
    empty["rule_instances"]["specification"] = [
        guidance_rule("empty-directive", directive=" ")
    ]
    cases.append(
        (
            empty,
            "RULE_DIRECTIVE_EMPTY",
            "/rule_instances/specification/0/directive",
        )
    )

    duplicate = minimal_config()
    duplicate["rule_instances"]["specification"] = [guidance_rule("same-id")]
    duplicate["rule_instances"]["delivery"] = [guidance_rule("same-id")]
    cases.append(
        (
            duplicate,
            "RULE_ID_DUPLICATE",
            "/rule_instances/delivery/0/rule_id",
        )
    )

    for invalid_scope in (
        "/src/**",
        "../src/**",
        r"src\**",
        "src//**",
    ):
        invalid = minimal_config()
        invalid["rule_instances"]["verification"] = [
            guidance_rule("invalid-scope", scope=[invalid_scope])
        ]
        cases.append(
            (
                invalid,
                "RULE_SCOPE_INVALID",
                "/rule_instances/verification/0/scope/0",
            )
        )

    repeated = minimal_config()
    repeated["rule_instances"]["delivery"] = [
        guidance_rule("repeated-scope", scope=["docs/**", "docs/**"])
    ]
    cases.append(
        (
            repeated,
            "RULE_SCOPE_DUPLICATE",
            "/rule_instances/delivery/0/scope/1",
        )
    )
    return cases


@pytest.mark.parametrize(
    ("document", "expected_code", "expected_path"),
    invalid_consumer_configs(),
)
def test_c_g03_invalid_rules_have_precise_diagnostics_and_zero_writes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    document: dict[str, Any],
    expected_code: str,
    expected_path: str,
) -> None:
    calls = block_external_calls(monkeypatch)
    write_config(tmp_path, document)
    target = tmp_path / ".harness" / "governance" / "model.lock.json"
    target.parent.mkdir()
    target.write_bytes(b"existing-lock\n")
    before = target.read_bytes()

    exit_code = main(["project", str(tmp_path), "--json"])
    payload = json.loads(capsys.readouterr().out)
    diagnostic = next(
        item
        for item in payload["diagnostics"]
        if item["code"] == expected_code
    )

    assert exit_code == 2
    assert payload["status"] == "blocked"
    assert diagnostic["path"] == expected_path
    if "/0/" in expected_path:
        assert diagnostic.get("rule_id")
    assert target.read_bytes() == before
    assert calls == []


@pytest.mark.parametrize(
    "field",
    [
        "kind",
        "blocking",
        "action",
        "action_bindings",
        "permission",
        "branch",
        "delivery",
        "provider",
        "validation_level",
    ],
)
def test_c_g04_execution_and_authorization_fields_never_call_providers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
) -> None:
    calls = block_external_calls(monkeypatch)
    document = minimal_config()
    item = guidance_rule("guidance-only")
    item[field] = True
    document["rule_instances"]["implementation"] = [item]
    target = tmp_path / "model.lock.json"
    target.write_bytes(b"existing-lock\n")
    before = target.read_bytes()

    result = project_model_lock(document, target)

    assert result["status"] == "blocked"
    assert result["diagnostics"] == [
        {
            "code": "RULE_FIELD_FORBIDDEN",
            "path": f"/rule_instances/implementation/0/{field}",
            "message": f"rule field is not allowed: {field}",
            "rule_id": "guidance-only",
            "expected": ["rule_id", "directive", "scope"],
            "actual": field,
        }
    ]
    assert target.read_bytes() == before
    assert calls == []


def test_c_g05_minimal_input_is_explicit_and_never_default_completed(
    tmp_path: Path,
) -> None:
    valid = minimal_config()
    missing = minimal_config()
    del missing["rule_instances"]["verification"]
    original = copy.deepcopy(missing)

    assert validate_project_config(valid) == []
    issues = validate_project_config(missing)
    initialized = initialize_repository(tmp_path)

    assert [(item.code, item.path) for item in issues] == [
        ("GOVERNANCE_DOMAIN_MISSING", "/rule_instances/verification")
    ]
    assert missing == original
    assert initialized["status"] == "initialized"
    assert {
        path.relative_to(tmp_path).as_posix()
        for path in tmp_path.rglob("*")
        if path.is_file()
    } == {
        ".agents/skills/harness/SKILL.md",
        ".harness/governance/model.lock.json",
        ".harness/harness.yaml",
    }
