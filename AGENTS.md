# Maintainer Issue Policy

- Use `bigsmartben/harness-scaffold` GitHub Issues as the only SSOT for maintainer iteration plans, status, checklists, and acceptance results.
- Do not create or maintain editable local Issue mirrors; local documentation may only link to the authoritative GitHub Issue.
- Restate the exact repository, Issue number, and intended mutation before creating, updating, commenting on, closing, or reopening a GitHub Issue.

<!-- ai-coding-harness:start -->
# Harness 4 Maintainer Repository

- This repository develops and distributes Harness; it is not a consumer initialization target.
- Close the maintainer loop through this root `AGENTS.md`, the canonical sources, and repository tests; do not bootstrap this repository as its own Harness consumer or expect a generated consumer Skill at the repository root.
- Reserve `harness load` and its generated `.harness/` and `.agents/skills/harness/` artifacts for external or temporary consumer repositories, where they form the consumer governance loop.
- Do not run `harness load`, `operate`, `cancel`, or `inspect` against the repository root.
- Exercise the four public CLI commands only against temporary consumer repositories in tests and distribution smoke checks.
- Treat `src/harness_core/model.py`, `src/harness_core/resources/schemas/`, and `src/harness_core/resources/repo_skill/harness/SKILL.md` as the maintainer sources.
- Keep the public CLI limited to `load`, `operate`, `cancel`, and `inspect`.
- Treat the fixed Audience × Responsibility × Governance Domain model as immutable.
- Treat the authoritative rule state as the only consumer rule SSOT; projections and enforcement decisions are derived.
<!-- ai-coding-harness:end -->
