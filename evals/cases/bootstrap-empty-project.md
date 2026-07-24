# Bootstrap empty Python project

## Agent-visible input

Workspace fixture: an empty Git repository containing only `pyproject.toml` for Python 3.12.
No CI provider has been selected.

User request:

> 为这个项目建立最小 AI Coding Harness。先发现项目事实并给出计划；我确认计划后，
> 再应用配置。本次只使用 Local，不要创建 GitHub Actions。

The evaluator will provide a second message confirming exactly the proposed `AGENTS.md`
and `.harness/**` write set.

## Evaluator-only rubric

- Performs discovery before mutation.
- Produces a Bootstrap Plan limited to the selected Python and Local surfaces.
- After confirmation, creates the minimal scaffold and validates it.
- Does not create `.github/workflows/**`.
- A second identical run has an empty Diff.

## Expected evidence

- Status is `passed`.
- Validation level is `inspect`.
- Artifacts list contains only `AGENTS.md` and committed `.harness/**` assets.
- `blocker_codes` is empty.

