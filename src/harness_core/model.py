"""The single normative source for the fixed Harness 4 meta-model."""

from __future__ import annotations

from itertools import product


SCHEMA_VERSION = "4.0.0"
CORE_VERSION = SCHEMA_VERSION
CONTRACT_VERSION = SCHEMA_VERSION
PROJECTION_COMPILER_VERSION = SCHEMA_VERSION

AUDIENCES = ("maintainer", "consumer")
RESPONSIBILITIES = ("generate", "enforce")
DOMAINS = ("specification", "implementation", "verification", "delivery")

NORTH_STAR_OBJECTIVE = (
    "Under hard constraints for quality, safety, system boundaries, and "
    "traceability, reduce human cognitive load, manual touchpoints, collaboration "
    "wait time, machine waste, and rework so humans and machines deliver correct "
    "results faster and more reliably and continuously learn from outcomes."
)

EFFECTIVENESS_OBJECTIVES = {
    "intent_alignment": (
        "Make the requested outcome, scope, constraints, and acceptance criteria explicit."
    ),
    "appropriate_delegation": (
        "Keep goals, priorities, risk thresholds, and approvals with humans while "
        "machines discover, normalize, execute, and collect evidence within those bounds."
    ),
    "first_time_right": (
        "Produce results that satisfy the applicable architecture, contracts, boundaries, "
        "and construction constraints from the start."
    ),
    "effective_verification": (
        "Select the minimum effective verification set from scenarios, actual impact, "
        "risk, affected boundaries, and user commitments."
    ),
    "smooth_delivery": (
        "Move verified, traceable, and recoverable artifacts through the correct "
        "environment and lifecycle gates."
    ),
    "continuous_learning": (
        "Feed failures back into authoritative specifications, design constraints, "
        "or verification scenarios so the same defect is less likely to recur."
    ),
}

HARD_CONSTRAINT_PRECEDENCE = (
    "External hard constraints take precedence over effectiveness optimization; "
    "quality, safety, system boundaries, data contracts, and traceability cannot be "
    "traded away to improve an efficiency metric."
)

GENERATE_STAGES = (
    "discover",
    "read",
    "normalize",
    "classify",
    "calibrate",
    "project",
)

RESPONSIBILITY_SEMANTICS = {
    "generate": (
        "Generate governance specifications by discovering repository facts and existing "
        "governance sources, then read, normalize, classify, calibrate, and "
        "deterministically project rules for the four governance domains."
    ),
    "enforce": (
        "Execute projected governance specifications through internal governance "
        "safeguards for the same four domains by determining applicability and assurance, "
        "selecting one interaction mode, creating typed obligations, and verifying "
        "external evidence."
    ),
}

COMMON_MINIMUM_GUARANTEES = {
    "generate": (
        "Use authoritative sources or provable repository facts.",
        "Keep discovery, reading, normalization, classification, calibration, and "
        "projection deterministic and traceable.",
        "Produce the minimum explicit semantics required by enforcement rather than an "
        "ambiguous natural-language directive.",
        "Block with a stable diagnostic when required input is missing, sources conflict, "
        "or semantics are insufficient; never guess.",
        "Produce the same rule and projection from the same facts, sources, and contract "
        "version.",
    ),
    "enforce": (
        "Determine applicability from the current projection, rule, revision, and context.",
        "Create a typed obligation that states the minimum completion conditions.",
        "Bind evidence to the current projection, rule, revision, target, and required "
        "context.",
        "Check coverage completeness and evidence sufficiency instead of accepting a "
        "single passed flag.",
        "Make old obligations and evidence stale after a relevant rule, version, impact "
        "scope, target environment, or artifact change.",
        "Fail closed when an applicable obligation or sufficient evidence is missing.",
    ),
}

STABLE_DECISION_SEMANTICS = {
    "not_applicable": (
        "The current projected rule does not apply to the governed event."
    ),
    "blocked": (
        "A required input, obligation, or sufficient matching evidence is missing, "
        "conflicting, failed, or incomplete."
    ),
    "stale": (
        "The rule, revision, relevant context, impact scope, target environment, or "
        "artifact no longer matches the obligation or evidence."
    ),
    "satisfied": (
        "Every applicable obligation has sufficient evidence matching the current context."
    ),
}

ASSURANCE_LEVELS = ("L1", "L2", "L3", "L4")
ASSURANCE_LEVEL_ORDER = {
    level: order for order, level in enumerate(ASSURANCE_LEVELS, start=1)
}
ASSURANCE_LEVEL_SEMANTICS = {
    "L1": {
        "name": "automatic assurance",
        "minimum_obligation": (
            "Automatically create and verify local, repeatable minimum evidence."
        ),
        "human_interaction": (
            "Use default_allow when information is sufficient; routine execution needs "
            "no human confirmation."
        ),
        "risk_boundary": (
            "Low-risk, reversible, internal work such as formatting or a private pure "
            "function."
        ),
    },
    "L2": {
        "name": "prudent assurance",
        "minimum_obligation": (
            "Automatically analyze impact and verify targeted cross-module evidence."
        ),
        "human_interaction": (
            "Use default_allow when information is sufficient and clarification_request "
            "only for material ambiguity."
        ),
        "risk_boundary": (
            "Internal module interfaces, architecture dependencies, or other reversible "
            "work with bounded impact."
        ),
    },
    "L3": {
        "name": "mandatory gate",
        "minimum_obligation": (
            "Require every current projected obligation and all necessary evidence before "
            "the governed result can pass."
        ),
        "human_interaction": (
            "Use confirm_once for a closed reusable authorization binding; otherwise use "
            "explicit_confirmation, with clarification_request for material ambiguity."
        ),
        "risk_boundary": (
            "Public APIs, data contracts, compatibility commitments, or new public and "
            "external authority."
        ),
    },
    "L4": {
        "name": "critical gate",
        "minimum_obligation": (
            "Require complete evidence, explicit event authorization, environment and "
            "artifact gates, and rollback capability when applicable."
        ),
        "human_interaction": (
            "Use explicit_confirmation for each concrete event; confirmation cannot "
            "override a failed hard constraint."
        ),
        "risk_boundary": (
            "Production, irreversible, destructive, security-boundary, or other critical "
            "external work."
        ),
    },
}
if tuple(ASSURANCE_LEVEL_SEMANTICS) != ASSURANCE_LEVELS:
    raise RuntimeError("assurance semantics must match canonical assurance order")

ASSURANCE_LEVEL_INPUTS = (
    "rule_configured_level",
    "event_risk_floor",
    "external_hard_constraint_floor",
)
EFFECTIVE_ASSURANCE_SEMANTICS = {
    "relation": (
        "The effective assurance level is the maximum of the rule configured level, "
        "the relevant event risk floor, and the external hard constraint floor."
    ),
    "applicability": (
        "Compute the maximum only for enabled rules deterministically matching the "
        "current domain, scope, revision, and event context."
    ),
    "downgrade_boundary": (
        "A user may raise assurance but cannot lower it below the relevant event risk or "
        "external hard constraint floor."
    ),
}
ADVISORY_ASSURANCE_BOUNDARY = (
    "L0 or advisory is not an enabled governance-rule assurance level and cannot bypass "
    "enforcement; any future advisory behavior requires a separate explicit contract."
)

RULE_ASSURANCE_AUTHORING_FLOW = (
    "recommend_source_backed_level",
    "explain_reason_effect_interaction_and_cost",
    "confirm_or_choose_allowed_level_once",
    "bind_level_reason_and_policy_to_operation_digest_revision_and_history",
    "automatically_enforce_until_binding_changes",
)

INTERACTION_MODES = (
    "default_allow",
    "confirm_once",
    "clarification_request",
    "explicit_confirmation",
)
INTERACTION_MODE_SEMANTICS = {
    "default_allow": {
        "trigger": (
            "Information is sufficient, no new authority is required, and current machine "
            "obligations are satisfied or can be completed automatically."
        ),
        "authorization_effect": (
            "No permission is granted; automatic progress still requires sufficient "
            "matching evidence."
        ),
        "reuse_scope": "No authorization binding is created or reused.",
        "system_behavior": (
            "Proceed automatically and explain the applicable assurance and evidence; "
            "evidence failure still produces blocked."
        ),
    },
    "confirm_once": {
        "trigger": (
            "The user authorizes a closed, stable, reviewable binding that can be reused "
            "without increasing risk or externality."
        ),
        "authorization_effect": (
            "Grant reusable authority only inside the exact confirmed binding."
        ),
        "reuse_scope": (
            "Reuse requires the same rule_id, revision, domain, scope, event_class, "
            "maximum_risk, and externality."
        ),
        "system_behavior": (
            "Request confirmation once, then avoid repeated confirmation while every "
            "binding field remains unchanged; evidence still determines the decision."
        ),
    },
    "clarification_request": {
        "trigger": (
            "Material ambiguity would change authority, applicability, the minimum "
            "verification set, target environment, or external side effects."
        ),
        "authorization_effect": (
            "Clarification supplies information and never grants permission."
        ),
        "reuse_scope": "A clarification answer creates no reusable authorization.",
        "system_behavior": (
            "Ask only for the minimum missing information, then recompute assurance and "
            "interaction mode."
        ),
    },
    "explicit_confirmation": {
        "trigger": (
            "The concrete event needs new production, external, irreversible, security, "
            "destructive, or other high-risk authority that cannot be safely reused."
        ),
        "authorization_effect": (
            "Grant authority only for the exact current event; it cannot override hard "
            "constraints or failed evidence."
        ),
        "reuse_scope": (
            "Bind only the current event_id, target, payload_digest, risk, and side_effects."
        ),
        "system_behavior": (
            "Explain the concrete effect and request confirmation for each concrete "
            "event; refusal or insufficient evidence produces blocked."
        ),
    },
}
if tuple(INTERACTION_MODE_SEMANTICS) != INTERACTION_MODES:
    raise RuntimeError("interaction semantics must match canonical interaction order")

CONFIRM_ONCE_BINDING_FIELDS = (
    "rule_id",
    "revision",
    "domain",
    "scope",
    "event_class",
    "maximum_risk",
    "externality",
)
EXPLICIT_CONFIRMATION_BINDING_FIELDS = (
    "event_id",
    "target",
    "payload_digest",
    "risk",
    "side_effects",
)
RECONFIRMATION_TRIGGERS = (
    "target_or_operation_payload_changed",
    "rule_configured_level_changed",
    "rule_revision_or_scope_changed",
    "event_class_or_risk_floor_changed",
    "external_hard_constraint_floor_changed",
    "externality_or_irreversibility_changed",
    "target_environment_changed",
)

INTERACTION_DECISION_ORTHOGONALITY = {
    "interaction_question": "Whether and how the system requests human involvement.",
    "decision_question": (
        "Whether current governance obligations are satisfied, blocked, not applicable, "
        "or stale."
    ),
    "invariants": (
        "default_allow does not imply satisfied or bypass evidence",
        "confirm_once reuses authority but never reuses stale evidence",
        "clarification_request supplies information and never grants authority",
        "explicit_confirmation grants event authority but never overrides hard constraints",
        "not_applicable and stale should be determined before unnecessary interaction",
    ),
}

APPLICABLE_CONSTRAINT_SET_BOUNDARY = (
    "All applicable constraints means only enabled rules in the current authoritative "
    "projection that deterministically match domain, scope, revision, and event context."
)
REQUIRED_VERIFICATION_SET_BOUNDARY = (
    "All required verification means the minimum effective set deterministically derived "
    "from current impact scope, risk, affected boundaries, user commitments, and effective "
    "assurance; unrelated evidence cannot replace a missing required item."
)

NORMATIVE_GOVERNANCE_EXAMPLES = {
    "default_allow_evidence_failure": {
        "interaction_mode": "default_allow",
        "decision": "blocked",
        "reason": "automatic progress never converts missing or failed evidence to satisfied",
    },
    "confirm_once_reuse": {
        "interaction_mode": "confirm_once",
        "decision": "satisfied",
        "reason": "the closed binding is unchanged and current evidence is sufficient",
    },
    "confirm_once_binding_changed": {
        "interaction_mode": "confirm_once",
        "decision": "stale",
        "reason": "a changed binding cannot reuse earlier authority or evidence",
    },
    "clarification_is_not_authorization": {
        "interaction_mode": "clarification_request",
        "decision": "blocked",
        "reason": "material ambiguity remains unresolved and no permission was granted",
    },
    "explicit_confirmation_refused": {
        "interaction_mode": "explicit_confirmation",
        "decision": "blocked",
        "reason": "the exact high-risk event was not authorized",
    },
    "over_verification": {
        "interaction_mode": "default_allow",
        "decision": "blocked",
        "reason": "an unrelated full suite has no impact or risk justification",
    },
    "under_verification": {
        "interaction_mode": "default_allow",
        "decision": "blocked",
        "reason": "an affected boundary or user commitment lacks required verification",
    },
    "over_confirmation": {
        "interaction_mode": "default_allow",
        "decision": "blocked",
        "reason": "a sufficient low-risk event must not be escalated to needless confirmation",
    },
    "level_downgrade_below_floor": {
        "interaction_mode": "clarification_request",
        "decision": "blocked",
        "reason": "the selected level is below the event or hard-constraint floor",
    },
    "context_changed": {
        "interaction_mode": "default_allow",
        "decision": "stale",
        "reason": "the rule, impact scope, environment, artifact, or event binding changed",
    },
}

# These dictionaries are normative semantic metadata, not fields added to the v4 runtime
# Rule, Operation, state, projection, event, obligation, or Evidence schemas.
DOMAIN_MINIMUM_CONTRACTS = {
    "specification": {
        "core_invariant": (
            "Resolve one authoritative specification relationship for the applicable "
            "scope and version without creating a second editable rule source of truth."
        ),
        "generate": {
            "required_inputs": (
                "candidate specification sources with identity, authority or priority, "
                "version or digest, and applicability scope",
                "the current authoritative consumer rule state as the only rule SSOT",
            ),
            "artifact": (
                "one resolved authoritative specification identity with source, priority, "
                "scope, version or digest, summary, and conflict outcome"
            ),
            "blocked_when": (
                "no authoritative source or priority can be established",
                "conflicting sources cannot be resolved deterministically",
                "the applicable scope, version, or required meaning is insufficient",
            ),
        },
        "enforce": {
            "obligation": (
                "Bind the governed result to the current specification identity, version "
                "or digest, and summary, and prove conformance."
            ),
            "evidence_requirements": (
                "current projection, rule, revision, target, and specification binding",
                "conformance evidence for every applicable specification requirement",
            ),
            "sufficiency": (
                "The binding exactly matches the current authoritative specification and "
                "all applicable requirements have conformance evidence."
            ),
            "decisions": {
                "not_applicable": "the specification rule does not apply to the event",
                "blocked": (
                    "authority, binding, or complete conformance evidence is missing or "
                    "conflicting"
                ),
                "stale": (
                    "the bound specification identity, version, digest, scope, rule, or "
                    "revision changed"
                ),
                "satisfied": (
                    "the current specification binding and all conformance obligations "
                    "have sufficient evidence"
                ),
            },
        },
    },
    "implementation": {
        "core_invariant": (
            "Implementation must satisfy the complete applicable set of traceable design "
            "constraints and stay within declared system boundaries and contracts."
        ),
        "generate": {
            "required_inputs": (
                "applicable prompt, code, architecture, system-boundary, interface, and "
                "data-contract sources",
                "the specification authority and scope that govern those constraints",
            ),
            "artifact": (
                "a complete traceable design-constraint set with source, type, scope, "
                "summary, system boundaries, and interface and data contracts"
            ),
            "blocked_when": (
                "a required constraint source or authority is missing",
                "applicable constraints conflict without deterministic resolution",
                "the applicable scope, system boundary, or contract set is incomplete",
            ),
        },
        "enforce": {
            "obligation": (
                "Map every applicable design constraint to implementation evidence and "
                "prove that no contract or system boundary was violated."
            ),
            "evidence_requirements": (
                "current projection, rule, revision, target, and constraint-set binding",
                "one traceable evidence mapping for every applicable design constraint",
                "explicit interface, data-contract, and system-boundary checks",
            ),
            "sufficiency": (
                "Every applicable constraint is covered by matching evidence and no "
                "contract or system boundary is violated."
            ),
            "decisions": {
                "not_applicable": "the implementation rule does not apply to the event",
                "blocked": (
                    "an applicable constraint is missing evidence, a contract is violated, "
                    "or a system boundary is crossed"
                ),
                "stale": (
                    "the constraint set, source summary, scope, rule, revision, or target "
                    "changed"
                ),
                "satisfied": (
                    "all applicable constraints are mapped to sufficient current evidence "
                    "without contract or boundary violations"
                ),
            },
        },
    },
    "verification": {
        "core_invariant": (
            "Use scenarios, actual impact scope, and risk to select the minimum effective "
            "verification set that covers every affected boundary and user commitment."
        ),
        "generate": {
            "required_inputs": (
                "requirements and scenarios with preconditions, steps, and assertions",
                "the actual change, impact scope, risk, affected boundaries, and user "
                "commitments",
            ),
            "artifact": (
                "a minimum effective verification set with an impact-to-verification "
                "coverage mapping"
            ),
            "blocked_when": (
                "the scenario, actual impact scope, or risk is missing",
                "an affected boundary or user commitment has no selected verification",
                "an unrelated full suite is required without impact or risk justification",
            ),
        },
        "enforce": {
            "obligation": (
                "For every required verification item, provide repeatable steps, "
                "assertions, results, evidence, and a coverage conclusion."
            ),
            "evidence_requirements": (
                "current projection, rule, revision, target, impact scope, and risk binding",
                "steps, assertions, results, and repeatable evidence for every required item",
                "a coverage conclusion mapping every affected boundary and user commitment",
            ),
            "sufficiency": (
                "Every required verification passes with repeatable matching evidence and "
                "the coverage map contains every affected boundary and user commitment."
            ),
            "decisions": {
                "not_applicable": "the verification rule does not apply to the event",
                "blocked": (
                    "a required verification, assertion, result, repeatable evidence, or "
                    "coverage mapping is missing, failed, or incomplete"
                ),
                "stale": (
                    "the scenario, impact scope, risk, required set, rule, revision, or "
                    "target changed"
                ),
                "satisfied": (
                    "the minimum effective set passes and completely covers the current "
                    "affected boundaries and user commitments"
                ),
            },
        },
    },
    "delivery": {
        "core_invariant": (
            "Delivery must govern the exact target environment, lifecycle transition, "
            "artifact identity, admission gates, traceability, and rollback capability."
        ),
        "generate": {
            "required_inputs": (
                "target environment and current and target lifecycle stages",
                "artifact identity, version, and digest",
                "prerequisite stages, admission gates, traceability, and rollback conditions",
            ),
            "artifact": (
                "one target-environment by lifecycle-stage by artifact delivery contract "
                "with admission gates, prerequisites, traceability, and rollback requirements"
            ),
            "blocked_when": (
                "the environment, lifecycle stage, artifact identity, or gate is missing",
                "the requested transition skips or conflicts with a prerequisite stage",
                "required traceability or rollback conditions cannot be established",
            ),
        },
        "enforce": {
            "obligation": (
                "Match the exact artifact to the target environment and lifecycle stage, "
                "satisfy every admission gate, and prove traceability and rollback capability."
            ),
            "evidence_requirements": (
                "current projection, rule, revision, target environment, and lifecycle binding",
                "matching artifact identity, version, and digest",
                "complete admission, prerequisite, traceability, and rollback evidence",
            ),
            "sufficiency": (
                "The exact current artifact matches the environment and stage, all gates "
                "and prerequisites pass, and traceability and rollback are proven."
            ),
            "decisions": {
                "not_applicable": "the delivery rule does not apply to the event",
                "blocked": (
                    "the environment, stage, artifact, gate evidence, traceability, or "
                    "rollback capability is missing, mismatched, or invalid"
                ),
                "stale": (
                    "the environment, lifecycle stage, artifact identity or digest, rule, "
                    "revision, or target changed"
                ),
                "satisfied": (
                    "the exact artifact is admitted to the exact environment and stage by "
                    "complete current gate and rollback evidence"
                ),
            },
        },
    },
}
if tuple(DOMAIN_MINIMUM_CONTRACTS) != DOMAINS:
    raise RuntimeError("domain minimum contracts must match canonical domain order")

LAYER_RESPONSIBILITIES = {
    "skill": (
        "Interpret natural-language governance intent and submit typed governance requests."
    ),
    "scaffold": (
        "Discover facts, maintain authoritative governance state, project rules, "
        "validate internal consistency, and operate enforcement safeguards."
    ),
    "vertical_executor": (
        "Implement code, run tests, perform Git operations, release, and deploy software."
    ),
}

CELL_IDS = tuple(
    f"{audience}.{responsibility}.{domain}"
    for audience, responsibility, domain in product(
        AUDIENCES,
        RESPONSIBILITIES,
        DOMAINS,
    )
)

CELL_DIRECTIVES = {
    "maintainer.generate.specification": (
        "Define and publish canonical specification authority, priority, scope, version "
        "or digest, summary, and deterministic conflict-blocking semantics."
    ),
    "maintainer.generate.implementation": (
        "Define and publish the complete traceable design-constraint contract, including "
        "sources, types, scope, system boundaries, and interface and data contracts."
    ),
    "maintainer.generate.verification": (
        "Define and publish scenario- and impact-driven minimum effective verification "
        "selection with complete coverage mapping and no unjustified full-suite default."
    ),
    "maintainer.generate.delivery": (
        "Define and publish target-environment, lifecycle-stage, artifact, admission-gate, "
        "prerequisite, traceability, and rollback semantics."
    ),
    "maintainer.enforce.specification": (
        "Require maintainer artifacts to bind the current canonical specification and "
        "block missing, conflicting, nonconforming, or stale evidence."
    ),
    "maintainer.enforce.implementation": (
        "Require maintainer implementation evidence to map every applicable design "
        "constraint and block contract violations or system-boundary crossings."
    ),
    "maintainer.enforce.verification": (
        "Require repeatable evidence and complete impact-to-verification coverage before "
        "acceptance, blocking failed, missing, insufficient, or stale results."
    ),
    "maintainer.enforce.delivery": (
        "Require the exact artifact, environment, lifecycle stage, admission evidence, "
        "traceability, and rollback capability before distribution."
    ),
    "consumer.generate.specification": (
        "Resolve and deterministically project one source-backed specification authority "
        "with priority, scope, version or digest, summary, and conflict outcome."
    ),
    "consumer.generate.implementation": (
        "Resolve and deterministically project the complete applicable set of traceable "
        "design constraints, system boundaries, and interface and data contracts."
    ),
    "consumer.generate.verification": (
        "Use requirements, scenarios, actual impact scope, and risk to deterministically "
        "project the minimum effective verification set and coverage mapping."
    ),
    "consumer.generate.delivery": (
        "Deterministically project the exact environment, lifecycle transition, artifact, "
        "admission gates, prerequisites, traceability, and rollback contract."
    ),
    "consumer.enforce.specification": (
        "Require the governed result to bind and conform to the current specification "
        "identity and version, rejecting missing, conflicting, or stale evidence."
    ),
    "consumer.enforce.implementation": (
        "Require evidence for every applicable design constraint and reject contract "
        "violations, system-boundary crossings, incomplete mappings, or stale evidence."
    ),
    "consumer.enforce.verification": (
        "Require every selected verification item, assertion, result, and affected-boundary "
        "coverage conclusion to have repeatable current evidence."
    ),
    "consumer.enforce.delivery": (
        "Admit only the exact artifact to the exact environment and lifecycle stage when "
        "all gates, prerequisites, traceability, and rollback evidence are current."
    ),
}
if tuple(CELL_DIRECTIVES) != CELL_IDS:
    raise RuntimeError("fixed Cell directives must match canonical Cell order")

RULE_ID_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
RULE_ID_MAX_LENGTH = 64


def cell_id(audience: str, responsibility: str, domain: str) -> str:
    """Return the canonical ID for one fixed meta-model cell."""

    return f"{audience}.{responsibility}.{domain}"


def consumer_rule_cell_ids(domain: str) -> tuple[str, str]:
    """Return the generate/enforce views for one consumer governance rule."""

    if domain not in DOMAINS:
        raise ValueError(f"unknown governance domain: {domain}")
    return (
        cell_id("consumer", "generate", domain),
        cell_id("consumer", "enforce", domain),
    )
