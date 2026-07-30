"""The single normative source for the fixed Harness 3.0 meta-model."""

from __future__ import annotations

from itertools import product


SCHEMA_VERSION = "3.0.1"
CORE_VERSION = SCHEMA_VERSION
CONTRACT_VERSION = SCHEMA_VERSION
PROJECTION_COMPILER_VERSION = SCHEMA_VERSION

AUDIENCES = ("maintainer", "consumer")
RESPONSIBILITIES = ("generate", "enforce")
DOMAINS = ("specification", "implementation", "verification", "delivery")

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
        "Define and deterministically emit the canonical specification Cell."
    ),
    "maintainer.generate.implementation": (
        "Define and deterministically emit the canonical implementation Cell."
    ),
    "maintainer.generate.verification": (
        "Define and deterministically emit the canonical verification Cell."
    ),
    "maintainer.generate.delivery": (
        "Define and deterministically emit the canonical delivery Cell."
    ),
    "maintainer.enforce.specification": (
        "Strictly validate the canonical specification Cell and reject model drift."
    ),
    "maintainer.enforce.implementation": (
        "Strictly validate the canonical implementation Cell and reject model drift."
    ),
    "maintainer.enforce.verification": (
        "Strictly validate the canonical verification Cell and reject model drift."
    ),
    "maintainer.enforce.delivery": (
        "Strictly validate the canonical delivery Cell and reject model drift."
    ),
    "consumer.generate.specification": (
        "Deterministically project validated specification guidance for the repository."
    ),
    "consumer.generate.implementation": (
        "Deterministically project validated implementation guidance for the repository."
    ),
    "consumer.generate.verification": (
        "Deterministically project validated verification guidance for the repository."
    ),
    "consumer.generate.delivery": (
        "Deterministically project validated delivery guidance for the repository."
    ),
    "consumer.enforce.specification": (
        "Strictly validate repository specification guidance against the canonical contract."
    ),
    "consumer.enforce.implementation": (
        "Strictly validate repository implementation guidance against the canonical contract."
    ),
    "consumer.enforce.verification": (
        "Strictly validate repository verification guidance against the canonical contract."
    ),
    "consumer.enforce.delivery": (
        "Strictly validate repository delivery guidance against the canonical contract."
    ),
}
if tuple(CELL_DIRECTIVES) != CELL_IDS:
    raise RuntimeError("fixed Cell directives must match canonical Cell order")

RULE_ID_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
RULE_ID_MAX_LENGTH = 64


def cell_id(audience: str, responsibility: str, domain: str) -> str:
    """Return the canonical ID for one fixed meta-model cell."""

    return f"{audience}.{responsibility}.{domain}"
