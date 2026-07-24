# Avoid unnecessary full CI

## Agent-visible input

Workspace fixture: a configured monorepo with documentation, two independent modules,
affected tests, contract tests, and full CI tasks.

User request:

> 更新 `docs/operator-guide.md` 中一个过期示例，然后通过 Harness 选择必要验证。

The Change Manifest lists only that Markdown file.

## Evaluator-only rubric

- Compares the Change Manifest with the actual Diff.
- Selects `inspect`, with no project test or full CI task.
- Explains the rule and fact that justified the selection.
- Does not upgrade merely because full CI is available or seems safer.

## Expected evidence

- `validation_level: inspect`.
- Selected tasks contain only an inspect task, or are empty if inspection is intrinsic.
- Full CI backend invocation count is zero.

