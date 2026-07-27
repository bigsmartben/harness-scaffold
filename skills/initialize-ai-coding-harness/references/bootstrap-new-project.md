# Bootstrap a new project

1. Discover verified Python, Node, or workspace-declared monorepo units without writing.
2. If no project type is supported, return `CONFIG_INVALID` with missing facts.
3. Default to the minimal Local backend.
4. Present GitHub Actions as optional; create a workflow only when the user selects it in the approved Plan.
5. Create the minimal `AGENTS.md` and `.harness/` files.
6. Validate all Schema and cross-file references.
7. Repeat the same approved operation to verify idempotence.

Example: a Python project whose `pyproject.toml` declares pytest receives `test:python-root`; it does not receive a guessed Node Task or GitHub Actions workflow.
