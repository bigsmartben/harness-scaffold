# Maintainer Issue Policy

- Use `bigsmartben/harness-scaffold` GitHub Issues as the only SSOT for maintainer iteration plans, status, checklists, and acceptance results.
- Do not create or maintain editable local Issue mirrors under `.harness/issues/`; local documentation may only link to the authoritative GitHub Issue.
- Restate the exact repository, Issue number, and intended mutation before creating, updating, commenting on, closing, or reopening a GitHub Issue.

<!-- ai-coding-harness:start -->
# AI Coding Harness

- Treat this block as the Harness orchestration entrypoint.
- Current governance projection: `sha256:f62c5bf0ee311f5bab85c5759afa5d507790fac076849646b19c2f3330c32a32`.
- Read `.harness/governance/projection.lock.json` before governed work.
- Use `$harness` for generation, update, action routing, or Evidence verification.
- Spawn only the six project roles declared in `.codex/agents/`; do not fall back to a generic agent.
- Projection lanes are read-only. Publish and code writes use a single writer or non-overlapping ownership.
- Submit only `projection_id`, Work Grant, `action_id`, scope, and typed parameters.
- Stop on any stable blocker code. Agent summaries, Memory, and Transcript are not authorization or Evidence.
<!-- ai-coding-harness:end -->
