<!-- ai-coding-harness:start -->
# AI Coding Harness

- Read project delivery configuration from `.harness/`.
- Query `.harness/tools.yaml` before invoking a Runtime, CLI, Shell, MCP, API, or repository script.
- Route Test, Build, CI, Push, Merge, Publish, Release, and Deploy semantics through `task_ref`, regardless of invocation channel.
- Run only explicitly auto-allowed `routine` Tasks automatically; request current confirmation for `expensive` and `critical`.
- Stop and request Handoff when the write scope expands.
- Require current confirmation for every Push, Merge, Publish, Release, or Deploy, then rely on CI/CD platform gates for formal authority.
- Do not claim Harness authorization or enforcement for ordinary tools, network access, or local file writes.
<!-- ai-coding-harness:end -->
