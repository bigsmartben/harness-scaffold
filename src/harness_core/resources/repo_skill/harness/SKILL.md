---
name: harness
description: Govern repository work in Codex App or Codex CLI with the installed sdd-harness runtime. Use for $harness, local implementation, git commit, Issue planning or writes, Test, Build, CI, Push, Pull Request, Merge, Publish, Release, Deploy, project policy, task decisions, and evidence-backed diagnostics.
---

# Harness

Use the repository's Harness projection to keep local work continuous and
controlled actions exact.

## Contract

- Input: the user's goal, current repository facts, project policy, and any
  action-specific decision.
- Output: the requested repository result plus the minimum sufficient
  validation summary, or a stable blocker code.
- Boundary: never treat tool availability as permission, never widen scope
  silently, and never reuse one action's decision for another action.
- Failure: fail closed when the runtime, projection, source, scope, binding,
  branch, target, or evidence cannot be verified.

## Start

1. Read `AGENTS.md` and `.harness/harness.yaml`.
2. Run `sdd-harness inspect --json`.
3. If status is `entrypoint-ready` and the user wants to generate or refresh
   repository governance, use the Projection route. The only allowed pending
   blocker at this point is `GOVERNANCE_SOURCE_MISSING`.
4. For every other non-empty `blocker_codes` result, stop and use the
   diagnostics route. Do not repair governance outside the user-confirmed task
   scope.
5. Keep internal artifact names out of normal user summaries.

## Route

| Intent | Reference |
|---|---|
| Generate, refresh, or explain repository governance | [references/projection.md](references/projection.md) |
| Inspect, edit, Test, or Build locally | [references/local-work.md](references/local-work.md) |
| Explicit `git commit` or equivalent | [references/commit.md](references/commit.md) |
| Plan or create a local/remote Issue | [references/issues.md](references/issues.md) |
| Push, PR, Merge, Publish, Release, or Deploy | [references/controlled-delivery.md](references/controlled-delivery.md) |
| Explain a blocker or inspect internal evidence | [references/diagnostics.md](references/diagnostics.md) |

Load only the directly relevant reference.

## User language

Use only these user-facing decision names:

- Project policy / 项目策略: versioned behavior for later tasks.
- Task decision / 本次决定: one task or one exact action only.

Default to a task decision. Create or change project policy only when the user
clearly asks for lasting behavior.
