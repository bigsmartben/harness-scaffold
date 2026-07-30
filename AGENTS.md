# Maintainer Issue Policy

- Use `bigsmartben/harness-scaffold` GitHub Issues as the only SSOT for maintainer iteration plans, status, checklists, and acceptance results.
- Do not create or maintain editable local Issue mirrors; local documentation may only link to the authoritative GitHub Issue.
- Restate the exact repository, Issue number, and intended mutation before creating, updating, commenting on, closing, or reopening a GitHub Issue.

<!-- ai-coding-harness:start -->
# Harness 3.0 Maintainer Repository

- This repository develops and distributes Harness; it is not a consumer initialization target.
- Do not run `sdd-harness init`, `project`, `validate`, or `inspect` against the repository root.
- Exercise the four public CLI commands only against temporary consumer repositories in tests and distribution smoke checks.
- Treat `src/harness_core/model.py`, `src/harness_core/resources/schemas/`, and `src/harness_core/resources/repo_skill/harness/SKILL.md` as the maintainer sources.
- Keep the public CLI limited to `init`, `project`, `validate`, and `inspect`.
- Treat the fixed Audience × Responsibility × Governance Domain model as immutable.
- Treat every `rule_instances` entry as guidance only; it cannot authorize, block, select, or execute an operation.
- Reject v1/v2 configuration and artifacts without writing, migrating, completing, deleting, or falling back.
<!-- ai-coding-harness:end -->
