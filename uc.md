# Harness 2.0 可观察用户用例

版本：`2.0.0`

| 用例 | 输入实例 | 可观察输出 |
|---|---|---|
| UC-001 初始化 | `sdd-harness init . --yes` | AGENTS、完整仓库 Skill、项目策略、有效投影；默认无 Hook |
| UC-002 四域覆盖 | 当前仓库事实 | 恰好 16 条 Coverage Record；Cell ID 不重复 |
| UC-003 本地修改 | “修改解析器” | 不询问普通工具权限，选择 T0/T1/T2/T3 |
| UC-004 项目策略 | “以后 Issue 使用 GitHub” | 版本化配置变化，新 `projection_id` |
| UC-005 本次决定 | “这次提交 `src/a.py`” | 只绑定精确 Commit；工作区变化后失效 |
| UC-006 选择性 Commit | `a.py` + 无关已暂存 `b.py` | 提交只含 `a.py`，`b.py` 暂存不变 |
| UC-007 部分暂存 | 同一文件 staged + unstaged | `PARTIAL_STAGING_UNSUPPORTED` |
| UC-008 Local Issue | Consumer 默认 Provider | 写入 `.harness/issues` |
| UC-009 Remote Issue | 精确 Repo / Title / Body | 只准备 Provider Request；失败不回退 |
| UC-010 Controlled Branch | `refs/heads/main` 直接写/Commit | `CONTROLLED_BRANCH_GATE_REQUIRED` |
| UC-011 历史配置 | 非 2.0 `harness.yaml` | 零写入返回 `HARNESS_RUNTIME_INCOMPATIBLE` |
| UC-012 可选 Hook | `init --with-hooks` | 增加纵深防御，治理 SSOT 不变 |
| UC-013 项目策略应用 | 摘要未变化的 Policy Plan | 原子刷新投影；旧本次决定失效 |
| UC-014 结束本次决定 | `decision-end --task-id task-22` | 只删除被忽略的对应运行态文件 |
| UC-015 受控交付 | PR / Merge / Publish / Release / Deploy | 平台门禁 + 独立决定 + 单次 Provider 调用 + 精确回执 |
| UC-016 交付失败 | Provider 异常或回执不完整 | 失败关闭，不回退其他 Provider 或本地动作 |
