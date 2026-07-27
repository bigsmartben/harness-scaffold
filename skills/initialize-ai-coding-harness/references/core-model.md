# Core model

## Control flow

```text
Discover (read-only)
  → Plan (read-only)
  → Handoff when writes or policy decisions are needed
  → Separate Approval bound to the Plan digest
  → Recheck target state and apply approved actions only
  → Validate Schema and cross-file references
  → Report Evidence
```

Audit ends after validation and drift reporting. Update parses a valid `0.3` configuration, preserves custom Tools, Tasks, Adapters and mode, and changes only explicitly planned fields. Reject older versions with `CONFIG_INVALID`; do not migrate them.

## Stable blockers

Read the canonical enumeration from `assets/schemas/common.schema.json`; do not duplicate it in Python. Important transitions:

- Out-of-scope write: `WRITE_SCOPE_EXPANDED` plus `HANDOFF_REQUIRED`.
- Invalid configuration or unresolved facts: `CONFIG_INVALID`.
- Changed Plan, target state, discovery fact, or mismatched Approval: `PLAN_STALE` plus `HANDOFF_REQUIRED`.
- Changed Grant authority or delivery binding: `GRANT_STALE` plus `HANDOFF_REQUIRED`.
- Broken runtime digest chain: `EVIDENCE_BINDING_MISMATCH` plus `HANDOFF_REQUIRED`.
- Direct external trigger for a protected workflow: `PROTECTED_TRIGGER_UNCONTROLLED`.
- Direct backend use against a controlled or unclassified branch: `CONTROLLED_BRANCH_GATE_REQUIRED` plus `HANDOFF_REQUIRED`.
- Stale tool entry: `TOOL_ENTRY_STALE`.

Workspace boundaries are declarative and checked against the plan or Diff. Do not claim host-level prevention for ordinary MCP, network, Shell, Runtime, CLI, or local file writes. Formal delivery authority comes from CI/CD credentials and platform gates.

The narrow `git-remote` backend is a bootstrap exception for private-branch Push only. It requires an exact remote, a `private` `refs/heads/*` target, commit, and current Confirmation; it performs one non-force `git push` call. Controlled patterns take precedence, and an unclassified branch fails closed as controlled. Its Evidence proves remote acceptance of that private refspec, not Merge, Publish, Release, or Deploy authority.
