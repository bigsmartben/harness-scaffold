# Harness 治理规范（SSOT）

目标规范：`2.0.0-draft`（已接受）
当前运行时协议：`1.0.0`

本文件是 Harness 的唯一规范来源（SSOT, Single Source of Truth）。其他文档只能解释或演示本规范，不得建立平行政策。

## 1. 产品定义

Harness 是运行在 Codex App / Codex CLI 中、绑定仓库的 Agent 治理框架。它只有两个顶层职责：

| 职责 | 中文 | 可验证结果 |
|---|---|---|
| `generate` | 生成治理规范 | 从固定仓库快照编译出可追溯的治理投影 |
| `enforce` | 确保规范执行 | 以投影驱动 Action 解析、G0–G7 与 Evidence |

Audit、仓库发现、Tool Registry、Task Catalog、边界和平台门禁都是这两个职责的实现机制，不是第三个产品模式。

正式入口是项目级 `$harness` Skill。`uv tool install` 与 `sdd-harness init` 用于分发和初始化；CLI、Plugin、Hook、MCP 和常驻服务都不是基础运行前提。

## 2. Contract-first 契约

### 2.1 输入

- 具有稳定摘要的 Repository Snapshot（仓库快照）；
- Manifest、Lockfile、Package Script、Workflow、仓库脚本和既有治理声明中的 source-backed facts（有来源事实）；
- `maintainer`、`consumer` 两类 Audience（适用用户）；
- Specification、Implementation、Verification、Delivery 四个治理域的规范来源；
- 当前任务、Work Grant（工作授权）和执行上下文。

环境中偶然存在的工具、模型推测、默认习惯和未验证命令都不是仓库事实。

### 2.2 输出

- `.harness/governance/sources.lock.json`：事实与来源锁；
- `.harness/governance/action-graph.json`：行为及调用关系；
- `.harness/governance/rules.json`：规范化规则 SSOT；
- `.harness/governance/projection.lock.json`：投影输入和 `projection_id`；
- `AGENTS.md`、`.codex/`、`.agents/skills/harness/`：Codex 运行时发布面；
- Gate Decision、Postcondition 结果和摘要链 Evidence；
- 失败时的稳定 blocker code（阻断码）与 Handoff（移交）状态。

### 2.3 边界条件

- Harness 只治理仓库内 Agent 行为，不定义产品需求或业务事实。
- 工具存在不等于仓库使用；仓库使用不等于允许调用；执行成功不等于治理结论有效。
- 生成器不能把“已生成”当作“已执行”；验证器不能静默修复输入。
- Agent 只能提交 `projection_id`、Work Grant、`action_id`、Audience、Scope 和类型化参数，不能覆盖 `command`、`argv`、`cwd`、环境变量或后置条件。
- 治理状态只存在于仓库 Artifact；Session、Memory、Transcript 和持久化 Agent 不得保存授权。
- 无法证明旁路被阻断时，规则最多是 `verified`，不得标为 `enforced`。

### 2.4 失败语义

所有失败都必须失败关闭（fail closed）并返回以下封闭枚举之一：

| 分类 | 阻断码 |
|---|---|
| 来源与投影 | `GOVERNANCE_SOURCE_MISSING`, `GOVERNANCE_CONFLICT`, `GOVERNANCE_SCOPE_UNRESOLVED`, `GOVERNANCE_INHERITANCE_INVALID`, `GOVERNANCE_PROJECTION_STALE`, `GOVERNANCE_COVERAGE_INCOMPLETE` |
| 行为与调用 | `TOOL_ACTION_UNCLASSIFIED`, `TOOL_BINDING_AMBIGUOUS`, `GOVERNANCE_PRECONDITION_FAILED`, `INVOCATION_BYPASS_ATTEMPT` |
| 结论与漂移 | `GOVERNANCE_NOT_ENFORCEABLE`, `GOVERNANCE_EVIDENCE_INCOMPLETE`, `GOVERNANCE_DRIFT_DETECTED` |
| Agent 绑定 | `AGENT_BINDING_UNAVAILABLE`, `AGENT_ROLE_CONTRACT_INVALID`, `AGENT_CONFIGURATION_UNTRUSTED` |
| 移交 | `HANDOFF_REQUIRED` |

## 3. 治理模型

每条规则同时具有三个正交维度，形成 `2 × 2 × 4 = 16` 个最小治理单元：

| 维度 | 封闭枚举 | 回答 |
|---|---|---|
| Audience | `maintainer`, `consumer` | 规则约束谁 |
| Responsibility | `generate`, `enforce` | 如何产生并落实规则 |
| Governance Domain | `specification`, `implementation`, `verification`, `delivery` | 规则约束 SDD 的哪个阶段 |

`maintainer` 维护 Harness 产品、规范和控制面；`consumer` 使用 Harness 治理目标项目。目标项目维护者在使用 Harness 时仍属于 `consumer`。

四个治理域分别回答：

| 治理域 | 人话定义 | 示例 |
|---|---|---|
| Specification | 要做什么、为什么做、怎样算完成 | “登录失败时显示可操作提示，不能泄露账号是否存在” |
| Implementation | 如何把规范变成项目制品 | 修改登录服务和错误提示组件 |
| Verification | 如何证明实现满足规范 | 运行最近的登录单测和接口契约测试 |
| Delivery | 如何把已验证制品交给外部系统或用户 | Commit、Push、PR、Release 或 Deploy |

Agent Control、Runtime Context、Action Binding、Tool and Platform Control、Project Profile 与 Evidence 是作用于四域的横向控制。PoC 是 `implementation` 中的开发模式；`other-tools` 不再作为分类，工具必须绑定明确 Action 和治理域。

### 3.1 Rule 最小结构

每条 Rule（规则）必须包含：`rule_id`、可空的 `action_id`、`audience`、`responsibility`、`domain`、`projection_id`、`source_refs`、单一 `directive`、`scope`、`inheritance`、`invocation`、`preconditions`、`postconditions`、`enforcement_level`、`confirmation_policy`、`evidence` 和 `failure`。

### 3.2 确定性投影

```text
projection_id = SHA256(
  repository_snapshot
  + governance_relevant_files_digest
  + governance_schema_version
  + projection_compiler_version
  + maintainer_declarations_digest
)
```

相同输入必须得到语义稳定、摘要相同的输出；任何治理输入变化都会使旧投影失效。

## 4. 规范规则

### 4.1 生成（generate）

- **GG-001**：发现器 MUST 只输出带 `source_ref` 与内容摘要的仓库事实。
- **GG-002**：投影器 MUST 构建 Action Graph（行为图），不能用工具清单代替行为分类。
- **GG-003**：编译器 MUST 为两类 Audience、两类 Responsibility 与四个 Governance Domain 生成完整 16 单元覆盖；无来源或缺少必要绑定的单元必须成为阻断性缺口。
- **GG-004**：Bootstrap、Adopt、Update MUST 先完成零写入预检，再按精确 Plan 由单写者发布；相同输入重复运行必须为空 Diff。
- **GG-005**：候选归并 MUST 保留冲突，不能静默选择；Schema 或跨文件校验失败时必须零写入。

### 4.2 Agent 绑定

- **AG-001**：主 Agent MUST 读取 `AGENTS.md`、项目 TOML 和当前投影，并等待所有必需只读 Subagent 后再发布。
- **AG-002**：六个角色 MUST 使用机器可校验的单一职责契约；缺失、无效或不受信时不得回退到通用 Agent。
- **AG-003**：Subagent MUST 继承父会话权限；TOML 的 Sandbox 默认值不能扩大父权限。
- **AG-004**：并行写入 MUST 有互不重叠的 ownership；无法证明时使用单一 `governed_worker`。

### 4.3 执行（enforce）

- **GE-001**：所有修改状态或产生权威结论的 Action MUST 通过 G0–G7，Gate Decision 只能由确定性内核产生。
- **GE-002**：Action Resolver MUST 从 `action_id` 唯一解析 `argv`、`cwd`、Scope、环境约束和 Postconditions。
- **GE-003**：Narrow Runner（窄执行器） MUST 拒绝任意命令字符串和任何绑定覆盖。
- **GE-004**：只有 Schema、Postcondition 和摘要链全部通过的 Evidence 才能支撑“测试通过”“构建成功”或“允许交付”等结论。
- **GE-005**：未知、未分类、过期、绑定歧义、证据不全或执行后漂移 MUST 失败关闭并返回完整阻断包。

### 4.4 确认

- **CF-001**：常规只读、已登记测试和 Work Grant 范围内修改不逐工具确认。
- **CF-002**：扩大范围按变更集确认一次；关键外部动作按交付包确认一次；确认不能替代分类、Gate 或 Evidence。

### 4.5 本地工作区与最低充分验证

- **LW-001**：本地目录、Staged/Unstaged/Untracked 修改和 Private Branch 属于 Local Workspace；目标范围内工作应连续推进，不逐文件或逐命令打断用户。
- **LW-002**：本地验证默认从 T0 Inspect 开始，只在影响事实要求时升级到 T1 Nearest、T2 Component 或 T3 Full。
- **LW-003**：正常成功时只向用户展示修改、验证强度、未运行项和剩余风险；内部 Gate、Digest 和完整 Evidence 按需展开。
- **LW-004**：Harness MUST 保留无关用户修改，不得自动 Stage、覆盖或提交未接管内容。

例如，只修改一段文档使用 T0 结构检查；修改单个函数优先运行最近的单元测试，而不是默认执行全仓库测试。

### 4.6 Commit 检查点与远端 Issue

- **CP-001**：`git commit` 或等价明确指令是本地工作唯一的常规可见检查点。
- **CP-002**：Commit 前询问用户是否对当前工作区执行跨对话影响分析；分析事实范围覆盖 Staged、Unstaged 和 Untracked。
- **CP-003**：Workspace Impact Scope 与 Commit Scope 必须分离；后者由用户确认的 Issue 格式计划决定。
- **IS-001**：普通消费者项目未配置远端时，Issue 目标默认是本地 `.harness/issues`；项目可以显式配置远端 Provider 和 Repository。
- **IS-002**：远端 Issue 创建、更新、评论、标签、负责人、里程碑、关闭和重开必须绑定精确 Provider、Repository、Issue 或内容，并获得当前确认。
- **IS-003**：远端失败不得静默回退为本地 Issue，也不得改投其他远端。
- **IS-004**：Harness 产品维护者迭代统一使用本仓库 GitHub Issues 作为唯一 SSOT；本地文档只能链接远端 Issue，不得保存可独立编辑的 Issue 正文镜像。
- **DL-001**：Commit 授权不得继承为 Push、PR、Merge、Publish、Release 或 Deploy 授权。

## 5. G0–G7

| Gate | 检查 | 典型失败 |
|---|---|---|
| G0 快照 | 当前仓库仍匹配 `projection_id` | `GOVERNANCE_PROJECTION_STALE` |
| G1 来源 | 规则来源存在且摘要有效 | `GOVERNANCE_SOURCE_MISSING` |
| G2 覆盖 | 行为已发现、分类并覆盖 | `GOVERNANCE_COVERAGE_INCOMPLETE` |
| G3 绑定 | 解析到唯一调用 | `TOOL_BINDING_AMBIGUOUS` |
| G4 前置 | 用户、范围、分支、成本和权限满足 | `GOVERNANCE_PRECONDITION_FAILED` |
| G5 调用 | 经过 Harness Dispatcher | `INVOCATION_BYPASS_ATTEMPT` |
| G6 结论 | Schema、后置条件和 Evidence 完整 | `GOVERNANCE_EVIDENCE_INCOMPLETE` |
| G7 漂移 | 执行后治理输入未意外变化 | `GOVERNANCE_DRIFT_DETECTED` |

## 6. Codex-native 编排

```text
主 Agent
├─ repo_mapper                 只读事实
├─ governance_projector × 16   只读候选
├─ projection_reconciler      只读归并
├─ governance_validator       只读裁决
├─ governed_worker            单写者执行
└─ evidence_verifier          只读验收
```

生成链为 Snapshot → Facts → Action Graph → 16 Governance Units → Reconciliation → Validation → 一次 Plan → 单点发布。执行链为 Action Request → Resolver → G0–G5 → Narrow Runner → Postconditions → G6–G7 → Evidence。

## 7. 版本迁移边界

四域模型是已接受的目标规范；当前 Schema、编译器和运行时仍使用 1.0 Artifact。迁移由 [Epic #22](https://github.com/bigsmartben/harness-scaffold/issues/22) 统一跟踪。

迁移完成前：

- 不得把目标文档描述成已经实现的运行时能力；
- 当前 1.0 Artifact 继续按现有 Schema 失败关闭；
- 新旧模型不得静默互转；
- 兼容或拒绝策略必须显式、可测试；
- Workspace / Branch Policy、Tool Registry、Task Catalog 和 Adapter 仍只是 source-backed 输入，不能形成平行政策。

## 8. 完成定义

只有当前投影可追溯、Agent 契约有效、16 个治理单元覆盖完整、写入满足单写者、Action 通过 G0–G7 且 Evidence 摘要链完整时，Harness 才能声明四域治理闭环有效。在迁移完成前，只能分别声明当前 1.0 运行时能力与已接受目标，不能混为一谈。
