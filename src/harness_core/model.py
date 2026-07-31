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
        "Discover repository facts and existing governance sources, then read, "
        "normalize, classify, calibrate, and deterministically project governance rules."
    ),
    "enforce": (
        "Generate and operate internal governance safeguards that create typed "
        "obligations and verify external evidence for projected rules."
    ),
}

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
        "Define specification governance semantics and publish their canonical "
        "maintainer sources."
    ),
    "maintainer.generate.implementation": (
        "Generate implementation contracts and artifacts from accepted governance semantics."
    ),
    "maintainer.generate.verification": (
        "Generate repeatable verification criteria that trace to the normative contract."
    ),
    "maintainer.generate.delivery": (
        "Generate version-aligned distribution guidance and release contract artifacts."
    ),
    "maintainer.enforce.specification": (
        "Operate safeguards that keep normative specification sources mutually consistent."
    ),
    "maintainer.enforce.implementation": (
        "Operate safeguards that require maintainer implementation evidence to satisfy "
        "accepted contracts."
    ),
    "maintainer.enforce.verification": (
        "Operate safeguards that require repeatable verification evidence before acceptance."
    ),
    "maintainer.enforce.delivery": (
        "Operate safeguards that require version and artifact integrity before distribution."
    ),
    "consumer.generate.specification": (
        "Discover and calibrate source-backed specification rules, then project them "
        "deterministically."
    ),
    "consumer.generate.implementation": (
        "Discover and calibrate source-backed implementation rules, then project them "
        "deterministically."
    ),
    "consumer.generate.verification": (
        "Discover and calibrate source-backed verification rules, then project them "
        "deterministically."
    ),
    "consumer.generate.delivery": (
        "Discover and calibrate source-backed delivery rules, then project them "
        "deterministically."
    ),
    "consumer.enforce.specification": (
        "Create specification obligations and verify typed evidence against active "
        "projected rules."
    ),
    "consumer.enforce.implementation": (
        "Create implementation obligations and verify typed evidence against active "
        "projected rules."
    ),
    "consumer.enforce.verification": (
        "Create verification obligations and verify typed evidence against active "
        "projected rules."
    ),
    "consumer.enforce.delivery": (
        "Create delivery obligations and verify typed evidence against active "
        "projected rules."
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
