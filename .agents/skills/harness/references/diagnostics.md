# Diagnostics

Use diagnostics only when normal work is blocked or the user asks for detail.

1. Run `sdd-harness inspect --json`.
2. Explain the first actionable blocker in plain language.
3. Distinguish repository fact, deterministic result, and inference.
4. Show projection, digest, coverage, or evidence identifiers only when they
   help resolve the blocker.
5. Never repair an invalid governance input silently.

Plugin, Hook, and MCP availability is defense-in-depth status, not the
repository governance source of truth.

