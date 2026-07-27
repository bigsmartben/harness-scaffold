# Forward Evaluation Workspace

本目录属于开发仓库，不会进入 Skill 发布包。评测运行器只把每个 Case 的
`Agent-visible input` 区段交给独立 Agent；`Evaluator-only rubric` 与
`Expected evidence` 必须留在评测侧，防止把隐藏结论泄漏给被测 Agent。

每次正式回归运行必须记录模型、Skill 摘要、Fixture 摘要和原始输出。失败结果不能
只保留评分，必须同时保存原始输出、Diff、Evidence 与 blocker codes。

`results/` 保存本机原始产物并由 `.gitignore` 排除；`runs/` 保存可提交的运行摘要、
模型与 Skill 摘要、Case 分数及原始产物摘要。当前正式运行记录见
[`runs/p3-forward-eval-20260724.yaml`](runs/p3-forward-eval-20260724.yaml)。该记录是
`0.3` 的 P2/P3 契约与 Skill 回归门禁，不代表 P4 已完成真实 GitHub 验收，也不启动
P5 安装或发布。
