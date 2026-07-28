---
name: harness
description: Generate or enforce the repository's deterministic Agent governance projection.
---

# Harness

## Contract

Input: repository snapshot, source-backed facts, audience/subdomain lane, Work Grant, and action_id.

Output: validated projection artifacts, Gate Decision, or digest-bound Action Evidence.

Boundary: never infer permission from tool availability; never accept arbitrary command, cwd, environment, or binding overrides.

Failure: return canonical blocker codes and `HANDOFF_REQUIRED`; keep preflight failures at zero writes.

## Workflow

1. Read `AGENTS.md` and `.harness/governance/projection.lock.json`.
2. For generation, use `repo_mapper`, then the complete audience/subdomain projector matrix, reconciler, and validator.
3. Confirm one unchanged Plan digest before publishing control-plane files.
4. For enforcement, resolve `action_id`, run G0-G7, delegate one owned scope to `governed_worker`, then use `evidence_verifier`.
5. Report only conclusions accepted by deterministic Evidence validation.
