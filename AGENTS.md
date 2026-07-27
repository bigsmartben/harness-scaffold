<!-- ai-coding-harness:start -->
# AI Coding Harness

- Treat this marked block as the Harness governance entrypoint; preserve every instruction outside the markers.
- Read workspace and branch policy from `.harness/`, and query `.harness/tools.yaml` before invoking a Runtime, CLI, Shell, MCP, API, or repository script.
- Limit Harness-managed execution to the local workspace and branches classified as `private` by `.harness/boundaries.yaml`.
- Treat controlled and unclassified branches as outside direct Harness execution. Require a strong, current confirmation and CI/CD platform gates; otherwise stop with `CONTROLLED_BRANCH_GATE_REQUIRED` and `HANDOFF_REQUIRED`.
- Route Test, Build, CI, Push, Merge, Publish, Release, and Deploy semantics through `task_ref`; run only explicitly auto-allowed `routine` Tasks automatically.
- Stop with the configured blocker codes when scope, bindings, branch classification, or platform Evidence do not match.
<!-- ai-coding-harness:end -->
