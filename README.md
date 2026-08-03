# SDD Harness

Harness 是基于固定 2-2-4 模型的仓库治理系统。它从仓库事实和已有治理来源生成
四域规则，由脚手架维护权威状态、确定性投影和内部执行保障；Harness Skill 是
用户的自然语言治理接口，不是实现、测试、Git、发布或部署入口。

治理效能重基线的计划、状态和验收以
[GitHub Epic #59](https://github.com/bigsmartben/harness-scaffold/issues/59)
及当前 F0
[#60](https://github.com/bigsmartben/harness-scaffold/issues/60)
为唯一事实源（SSOT, Single Source of Truth）。已完成的 v4 重构历史仍见
[#49](https://github.com/bigsmartben/harness-scaffold/issues/49)。

当前已发布并生效的合同版本仍是 `4.0.0`。#60 固定的是 #59 后续工作包使用的
规范语义；在领域数据合同、迁移、运行时和分发完成版本闭环前，它不表示 v4
已经支持新的领域字段或执行判断。首次 consumer bootstrap：

```text
uv tool install "sdd-harness @ git+https://github.com/bigsmartben/harness-scaffold.git@v4.0.0"
cd <consumer-repository>
harness load
```

## 北极星目标

> 在质量、安全、系统边界和可追溯性等硬约束下，减少人的认知负担、人工触点、
> 协作等待、机器浪费和返工，使人和机器更快、更稳定地交付正确结果，并能从
> 结果中持续学习。

```text
人机协同效能
= 有效成果
÷（人工注意力 + 机器成本 + 等待时间 + 返工成本）
```

这是优化方向，不是用速度抵消质量或安全的数值公式。外部硬约束始终优先。

| 子目标 | 具体例子 |
|---|---|
| 意图对齐 | 实现前明确目标、范围、约束和验收标准 |
| 合理分工 | 人确定风险阈值和批准，机器发现事实、执行并收集证据 |
| 一次做对 | 产出从一开始就满足架构、契约和系统边界 |
| 有效验证 | 按实际影响选择最低有效验证，不漏测也不机械全量测试 |
| 顺畅交付 | 只有可追溯、可回滚的正确制品通过目标环境门禁 |
| 持续学习 | 将失败回流为权威规格、设计约束或验证场景 |

## 固定模型

| 轴 | 固定值 |
|---|---|
| Audience（适用方） | `maintainer`、`consumer` |
| Responsibility（治理职责） | `generate`、`enforce` |
| Governance Domain（治理域） | `specification`、`implementation`、`verification`、`delivery` |

```text
2 × 2 × 4 = 16 个固定 Cell
```

`generate` 包含事实发现、已有治理读取、规整、分类、calibration（校准）和投影。
calibration 不是第三种 Responsibility。

`enforce` 表示脚手架建立治理义务、接收外部垂直执行者的类型化证据并核验结果。
它不再等同于 Schema、摘要或模型锁漂移校验。

## 四域最低保障

| Domain | `generate`（生成）至少产生 | `enforce`（执行保障）至少证明 |
|---|---|---|
| `specification` | 唯一权威规格关系：来源、优先级、范围、版本/摘要和冲突结果 | 结果绑定当前规格并完整证明符合性 |
| `implementation` | 完整、可追溯的设计约束集合及系统、接口和数据边界 | 每条适用约束都有证据，且未违反契约或越界 |
| `verification` | 由场景、实际影响范围和风险得到的最低有效验证集合及覆盖映射 | 每项必需验证可重复，且覆盖所有受影响边界和用户承诺 |
| `delivery` | “目标环境 × 生命周期阶段 × 制品 × 准入门槛”合同及回滚要求 | 正确制品在正确环境和阶段满足全部门禁，并可追溯、可回滚 |

必要输入缺失、冲突无法确定性解决或语义不足时，`generate` 必须阻断而不是猜测。
`enforce` 先判断适用性，再建立类型化义务并核验证据充分性；单个
`passed=true` 不能替代覆盖结论。

| 决策 | 最低语义 |
|---|---|
| `not_applicable` | 当前规则不适用于事件 |
| `blocked` | 必要输入、义务或充分证据缺失、冲突、失败或不完整 |
| `stale` | 规则、修订版、影响范围、环境或制品已经变化 |
| `satisfied` | 所有适用义务都有与当前上下文匹配的充分证据 |

例如，局部纯函数变化通常只需单元测试；不能无条件升级为昂贵全量测试。模块间
契约变化则至少需要单元与集成验证，不能用大量无关测试通过来掩盖集成验证缺失。
`scope`（规则适用范围）与 `impact_scope`（本次变化的实际影响范围）不得混用；
环境是 `delivery` 的内部维度，Gitflow 是生命周期策略，不是第五个治理域。

## 治理强度与四类交互

治理强度保障模型是规则内部属性，不是第五个 Governance Domain（治理域）。用户
添加或更新规则时，系统先推荐等级并说明理由、保障效果、人工交互和验证成本；
用户确认一次后，最终选择随规则 revision（修订版）保存。

```text
有效治理强度
= max（规则设定等级，事件风险下限，外部硬约束下限）
```

| 等级 | 最低保障 | 具体例子 |
|---|---|---|
| L1 自动保障 | 自动核验局部、可重复证据；信息充分时无需人工确认 | 私有纯函数只运行相关单元测试 |
| L2 审慎保障 | 自动分析影响并核验跨模块定向证据 | 内部接口变化运行单元与集成测试 |
| L3 强制门禁 | 全部必需证据满足后才能通过；封闭授权可确认一次 | 公共 API 兼容性规则 |
| L4 关键门禁 | 完整证据、逐事件授权、环境/制品门禁和必要回滚 | 生产发布或不可逆操作 |

L0/advisory（只观察或建议）不属于 enabled 规则的执行保障，不能用来绕过
`enforce`。用户可以提高等级，但不能降到事件风险或外部硬约束要求以下。

| 交互模式 | 稳定语义 |
|---|---|
| 默认放行 | 信息充分且无需新增权限时自动推进；仍必须核验证据 |
| 确认一次 / 不重复确认 | 只在 rule_id、revision、domain、scope、事件类别、风险上限和外部性均不变时复用 |
| 澄清请求 | 只补充会改变权威结果、范围、验证集合、环境或副作用的信息；不授予权限 |
| 明确确认 | 对生产、外部、不可逆、安全等具体事件逐次授权；不能覆盖硬约束 |

确认一次至少绑定 rule_id、revision、domain、scope、事件类别、风险上限和外部性；
明确确认至少绑定当前 event、target、payload digest、风险和副作用。任一关键绑定
变化后都必须重新计算，不能复用旧授权或旧 Evidence。

交互模式回答“是否以及如何请人介入”；`satisfied`、`blocked`、
`not_applicable`、`stale` 回答“治理义务是否成立”。例如，默认放行的 L1 事件
如果测试 Evidence（证据）失败，仍必须 `blocked`；明确确认了生产发布，但缺少
必要回滚能力，也仍然 `blocked`。

## 三层协作

| 层 | 做什么 | 实例 |
|---|---|---|
| Harness Skill | 理解治理意图并提交类型化请求 | “停用 contract-tests”→ disable 请求 |
| Harness 脚手架 | 发现事实、保存权威状态、投影并执行保障 | 对测试证据返回 `satisfied` / `blocked` |
| 垂直业务执行者 | 实现、测试、Git、发布、部署 | 测试 Worker 实际运行契约测试 |

Skill 不会因为用户提到 verification 就运行测试，也不会因为用户提到 delivery
就发布软件。

## 权威关系

```text
仓库事实 + 已有治理来源
          │
          ▼
       generate
          │
          ▼
     权威规则状态
       │       │
       ▼       ▼
  规则投影   enforce 保障状态
```

规则投影和保障状态都是可重算派生物，不是第二份规则 SSOT。聊天、Agent 总结和
Memory 不构成权威治理状态或执行证据。

## Maintainer / Consumer 边界

本仓库开发并分发 Harness，不是 consumer 初始化目标。根目录通过 `AGENTS.md`、
规范源码和仓库测试闭环；consumer 的 load、规则变更和执行保障只能在外部或临时
仓库验收。

## 文档

- [规范说明](docs/specification.md)
- [2-2-4 治理模型白皮书](docs/harness-2x2x4-governance-model-whitepaper.md)
- [快速开始与实施状态](docs/quickstart.md)
- [仓库结构](docs/repository-structure.md)
- [4.0.0 发布说明](docs/release-notes-4.0.0.md)
- [验收追踪](docs/acceptance-traceability.md)
