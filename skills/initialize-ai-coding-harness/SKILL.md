---
name: harness
description: Generate and enforce repository-local Agent governance in Codex App or Codex CLI. Use for $harness, governance projection, Bootstrap, Adopt, Update, governed Work, Test, Build, CI, Merge, Publish, Release, Deploy, and Evidence validation.
---

# Harness

Harness is Agent-bound orchestration plus a deterministic contract kernel. Read `AGENTS.md`, `.codex/config.toml`, the current projection lock, and this Skill before acting.

## Route

| Intent | Route | Reference |
|---|---|---|
| Existing repository | Adopt / 接管 | [references/adopt-existing-project.md](references/adopt-existing-project.md) |
| New repository | Bootstrap / 初始化 | [references/bootstrap-new-project.md](references/bootstrap-new-project.md) |
| Generate, update, inspect, or diagnose governance | Core / 核心模型 | [references/core-model.md](references/core-model.md) |
| Resolve a repository Action | Registry / 行为绑定 | [references/tool-registry.md](references/tool-registry.md) |
| Work, Test, Build, Merge, Publish, Release, Deploy | Enforcement / 执行 | [references/delivery-model.md](references/delivery-model.md) |
| Validate external authority or Evidence | Platform / 平台门禁 | [references/github-platform-gates.md](references/github-platform-gates.md) |

Load only the directly linked Reference needed for the active route. Load Schema only for deterministic validation.

## Generate

1. Spawn `repo_mapper` to call deterministic discovery and return source-backed facts.
2. Spawn read-only `governance_projector` instances for every required Audience × Subdomain.
3. Wait for every required result; then use `projection_reconciler` without silently resolving conflicts.
4. Use `governance_validator` to run Schema and cross-file validation.
5. Present one exact Plan and one aggregated confirmation only when governance Scope changes.
6. Publish with a plan-bound single writer. Never treat Agent output as final SSOT.

## Enforce

1. Accept only `projection_id`, Work Grant, `action_id`, Audience, Scope, and typed parameters.
2. Resolve the exact binding; reject `command`, `argv`, `cwd`, environment, Scope, or Postcondition overrides.
3. Run G0–G5 before invocation.
4. Use one `governed_worker` for the resolved ownership.
5. Use `evidence_verifier` for Postconditions, G6, G7, and digest-chain validation.
6. Report a conclusion only when deterministic Evidence accepts it.

## Stop

Fail closed when a source, matrix cell, Agent contract, inheritance edge, Action classification, unique binding, precondition, dispatcher path, Postcondition, Evidence link, or post-run snapshot cannot be proven. Return the canonical blocker codes from `governance.schema.json`; add `HANDOFF_REQUIRED` when human or platform authority is required.

Never fall back to a generic Agent, infer permission from tool presence, let parallel writers overlap, use per-tool confirmation as a substitute for missing governance, or claim `enforced` while an undeclared bypass remains possible.
