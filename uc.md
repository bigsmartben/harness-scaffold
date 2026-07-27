# Harness 可观察用户用例

版本：`1.0.0`

每个用例都给出输入、输出、边界和失败语义，并映射到[治理规范](docs/specification.md)。

## UC-001：从仓库事实生成投影

- 规则：GG-001、GG-002
- 输入：包含 `pyproject.toml` 与已登记测试任务的仓库。
- 输出：带来源摘要的 Facts 和 `test:contracts` Action 节点。
- 边界：PATH 中额外工具不得生成规则。
- 失败：来源缺失返回 `GOVERNANCE_SOURCE_MISSING`。
- 验证：相同输入的 Canonical JSON 和摘要相同。

## UC-002：覆盖两类用户和六个子域

- 规则：GG-003
- 输入：一个固定 Repository Snapshot。
- 输出：`maintainer`、`consumer` × 六个 Subdomain 的 12 个投影切片。
- 边界：一个行为可属于多个子域，但枚举不能扩成第七类。
- 失败：缺格返回 `GOVERNANCE_COVERAGE_INCOMPLETE`。
- 验证：矩阵集合与封闭枚举精确相等。

## UC-003：重复初始化为空 Diff

- 规则：GG-004
- 输入：同版本、同事实、同声明，连续两次 `sdd-harness init --yes`。
- 输出：第一次发布控制面，第二次 Action 列表为空。
- 边界：保留用户自有 `AGENTS.md` 内容。
- 失败：预检冲突时零写入。
- 验证：两次 `projection_id` 相同，第二次没有文件变化。

## UC-004：归并冲突失败关闭

- 规则：GG-005
- 输入：同一 `action_id` 的两个互斥 Binding。
- 输出：包含所有冲突的 Reconciliation Result。
- 边界：Reconciler 不能根据偏好选一个。
- 失败：`GOVERNANCE_CONFLICT` 与 `TOOL_BINDING_AMBIGUOUS`。
- 验证：发布目录保持不变。

## UC-005：主 Agent 等待完整 Agent 图

- 规则：AG-001
- 输入：需要 2 × 6 投影的生成任务。
- 输出：等待所有必需只读结果后才进入验证和发布。
- 边界：候选 Artifact 不是最终 SSOT。
- 失败：未等待完整结果返回 `AGENT_BINDING_UNAVAILABLE`。
- 验证：编排状态机不能从 incomplete 直接到 publish。

## UC-006：拒绝不受信的自定义 Agent

- 规则：AG-002、AG-003
- 输入：缺失、格式无效或没有受管标记的角色 TOML。
- 输出：完整角色诊断。
- 边界：TOML 只能收紧默认 Sandbox，不能提升父权限。
- 失败：`AGENT_ROLE_CONTRACT_INVALID` 或 `AGENT_CONFIGURATION_UNTRUSTED`。
- 验证：不生成通用 Agent 回退，也不写治理文件。

## UC-007：并行写入必须互斥

- 规则：AG-004
- 输入：两个 Worker 请求修改同一文件。
- 输出：改为单一 Worker 或互不重叠的 ownership。
- 边界：只读投影可并行。
- 失败：无法证明不重叠时停止并 `HANDOFF_REQUIRED`。
- 验证：调度器拒绝重叠 Scope。

## UC-008：常规测试自动过门禁

- 规则：GE-001、CF-001
- 输入：投影内的 `test:contracts` 与有效 Work Grant。
- 输出：自动通过 G0–G7 并产生 Evidence。
- 边界：不逐命令确认。
- 失败：任一 Gate 失败即不接受“测试通过”。
- 验证：Evidence 记录八个 Gate 结果。

## UC-009：Agent 不能覆盖调用绑定

- 规则：GE-002、GE-003
- 输入：携带 `command`、`argv`、`cwd` 或 `env` 的 Action Request。
- 输出：不调用 Runner。
- 边界：只接受 Schema 允许的类型化参数。
- 失败：`INVOCATION_BYPASS_ATTEMPT`。
- 验证：Adapter 调用次数为零。

## UC-010：Evidence 才能支撑结论

- 规则：GE-004
- 输入：退出码为零但缺少 Postcondition 或摘要绑定的执行结果。
- 输出：拒绝权威结论。
- 边界：Agent 自然语言总结不是 Evidence。
- 失败：`GOVERNANCE_EVIDENCE_INCOMPLETE`。
- 验证：补齐并校验摘要链后才接受。

## UC-011：投影漂移立即失效

- 规则：GE-005
- 输入：发布投影后修改治理相关 Manifest。
- 输出：G0 或 G7 检测到不同 Snapshot。
- 边界：运行日志和 Evidence 目录不算投影输入。
- 失败：`GOVERNANCE_PROJECTION_STALE` 或 `GOVERNANCE_DRIFT_DETECTED`。
- 验证：旧 Work Grant 不再授权执行。

## UC-012：权限跃迁集中确认

- 规则：CF-002
- 输入：一次变更集扩大多个路径，或一次交付包含 Push、CI、PR。
- 输出：分别形成一个变更确认包或一个交付确认包。
- 边界：确认不能修复未知 Action、歧义 Binding 或缺失 Evidence。
- 失败：拒绝确认时只停止跃迁，不影响原 Scope 内安全工作。
- 验证：同一包只请求一次确认，并绑定 `projection_id` 与目标。
