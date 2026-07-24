# Core model

## Control flow

```text
Discover (read-only)
  → Plan (read-only)
  → Handoff when writes or policy decisions are needed
  → Apply approved actions only
  → Validate Schema and cross-file references
  → Report Evidence
```

Audit ends after validation and drift reporting. Update uses the same discovery and validation but produces a minimal repair Plan.

## Stable blockers

Read the canonical enumeration from `assets/schemas/common.schema.json`; do not duplicate it in Python. Important transitions:

- Out-of-scope write: `WRITE_SCOPE_EXPANDED` plus `HANDOFF_REQUIRED`.
- Invalid configuration or unresolved facts: `CONFIG_INVALID`.
- Direct external trigger for a protected workflow: `PROTECTED_TRIGGER_UNCONTROLLED`.
- Stale tool entry: `TOOL_ENTRY_STALE`.

Workspace boundaries are declarative and checked against the plan or Diff. Do not claim host-level prevention for ordinary MCP, network, Shell, Runtime, CLI, or local file writes. Formal delivery authority comes from CI/CD credentials and platform gates.
