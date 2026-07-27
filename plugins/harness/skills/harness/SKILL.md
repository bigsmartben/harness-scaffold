---
name: harness
description: Generate, update, inspect, or enforce the current repository's deterministic Agent governance projection.
---

# Harness

## Contract

- Input: repository snapshot, source-backed facts, audience/subdomain lane, Work Grant, and `action_id`.
- Output: validated projection artifacts, Gate Decision, or digest-bound Action Evidence.
- Boundary: never infer permission from tool availability and never accept arbitrary invocation overrides.
- Failure: return canonical blocker codes and `HANDOFF_REQUIRED`; preflight failure writes nothing.

## Generate

1. Read `AGENTS.md`, `.codex/config.toml`, and `.harness/governance/projection.lock.json`.
2. Use `repo_mapper` for deterministic facts.
3. Run one read-only `governance_projector` per audience × subdomain lane.
4. Wait for all lanes, then use `projection_reconciler` and `governance_validator`.
5. Present one exact Plan digest and write scope.
6. Publish only the unchanged confirmed Plan through the single writer.

## Enforce

1. Resolve the requested `action_id`; do not accept a command string.
2. Bind the current projection and Work Grant.
3. Run G0-G5 before invocation.
4. Give one non-overlapping ownership scope to `governed_worker`.
5. Use `evidence_verifier` for G6-G7.
6. Report only accepted conclusions.

If Plugin/Core/Schema compatibility is missing or the projection is stale, stay
in bootstrap-only mode and permit only read-only inspection and projection repair.
