"""Deterministic text-template helpers shared by planning and apply."""

from __future__ import annotations

import re


HARNESS_MARKER_START = "<!-- ai-coding-harness:start -->"
HARNESS_MARKER_END = "<!-- ai-coding-harness:end -->"
PLACEHOLDER = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


def render_template(text: str, context: dict[str, str]) -> str:
    """Render simple named placeholders and reject missing values."""

    missing: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in context:
            missing.add(key)
            return match.group(0)
        return str(context[key])

    rendered = PLACEHOLDER.sub(replace, text)
    if missing:
        raise ValueError(f"missing template values: {', '.join(sorted(missing))}")
    return rendered


def replace_marked_block(current: str, block: str) -> str:
    """Insert or replace the one paired Harness block without touching other text."""

    has_start = HARNESS_MARKER_START in current
    has_end = HARNESS_MARKER_END in current
    if has_start != has_end:
        raise ValueError("Harness marker pair is incomplete")
    if not has_start:
        prefix = f"{current.rstrip()}\n\n" if current.strip() else ""
        return f"{prefix}{block.lstrip()}"

    start = current.index(HARNESS_MARKER_START)
    end = current.index(HARNESS_MARKER_END, start) + len(HARNESS_MARKER_END)
    if current.find(HARNESS_MARKER_START, start + 1) != -1:
        raise ValueError("multiple Harness marker blocks are not allowed")
    return f"{current[:start]}{block.rstrip()}{current[end:]}"
