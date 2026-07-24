# Forward Evaluation Workspace

本目录属于开发仓库，不会进入 Skill 发布包。评测运行器只把每个 Case 的
`Agent-visible input` 区段交给独立 Agent；`Evaluator-only rubric` 与
`Expected evidence` 必须留在评测侧，防止把隐藏结论泄漏给被测 Agent。

正式 P5 运行前必须记录模型、Skill 摘要、Fixture 摘要和原始输出。失败结果不能
只保留评分，必须同时保存原始输出、Diff、Evidence 与 blocker codes。

