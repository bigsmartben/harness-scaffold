# Harness 2-2-4 治理规范

本规范是 Harness 治理模型的当前语义基线。实施范围和验收状态以
[GitHub Epic #49](https://github.com/bigsmartben/harness-scaffold/issues/49)
及其子 Issue 为唯一事实源（SSOT, Single Source of Truth）。

## 1. 产品定位

Harness 是仓库治理系统。它围绕固定的 Audience × Responsibility × Governance
Domain 模型，建立仓库规则的生成与执行保障闭环：

```text
仓库事实 + 已有治理来源
          │
          ▼
generate：发现 → 读取 → 规整 → 分类 → 校准 → 投影
          │
          ▼
权威规则状态 ──> 确定性投影
          │
          ▼
enforce：适用性 → 义务 → 外部证据 → 核验 → 稳定决策
```

calibration（校准）只是 `generate` 的内部阶段，不是第三种 Responsibility
（治理职责），也不是用户模式。

## 2. 固定 2-2-4 模型

| 轴 | 中文 | 固定值 |
|---|---|---|
| Audience | 适用方 | `maintainer`、`consumer` |
| Responsibility | 治理职责 | `generate`、`enforce` |
| Governance Domain | 治理域 | `specification`、`implementation`、`verification`、`delivery` |

三轴笛卡尔积固定产生 16 个 Cell（治理单元）。Cell ID 固定为：

```text
<audience>.<responsibility>.<domain>
```

规则不会创建第 17 个 Cell。consumer 的一条 domain=`verification` 规则由同一
身份的两个责任视图表达：

```text
consumer.generate.verification
consumer.enforce.verification
```

前者说明规则怎样从事实和治理来源生成并进入投影；后者引用同一规则 revision
（修订版）的执行保障合同。两个视图不是两条规则，也不是两个规则 SSOT。

## 3. 两种 Responsibility

| Responsibility | 规范语义 | 实例 |
|---|---|---|
| `generate` | 发现仓库事实和既有治理来源，读取、规整、分类、校准并确定性投影规则 | 从 `pyproject.toml` 的 Python 版本约束生成 implementation 规则候选 |
| `enforce` | 脚手架内部建立类型化义务，接收外部执行者的证据，核验后返回稳定决策 | 外部测试工具提交测试结果，脚手架核验 verification 规则是否满足 |

Schema 校验、固定 Cell 校验和摘要漂移检测仍是必要的内部一致性检查，但不再定义
`enforce`。只证明模型锁未被篡改，不能证明治理规则已经生效。

## 4. 三层职责边界

| 层 | 负责 | 不负责 |
|---|---|---|
| Harness Skill | 理解治理意图；提交类型化治理请求 | 投影、内部校验、执行保障、实现、测试、Git、发布、部署 |
| Harness 脚手架 | 事实发现、权威状态、投影、内部校验、执行保障、稳定诊断 | 替代垂直业务工具执行工作 |
| 垂直业务执行者 | 实现代码、运行测试、Git、发布、部署；提交类型化结果或证据 | 定义 Harness 的权威治理状态 |

例如，用户说“为 API 变更新增契约测试规则”时，Skill 可以提交 add 请求；脚手架
保存并投影规则；测试 Worker 实际运行测试并返回证据。Skill 不运行测试，脚手架
也不把聊天总结当成测试证据。

## 5. 四个治理域

| Domain | 关注点 | 规则实例 |
|---|---|---|
| `specification` | 目标、约束、验收边界 | 公共行为变更前必须定义可观察验收条件 |
| `implementation` | 代码和配置的构造约束 | 公共边界使用明确类型 |
| `verification` | 可重复的验证证据 | 公共契约变更必须提供契约测试结果 |
| `delivery` | 交付物和发布完整性 | 破坏性变更必须进入发布说明 |

治理域是分类，不是流水线阶段。domain=`delivery` 不授权 Skill 发布软件。

## 6. 权威关系

```text
权威规则状态（SSOT）
  ├─派生→ 当前规则投影
  └─派生→ 当前 enforcement obligation / decision
```

- consumer 的权威规则状态保存稳定身份、domain、来源、revision、状态和历史；
- 投影是可重算派生物，不是第二份可编辑规则；
- 执行保障状态必须绑定 projection、rule_id 和 revision；
- 规则或投影变化后，旧保障义务和旧证据必须失效；
- Agent 总结、聊天记录和 Memory 不构成权威状态或执行证据。

Load Core 的治理来源优先级固定为：

| 优先级 | 来源 | 示例 |
|---:|---|---|
| 500 | 当前仓库事实派生 baseline | `src/api.py` 的摘要进入 implementation fact |
| 400 | 当前 v4 权威状态 | `.harness/governance/state.json` |
| 300 | 旧 Harness 配置 | `.harness/harness.yaml` |
| 250 / 225 | Agent 指令 | `AGENTS.md` / `CLAUDE.md` |
| 200 / 150 | 其他仓库治理文档 | Copilot 指令 / `CONTRIBUTING.md` |

同一 `rule_id` 的内容完全一致时确定性合并来源；内容不一致时返回
`RULE_CANDIDATE_CONFLICT` 并保持零写入。四条 `repo-*-baseline` 是事实派生物，
所以仓库事实摘要变化时以新事实刷新并记录 `DERIVED_BASELINE_REFRESHED`。例如
`src/api.py` 内容变化只刷新 implementation baseline，不把旧 state 误判成人工规则冲突。
若某条 baseline 已被显式删除，其 tombstone（墓碑）会阻止后续 load 重新使用该
退休身份，避免每次 load 都陷入 `RULE_ID_RETIRED`。

`load.schema.json` 固定 `LoadRequest`（加载请求），
`load-result.schema.json` 固定完整 `LoadResult`（加载结果）。相同快照必须产生完全
一致的候选、校准记录、诊断和结果摘要。

## 7. 规则与 Operation 合同

当前规则至少包含：

| 字段 | 语义 |
|---|---|
| `rule_id` | 仓库内稳定且不可静默复用的身份 |
| `domain` | 四个固定治理域之一 |
| `directive` / `scope` | 治理内容和适用范围 |
| `sources` | 带类型、引用和摘要的来源数组 |
| `status` | `enabled` 或 `disabled` |
| `revision` | 每次成功状态变化递增的乐观并发版本 |
| `history` | 绑定 Operation 的各 revision 完整快照 |

删除后的规则进入非生效 tombstone（墓碑历史），不再属于当前 `rules` 集合，且其
`rule_id` 不可被 add 静默复用。

规则变更采用两步 Operation：

```text
register(request) → pending
                    ├─ apply  → applied
                    └─ cancel → cancelled
```

请求绑定 `operation_id`、`operation_type`、`target_rule_id`、`base_revision`、
payload 和 `payload_digest`。add/update 携带完整规则内容；disable/enable/delete
不携带 payload。`cancel` 是针对 Operation 的控制请求，不是规则状态。

| 操作 | 前置条件 | 成功后 |
|---|---|---|
| add | 当前和墓碑中都没有该身份；base=0 | revision=1、enabled |
| update | 当前规则存在且 base 匹配 | 同一身份，新 revision |
| disable | 当前 enabled 且 base 匹配 | disabled，新 revision |
| enable | 当前 disabled 且 base 匹配 | enabled，新 revision |
| delete | 当前规则存在且 base 匹配 | 从当前集合移除，保留墓碑历史 |
| cancel | 目标 Operation 为 pending | 仅 Operation 变 cancelled |

“取消当前操作”只有在恰好一个 pending Operation 时才明确；零个或多个候选返回
`CANCEL_TARGET_AMBIGUOUS`。apply/cancel 对同一 pending Operation 只允许一个
终态获胜，已 applied 的操作不会因 cancel 隐式回滚。

## 8. 16 个 Cell 的规范语义

| Cell | 规范语义 |
|---|---|
| `maintainer.generate.specification` | 定义治理规范语义并发布维护者规范源 |
| `maintainer.generate.implementation` | 从已接受语义生成实现合同与制品 |
| `maintainer.generate.verification` | 生成可追溯、可重复的验证标准 |
| `maintainer.generate.delivery` | 生成版本一致的分发与发布合同制品 |
| `maintainer.enforce.specification` | 运行保障，维持规范源之间的一致性 |
| `maintainer.enforce.implementation` | 运行保障，要求维护实现证据满足合同 |
| `maintainer.enforce.verification` | 运行保障，要求验收前具有可重复证据 |
| `maintainer.enforce.delivery` | 运行保障，要求分发前版本与制品完整 |
| `consumer.generate.specification` | 发现、校准并投影来源可追溯的规范规则 |
| `consumer.generate.implementation` | 发现、校准并投影来源可追溯的实现规则 |
| `consumer.generate.verification` | 发现、校准并投影来源可追溯的验证规则 |
| `consumer.generate.delivery` | 发现、校准并投影来源可追溯的交付规则 |
| `consumer.enforce.specification` | 建立规范义务并按当前规则核验类型化证据 |
| `consumer.enforce.implementation` | 建立实现义务并按当前规则核验类型化证据 |
| `consumer.enforce.verification` | 建立验证义务并按当前规则核验类型化证据 |
| `consumer.enforce.delivery` | 建立交付义务并按当前规则核验类型化证据 |

`src/harness_core/model.py` 中的 `CELL_DIRECTIVES` 是以上 Cell 语义的机器 SSOT。

## 9. Enforce 最小机器闭环

```text
projection_id + rule_id + revision
  → typed governed event
  → deterministic applicability
  → enforcement obligation
  → 外部垂直执行者的 typed Evidence
  → postcondition 核验
  → satisfied / blocked / not_applicable / stale
```

四个 domain 分别要求 `acceptance_record`、`implementation_result`、
`verification_result` 和 `delivery_result`。Evidence 必须绑定当前 obligation、
projection、rule_id 和 revision；规则更新、停用、删除或重新投影后，旧 Evidence
返回 `stale`。Agent summary、Memory、chat 和 Transcript 稳定返回
`EVIDENCE_PRODUCER_FORBIDDEN`。

Harness 只核验外部执行者提交的结果。例如 verification obligation 可以要求
`verification_result`，但运行测试仍属于测试 Worker。
