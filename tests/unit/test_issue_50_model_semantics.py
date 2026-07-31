from __future__ import annotations

import harness_core


def test_generate_has_calibration_as_an_internal_stage() -> None:
    assert harness_core.RESPONSIBILITIES == ("generate", "enforce")
    assert harness_core.GENERATE_STAGES == (
        "discover",
        "read",
        "normalize",
        "classify",
        "calibrate",
        "project",
    )
    assert "calibrate" not in harness_core.RESPONSIBILITIES
    assert "calibrate" in harness_core.RESPONSIBILITY_SEMANTICS["generate"]


def test_enforce_is_an_internal_safeguard_not_model_drift_validation() -> None:
    semantics = harness_core.RESPONSIBILITY_SEMANTICS["enforce"].lower()
    assert "internal governance safeguards" in semantics
    assert "typed obligations" in semantics
    assert "external evidence" in semantics
    assert "model drift" not in semantics


def test_skill_scaffold_and_vertical_executor_have_distinct_owners() -> None:
    assert harness_core.LAYER_RESPONSIBILITIES == {
        "skill": (
            "Interpret natural-language governance intent and submit typed "
            "governance requests."
        ),
        "scaffold": (
            "Discover facts, maintain authoritative governance state, project rules, "
            "validate internal consistency, and operate enforcement safeguards."
        ),
        "vertical_executor": (
            "Implement code, run tests, perform Git operations, release, and deploy "
            "software."
        ),
    }


def test_each_domain_maps_one_consumer_rule_to_two_fixed_views() -> None:
    expected = {
        "specification": (
            "consumer.generate.specification",
            "consumer.enforce.specification",
        ),
        "implementation": (
            "consumer.generate.implementation",
            "consumer.enforce.implementation",
        ),
        "verification": (
            "consumer.generate.verification",
            "consumer.enforce.verification",
        ),
        "delivery": (
            "consumer.generate.delivery",
            "consumer.enforce.delivery",
        ),
    }
    assert {
        domain: harness_core.consumer_rule_cell_ids(domain)
        for domain in harness_core.DOMAINS
    } == expected
    assert len(harness_core.CELL_IDS) == 16


def test_all_sixteen_cell_directives_are_distinct_and_in_scope() -> None:
    directives = harness_core.CELL_DIRECTIVES
    assert tuple(directives) == harness_core.CELL_IDS
    assert len(set(directives.values())) == 16
    assert all(
        "model drift" not in directive.lower()
        for directive in directives.values()
    )
    assert all(
        verb not in directive.lower()
        for directive in directives.values()
        for verb in (" run tests", " perform git", " deploy software")
    )
