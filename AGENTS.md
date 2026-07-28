<!-- ai-coding-harness:start -->
# AI Coding Harness 2.0

- Treat this marked block as the repository Harness entrypoint.
- Use `$harness` for governed local work, explicit `git commit`, Issue operations, Test, Build, CI, and controlled delivery.
- Read `.harness/harness.yaml` and run `sdd-harness inspect --json` before a governed action.
- Keep ordinary local work continuous and use only the minimum sufficient T0-T3 validation.
- Call actions by their source-backed `action_id`; do not invent or override an invocation.
- Treat project policy as versioned behavior and a task decision as one task or one exact action only.
- Require an independent task decision and upstream platform gates for every controlled action.
- Stop with stable blocker codes when runtime, projection, source, scope, binding, branch, target, or evidence cannot be verified.
<!-- ai-coding-harness:end -->
