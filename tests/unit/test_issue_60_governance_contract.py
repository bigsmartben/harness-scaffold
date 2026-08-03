from __future__ import annotations

from itertools import product
from pathlib import Path

from harness_core import model


ROOT = Path(__file__).resolve().parents[2]
NORMATIVE_DOCUMENTS = (
    ROOT / "README.md",
    ROOT / "docs/specification.md",
    ROOT / "docs/harness-2x2x4-governance-model-whitepaper.md",
)


def test_north_star_keeps_effectiveness_below_hard_constraints() -> None:
    assert tuple(model.EFFECTIVENESS_OBJECTIVES) == (
        "intent_alignment",
        "appropriate_delegation",
        "first_time_right",
        "effective_verification",
        "smooth_delivery",
        "continuous_learning",
    )
    assert "human cognitive load" in model.NORTH_STAR_OBJECTIVE
    assert "machine waste" in model.NORTH_STAR_OBJECTIVE
    assert "correct results" in model.NORTH_STAR_OBJECTIVE
    assert "take precedence" in model.HARD_CONSTRAINT_PRECEDENCE
    assert "cannot be traded away" in model.HARD_CONSTRAINT_PRECEDENCE


def test_common_minimum_guarantees_are_deterministic_and_fail_closed() -> None:
    generate = " ".join(model.COMMON_MINIMUM_GUARANTEES["generate"]).lower()
    enforce = " ".join(model.COMMON_MINIMUM_GUARANTEES["enforce"]).lower()

    assert "authoritative sources" in generate
    assert "deterministic and traceable" in generate
    assert "never guess" in generate
    assert "same rule and projection" in generate

    assert "typed obligation" in enforce
    assert "coverage completeness" in enforce
    assert "single passed flag" in enforce
    assert "stale" in enforce
    assert "fail closed" in enforce


def test_responsibilities_form_the_generate_then_enforce_closed_loop() -> None:
    generate = model.RESPONSIBILITY_SEMANTICS["generate"].lower()
    enforce = model.RESPONSIBILITY_SEMANTICS["enforce"].lower()

    assert "generate governance specifications" in generate
    assert "four governance domains" in generate
    assert "execute projected governance specifications" in enforce
    assert "same four domains" in enforce
    assert "selecting one interaction mode" in enforce


def test_assurance_levels_and_three_floors_have_one_ordered_semantics() -> None:
    assert model.ASSURANCE_LEVELS == ("L1", "L2", "L3", "L4")
    assert tuple(model.ASSURANCE_LEVEL_ORDER) == model.ASSURANCE_LEVELS
    assert tuple(model.ASSURANCE_LEVEL_SEMANTICS) == model.ASSURANCE_LEVELS
    assert model.ASSURANCE_LEVEL_INPUTS == (
        "rule_configured_level",
        "event_risk_floor",
        "external_hard_constraint_floor",
    )

    for rule_level, event_floor, hard_floor in product(
        model.ASSURANCE_LEVELS, repeat=3
    ):
        effective = max(
            (rule_level, event_floor, hard_floor),
            key=model.ASSURANCE_LEVEL_ORDER.__getitem__,
        )
        assert model.ASSURANCE_LEVEL_ORDER[effective] == max(
            model.ASSURANCE_LEVEL_ORDER[rule_level],
            model.ASSURANCE_LEVEL_ORDER[event_floor],
            model.ASSURANCE_LEVEL_ORDER[hard_floor],
        )

    semantics = str(model.EFFECTIVE_ASSURANCE_SEMANTICS).lower()
    assert "maximum" in semantics
    assert "cannot lower" in semantics
    assert "domain, scope, revision, and event context" in semantics


def test_each_assurance_level_has_obligation_interaction_and_risk_boundary() -> None:
    for semantics in model.ASSURANCE_LEVEL_SEMANTICS.values():
        assert set(semantics) == {
            "name",
            "minimum_obligation",
            "human_interaction",
            "risk_boundary",
        }
        assert all(semantics.values())

    combined = str(model.ASSURANCE_LEVEL_SEMANTICS).lower()
    assert "private pure function" in combined
    assert "architecture dependencies" in combined
    assert "public apis" in combined
    assert "production" in combined
    assert "rollback capability" in combined
    assert "l0" in model.ADVISORY_ASSURANCE_BOUNDARY.lower()
    assert "cannot bypass enforcement" in model.ADVISORY_ASSURANCE_BOUNDARY.lower()


def test_rule_authoring_recommends_explains_confirms_and_then_automates() -> None:
    assert model.RULE_ASSURANCE_AUTHORING_FLOW == (
        "recommend_source_backed_level",
        "explain_reason_effect_interaction_and_cost",
        "confirm_or_choose_allowed_level_once",
        "bind_level_reason_and_policy_to_operation_digest_revision_and_history",
        "automatically_enforce_until_binding_changes",
    )


def test_four_interaction_modes_have_closed_distinct_semantics() -> None:
    assert model.INTERACTION_MODES == (
        "default_allow",
        "confirm_once",
        "clarification_request",
        "explicit_confirmation",
    )
    assert tuple(model.INTERACTION_MODE_SEMANTICS) == model.INTERACTION_MODES

    for semantics in model.INTERACTION_MODE_SEMANTICS.values():
        assert set(semantics) == {
            "trigger",
            "authorization_effect",
            "reuse_scope",
            "system_behavior",
        }
        assert all(semantics.values())

    combined = str(model.INTERACTION_MODE_SEMANTICS).lower()
    assert "evidence failure still produces blocked" in combined
    assert "request confirmation once" in combined
    assert "never grants permission" in combined
    assert "each concrete event" in combined
    assert "cannot override hard constraints" in combined


def test_confirmation_bindings_and_reconfirmation_triggers_are_closed() -> None:
    assert model.CONFIRM_ONCE_BINDING_FIELDS == (
        "rule_id",
        "revision",
        "domain",
        "scope",
        "event_class",
        "maximum_risk",
        "externality",
    )
    assert model.EXPLICIT_CONFIRMATION_BINDING_FIELDS == (
        "event_id",
        "target",
        "payload_digest",
        "risk",
        "side_effects",
    )
    assert model.RECONFIRMATION_TRIGGERS == (
        "target_or_operation_payload_changed",
        "rule_configured_level_changed",
        "rule_revision_or_scope_changed",
        "event_class_or_risk_floor_changed",
        "external_hard_constraint_floor_changed",
        "externality_or_irreversibility_changed",
        "target_environment_changed",
    )


def test_interaction_modes_are_orthogonal_to_enforcement_decisions() -> None:
    orthogonality = str(model.INTERACTION_DECISION_ORTHOGONALITY).lower()
    assert "whether and how" in orthogonality
    assert "satisfied, blocked, not applicable, or stale" in orthogonality
    assert "default_allow does not imply satisfied" in orthogonality
    assert "never overrides hard constraints" in orthogonality

    assert "enabled rules" in model.APPLICABLE_CONSTRAINT_SET_BOUNDARY
    assert "domain, scope, revision, and event context" in (
        model.APPLICABLE_CONSTRAINT_SET_BOUNDARY
    )
    assert "minimum effective set" in model.REQUIRED_VERIFICATION_SET_BOUNDARY
    assert "unrelated evidence cannot replace" in (
        model.REQUIRED_VERIFICATION_SET_BOUNDARY
    )


def test_normative_examples_cover_interaction_and_efficiency_failures() -> None:
    examples = model.NORMATIVE_GOVERNANCE_EXAMPLES
    assert tuple(examples) == (
        "default_allow_evidence_failure",
        "confirm_once_reuse",
        "confirm_once_binding_changed",
        "clarification_is_not_authorization",
        "explicit_confirmation_refused",
        "over_verification",
        "under_verification",
        "over_confirmation",
        "level_downgrade_below_floor",
        "context_changed",
    )
    assert {example["interaction_mode"] for example in examples.values()} == set(
        model.INTERACTION_MODES
    )
    assert {example["decision"] for example in examples.values()} <= set(
        model.STABLE_DECISION_SEMANTICS
    )
    assert examples["default_allow_evidence_failure"]["decision"] == "blocked"
    assert examples["confirm_once_binding_changed"]["decision"] == "stale"
    assert examples["clarification_is_not_authorization"]["decision"] == "blocked"
    assert examples["over_confirmation"]["interaction_mode"] == "default_allow"


def test_each_domain_defines_the_complete_minimum_contract_shape() -> None:
    assert tuple(model.DOMAIN_MINIMUM_CONTRACTS) == model.DOMAINS
    assert tuple(model.STABLE_DECISION_SEMANTICS) == (
        "not_applicable",
        "blocked",
        "stale",
        "satisfied",
    )

    for contract in model.DOMAIN_MINIMUM_CONTRACTS.values():
        assert set(contract) == {"core_invariant", "generate", "enforce"}
        assert set(contract["generate"]) == {
            "required_inputs",
            "artifact",
            "blocked_when",
        }
        assert set(contract["enforce"]) == {
            "obligation",
            "evidence_requirements",
            "sufficiency",
            "decisions",
        }
        assert tuple(contract["enforce"]["decisions"]) == tuple(
            model.STABLE_DECISION_SEMANTICS
        )
        assert contract["generate"]["required_inputs"]
        assert contract["generate"]["blocked_when"]
        assert contract["enforce"]["evidence_requirements"]


def test_specification_contract_resolves_authority_without_a_second_rule_ssot() -> None:
    contract = model.DOMAIN_MINIMUM_CONTRACTS["specification"]
    combined = str(contract).lower()

    assert "one authoritative specification relationship" in combined
    assert "second editable rule source of truth" in combined
    assert "priority" in combined
    assert "version or digest" in combined
    assert "conflicting sources" in combined
    assert "all applicable requirements" in combined


def test_implementation_contract_requires_complete_constraint_evidence() -> None:
    contract = model.DOMAIN_MINIMUM_CONTRACTS["implementation"]
    combined = str(contract).lower()

    assert "complete applicable set" in combined
    assert "prompt, code, architecture" in combined
    assert "system boundaries" in combined
    assert "interface and data contracts" in combined
    assert "every applicable design constraint" in combined


def test_verification_contract_prevents_under_and_over_verification() -> None:
    contract = model.DOMAIN_MINIMUM_CONTRACTS["verification"]
    combined = str(contract).lower()

    assert "preconditions, steps, and assertions" in combined
    assert "actual change, impact scope, risk" in combined
    assert "minimum effective verification set" in combined
    assert "impact-to-verification coverage mapping" in combined
    assert "affected boundary or user commitment" in combined
    assert "unrelated full suite" in combined
    assert "repeatable matching evidence" in combined


def test_delivery_contract_covers_environment_and_lifecycle() -> None:
    contract = model.DOMAIN_MINIMUM_CONTRACTS["delivery"]
    combined = str(contract).lower()

    assert "target environment" in combined
    assert "lifecycle stage" in combined
    assert "artifact identity, version, and digest" in combined
    assert "admission gates" in combined
    assert "traceability" in combined
    assert "rollback" in combined
    assert "skips or conflicts with a prerequisite stage" in combined


def test_all_cell_directives_match_the_domain_minimum_guarantees() -> None:
    directives = model.CELL_DIRECTIVES
    assert tuple(directives) == model.CELL_IDS
    assert len(set(directives.values())) == 16

    expected_terms = {
        ("generate", "specification"): ("authority", "scope", "conflict"),
        ("enforce", "specification"): ("current", "specification", "evidence"),
        ("generate", "implementation"): ("complete", "traceable", "boundar"),
        ("enforce", "implementation"): ("every applicable", "constraint", "contract"),
        ("generate", "verification"): ("impact", "minimum effective", "coverage"),
        ("enforce", "verification"): ("repeatable", "evidence", "coverage"),
        ("generate", "delivery"): ("environment", "lifecycle", "rollback"),
        ("enforce", "delivery"): ("exact", "environment", "rollback"),
    }
    for audience in model.AUDIENCES:
        for (responsibility, domain), terms in expected_terms.items():
            directive = directives[f"{audience}.{responsibility}.{domain}"].lower()
            assert all(term in directive for term in terms)


def test_f0_semantics_do_not_pretend_to_be_a_new_runtime_contract() -> None:
    assert model.SCHEMA_VERSION == "4.0.0"
    assert model.CONTRACT_VERSION == "4.0.0"
    assert model.CORE_VERSION == "4.0.0"


def test_machine_semantics_and_normative_documents_share_the_f0_baseline() -> None:
    required_terms = (
        "认知负担",
        "机器浪费",
        "外部硬约束",
        "specification",
        "implementation",
        "verification",
        "delivery",
        "L1",
        "L2",
        "L3",
        "L4",
        "L0/advisory",
        "默认放行",
        "确认一次",
        "澄清请求",
        "明确确认",
        "推荐等级",
        "保障效果",
        "验证成本",
        "payload digest",
        "外部性",
        "规则设定等级",
        "事件风险下限",
        "外部硬约束下限",
        "最低有效验证",
        "impact_scope",
        "生命周期",
        "回滚",
        "not_applicable",
        "blocked",
        "stale",
        "satisfied",
    )
    for path in NORMATIVE_DOCUMENTS:
        text = path.read_text(encoding="utf-8")
        assert "issues/59" in text
        assert "issues/60" in text
        assert all(term in text for term in required_terms)
