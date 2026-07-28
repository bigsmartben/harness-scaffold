# Forward Evaluation Workspace

本目录属于开发仓库，不会进入 Skill 发布包。评测运行器只把每个 Case 的
`Agent-visible input` 区段交给独立 Agent；`Evaluator-only rubric` 与
`Expected evidence` 必须留在评测侧，防止把隐藏结论泄漏给被测 Agent。

每次正式回归运行必须记录模型、Skill 摘要、Fixture 摘要和原始输出。失败结果不能
只保留评分，必须同时保存原始输出、Diff、Evidence 与 blocker codes。

`results/` 保存本机原始产物并由 `.gitignore` 排除；`runs/` 保存可提交的运行摘要、
模型与 Skill 摘要、Case 分数及原始产物摘要。

当前权威可观察行为来自 `uc.md`，自动化覆盖映射保存在 `coverage.yaml`。
Harness 2.0 不保留历史版本评测或兼容基线。
