# Harness 2-2-4 治理规范

本规范是 Harness 治理模型的语义基线。治理效能重基线的计划、状态和验收以
[GitHub Epic #59](https://github.com/bigsmartben/harness-scaffold/issues/59)
及 F0
[#60](https://github.com/bigsmartben/harness-scaffold/issues/60)
为唯一事实源（SSOT, Single Source of Truth）。已发布的 `4.0.0` 仍是当前唯一
生效的运行时合同；本 F0 只固定后续功能 Issue 必须实现的规范语义，不提前增加领域
Schema 字段、迁移或运行时能力。

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

## 2. 北极星目标与效能边界

Harness 治理体系的北极星目标是：

> 在质量、安全、系统边界和可追溯性等硬约束下，减少人的认知负担、人工触点、
> 协作等待、机器浪费和返工，使人和机器更快、更稳定地交付正确结果，并能从
> 结果中持续学习。

概念关系：

```text
人机协同效能
= 有效成果
÷（人工注意力 + 机器成本 + 等待时间 + 返工成本）
```

该表达只说明优化方向，不是允许用速度抵消质量、安全或数据契约的数值公式。
外部硬约束始终优先，观察指标也不能反向削弱必要验证。

| 子目标 | 需要回答的问题 | 具体例子 |
|---|---|---|
| 意图对齐 | 机器是否理解人的真实目标 | 实现前明确结果、范围、约束和验收标准 |
| 合理分工 | 人和机器分别承担什么 | 人确定优先级、风险阈值和批准；机器发现、规整、执行并收集证据 |
| 一次做对 | 初始产出是否符合约束 | 代码同时满足架构、接口契约、数据契约和系统边界 |
| 有效验证 | 是否以合理成本获得足够可信度 | 按影响选择单元、集成、定向回归和用户验证 |
| 顺畅交付 | 已验证结果能否安全进入目标环境 | 核对分支、版本、制品、准入门槛和回滚条件 |
| 持续学习 | 同类问题是否会重复 | 将失败回流为权威规格、设计约束或验证场景 |

## 3. 固定 2-2-4 模型

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

## 4. 两种 Responsibility

| Responsibility | 规范语义 | 实例 |
|---|---|---|
| `generate` | 发现仓库事实和既有治理来源，读取、规整、分类、校准并确定性投影规则 | 从 `pyproject.toml` 的 Python 版本约束生成 implementation 规则候选 |
| `enforce` | 脚手架内部建立类型化义务，接收外部执行者的证据，核验后返回稳定决策 | 外部测试工具提交测试结果，脚手架核验 verification 规则是否满足 |

Schema 校验、固定 Cell 校验和摘要漂移检测仍是必要的内部一致性检查，但不再定义
`enforce`。只证明模型锁未被篡改，不能证明治理规则已经生效。

## 5. 三层职责边界

| 层 | 负责 | 不负责 |
|---|---|---|
| Harness Skill | 理解治理意图；提交类型化治理请求 | 投影、内部校验、执行保障、实现、测试、Git、发布、部署 |
| Harness 脚手架 | 事实发现、权威状态、投影、内部校验、执行保障、稳定诊断 | 替代垂直业务工具执行工作 |
| 垂直业务执行者 | 实现代码、运行测试、Git、发布、部署；提交类型化结果或证据 | 定义 Harness 的权威治理状态 |

例如，用户说“为 API 变更新增契约测试规则”时，Skill 可以提交 add 请求；脚手架
保存并投影规则；测试 Worker 实际运行测试并返回证据。Skill 不运行测试，脚手架
也不把聊天总结当成测试证据。

## 6. 四个治理域及最低保障合同

四域是治理分类，不是必须顺序执行的流水线阶段。`delivery` 不授权 Skill 发布
软件；环境是 delivery 的内部维度，不是第五个 Governance Domain（治理域）。

### 6.1 通用 `generate` 最低保障

`generate` 必须：

- 读取权威来源或可证明的仓库事实；
- 使发现、读取、规整、分类、校准和投影可追溯、确定；
- 产生 `enforce` 所需的最低明确语义，不能只留下模糊自然语言；
- 在必要输入缺失、来源冲突或语义不足时给出稳定阻断/澄清，不能猜测；
- 对相同事实、来源和合同版本产生相同规则与投影。

```text
generate(domain, authoritative_inputs)
  → projected_rule
  | blocked
```

### 6.2 通用 `enforce` 最低保障

`enforce` 必须：

- 按当前投影、规则、revision（修订版）和上下文确定适用性；
- 为适用规则建立说明最低完成条件的类型化义务；
- 使 Evidence（证据）绑定当前投影、规则、revision、目标和必要上下文；
- 检查覆盖完整性和证据充分性，不能只接受单个 `passed=true`；
- 在规则、版本、影响范围、目标环境或制品变化后使旧义务和证据失效；
- 在适用义务或充分证据缺失时失败关闭。

```text
enforce(projected_rule, governed_event, evidence)
  → satisfied
  | blocked
  | not_applicable
  | stale
```

### 6.3 四域最低合同总览

| Domain | 核心不变量 | `generate` 最低产物 | `enforce` 最低证明 |
|---|---|---|---|
| `specification` | 为适用范围和版本确定唯一权威规格关系，不创建第二份可编辑规则 SSOT | 权威来源、优先级、范围、版本/摘要和冲突结果 | 结果绑定当前规格，且所有适用要求都有符合性证据 |
| `implementation` | 实现满足完整、可追溯的适用设计约束，且不越过系统和契约边界 | 约束来源、类型、范围、摘要、系统边界、接口和数据契约 | 每条适用约束都有映射证据，且无契约违反或系统越界 |
| `verification` | 以场景、实际影响范围和风险选择覆盖全部受影响边界与用户承诺的最低有效验证 | 最低有效验证集合及影响—验证覆盖映射 | 每项必需验证的步骤、断言、结果、证据和覆盖结论完整可重复 |
| `delivery` | 治理精确的环境、生命周期转换、制品、准入、追溯与回滚能力 | “环境 × 生命周期阶段 × 制品 × 准入门槛”合同及前置、追溯和回滚要求 | 正确制品在正确环境和阶段满足全部门禁，并可追溯、可回滚 |

### 6.4 `specification`（规格）

最低输入与生成产物：

```text
候选规格来源（身份 + 权威/优先级 + 版本/摘要 + 适用范围）
+ 当前权威规则状态
→ 唯一权威规格关系 + 冲突处理结果
```

来源权威性、适用范围、版本或必要语义缺失，以及冲突无法确定性解决时，必须
`blocked`。consumer 的权威规则状态仍是唯一规则 SSOT；规格解析结果和投影只是
输入或派生物。

最低执行义务是：工作结果绑定当前规格身份、版本/摘要，并证明符合所有适用要求。

- 正例：API Schema 与说明文档冲突，但已声明 Schema 优先；系统按该关系裁决并
  保留冲突结果。
- 反例：没有权威优先级时采用“最后读取的文档获胜”。该结果不确定，必须阻断。

### 6.5 `implementation`（实现）

最低输入与生成产物：

```text
提示词、代码、架构、系统边界、接口与数据契约来源
+ specification 确定的权威关系
→ 完整、可追溯的适用设计约束集合
```

约束来源缺失、冲突无法确定性解决，或范围、系统边界、契约集合不完整时，必须
`blocked`。最低执行义务是“每条适用约束 → 对应实现证据”，并显式检查接口、
数据契约和系统边界。

- 正例：公共 CLI 只允许 `load`、`operate`、`cancel`、`inspect`，实现证据逐项
  说明四命令边界未改变。
- 反例：第五个命令的测试全部通过，但它违反固定系统边界，仍必须阻断。

### 6.6 `verification`（验证）

每个场景至少表达：

```text
需求规格
→ 前置条件
→ 用户或系统操作步骤
→ 断言
→ 结论
```

每次受治理变化进一步表达：

```text
变更内容
→ impact_scope（实际影响范围）
→ 风险
→ 最低有效验证集合
→ 影响—验证覆盖映射
→ 验证 Evidence
→ 覆盖结论
```

`scope` 是规则适用目标，`impact_scope` 是本次变化的实际影响范围，两者不能用
同一个文件匹配字符串混为一谈。场景、影响或风险缺失，受影响边界/用户承诺没有
对应验证，或者无影响与风险依据却机械要求无关全量测试时，生成阶段必须阻断。

| 影响范围 | 最低验证基线 |
|---|---|
| 单个函数、类或局部算法 | 单元测试（Unit Test，单元级验证） |
| 模块间接口或数据流 | 单元测试 + 集成测试（Integration Test，模块协作验证） |
| 公共契约、共享基础能力或兼容性边界 | 单元测试 + 集成测试 + 定向回归测试（Regression Test，既有行为验证） |
| 完整用户任务或关键路径 | 相关底层验证 + 用户/端到端验证（User/E2E，用户结果验证） |
| 发布、部署或环境变化 | 相关回归 + 用户验收 + 交付准入与回滚验证 |

该表是最低基线而非封闭枚举；契约、属性、性能、安全和 smoke（冒烟）验证可按
风险纳入。执行阶段必须为每项必需验证核验步骤、断言、结果、可重复证据和覆盖
结论。

- 正例：局部纯函数变化选择相关单元测试，不触发无关全量测试。
- 验证不足反例：模块间契约变化只有大量无关单元测试通过，却缺少集成验证。
- 过度验证反例：仅修改文案也无条件运行全部高成本性能和端到端测试。
- stale 反例：影响范围扩大后仍复用旧验证集合和旧证据。

### 6.7 `delivery`（交付）

最低输入与生成产物：

```text
目标环境
× 当前/目标生命周期阶段
× 制品身份/版本/摘要
× 准入门槛
+ 前置阶段 + 追溯 + 回滚条件
→ 交付合同
```

环境示例包括开发、测试、预发布和生产；生命周期包括 Gitflow、分支合并、构建、
版本、发布、部署和回滚；制品可为 wheel、容器镜像或配置包。Gitflow 是生命周期
策略，不是运行环境。

环境、阶段、制品或门禁缺失，转换跳过前置阶段，或不能建立追溯与回滚条件时，
生成阶段必须阻断。执行阶段只有在制品身份/版本/摘要、目标环境、目标阶段、
全部准入证据、追溯和回滚能力精确匹配时才能放行。

- 正例：生产部署重新核对制品摘要、版本、生产门禁和回滚能力。
- 反例：复用测试环境证据把制品直接放入生产，或把 Gitflow 误建模为第五个域。

## 7. 治理强度保障模型与交互模式

治理强度决定“一条适用规则需要多强的执行保障，以及当前事件何时需要人介入”。
它是规则内部的保障语义，不是第五个 Governance Domain、第三种 Responsibility
或新的顶层模型轴。

### 7.1 三个独立输入与有效强度

| 输入 | 含义 | 具体例子 |
|---|---|---|
| 规则设定等级 | 用户在 add/update 时确认、随 rule revision 保存的长期保障强度 | 公共 API 兼容性规则设为 L3 |
| 事件风险下限 | 本次实际影响、可逆性、外部性和成本要求的最低强度 | 内部规则本次跨入公共契约，事件下限升为 L3 |
| 外部硬约束下限 | 安全、数据、公共契约或生产环境不可降级的最低强度 | 生产环境要求 L4 与回滚能力 |

```text
有效治理强度
= max（规则设定等级，事件风险下限，外部硬约束下限）
```

计算只针对当前权威投影中与 domain、scope、revision 和 event context（事件上下文）
确定匹配的 enabled 规则。用户可以提高等级，但不能把规则降到事件风险或外部
硬约束下限以下。

### 7.2 L1–L4 最低语义

| 等级 | 最低义务 | 人工交互 | 风险边界实例 |
|---|---|---|---|
| L1 自动保障 | 自动建立并核验局部、可重复的最低证据 | 信息充分时默认放行，0 次日常确认 | 格式规范、私有纯函数 |
| L2 审慎保障 | 自动完成影响分析并核验跨模块定向证据 | 默认放行；仅在实质性歧义时澄清 | 内部模块接口、架构依赖 |
| L3 强制门禁 | 当前投影的全部必需证据满足后才能通过 | 封闭授权确认一次，否则明确确认 | 公共 API、数据契约、兼容性承诺 |
| L4 关键门禁 | 完整证据、逐事件授权、环境/制品门禁和必要回滚 | 每个具体事件明确确认 | 生产、不可逆、删除、安全边界 |

L0/advisory（只观察或建议）不是 enabled 规则的保障等级，不能成为绕过
`enforce` 的旁路。未来若需要 advisory，必须单独定义状态、投影和用户预期。

### 7.3 添加与更新规则

```text
来源可追溯的推荐等级
→ 展示理由、保障效果、人工交互和验证成本
→ 用户确认一次或选择允许范围内的其他等级
→ 绑定 Operation、payload digest、rule revision 与 history
→ 绑定不变时自动执行保障
```

系统不得把可计算的等级判断推给用户。选择低于事件风险或外部硬约束下限时，
必须零规则写入并说明不可降低的来源。

### 7.4 四类 interaction mode（交互模式）

| 模式 | 触发条件 | 授权与复用边界 | 系统行为 |
|---|---|---|---|
| 默认放行 | 信息充分、无需新增权限，机器义务已满足或可自动满足 | 不产生授权 | 自动推进并解释依据；Evidence 失败仍 blocked |
| 确认一次 / 不重复确认 | 用户确认封闭、稳定且可复核的绑定 | 只复用相同 rule_id、revision、domain、scope、事件类别、风险上限和外部性 | 首次确认后不重复询问；绑定变化后失效 |
| 澄清请求 | 歧义会实质改变权威结果、适用范围、最低验证集合、目标环境或副作用 | 只补信息，不授予权限 | 请求最少必要字段，答复后重算强度与模式 |
| 明确确认 | 当前具体事件需要生产、外部、不可逆、安全或其他高风险权限 | 只绑定当前 event、target、payload digest、风险和副作用 | 逐事件说明效果并确认，不产生长期授权 |

重新确认条件是封闭的：目标或 Operation payload、规则等级、rule revision/scope、
事件类别/风险下限、外部硬约束下限、外部性/不可逆性或目标环境发生变化。Evidence
缺失或失败通常要求补证或修复，不自动要求用户重新授权。

### 7.5 交互模式与稳定决策正交

交互模式回答“是否以及如何请求人介入”，稳定决策回答“治理义务最终是否成立”。

- 默认放行不等于 `satisfied`，也不跳过 Evidence；
- 确认一次只复用权限，不复用 stale Evidence；
- 澄清请求不授予权限；
- 明确确认不能覆盖硬约束或把失败 Evidence 改成 `satisfied`；
- `not_applicable`、`stale` 和已知硬约束失败应在人介入前确定，避免无意义确认。

具体反例：

| 失败模式 | 输入 | 正确结果 |
|---|---|---|
| 默认放行证据失败 | L1 私有函数信息完整，但单元测试失败 | mode=默认放行，decision=blocked |
| 一次确认越界复用 | L3 规则 revision 或风险上限已变化 | 旧确认和旧 Evidence stale，重新计算模式 |
| 把澄清当授权 | 用户只补充 impact_scope | 不产生发布或外部操作权限 |
| 明确确认覆盖硬约束 | 用户同意生产发布，但缺少必要回滚 | blocked，不执行发布 |
| 过度验证 | 局部纯函数无依据要求全量 E2E/性能测试 | blocked，重新选择最低有效集合 |
| 验证不足 | 公共契约只有无关单元测试 | blocked，补集成与定向回归 |
| 过度确认 | L1 信息充分仍要求逐事件确认 | mode 应为默认放行，人工触点为 0 |
| 等级降低 | 用户选 L1，但外部数据契约下限为 L3 | blocked，解释 L3 下限来源 |

“全部适用约束”只指当前 authoritative projection（权威投影）中与 domain、scope、
revision 和 event context 确定匹配的 enabled 规则；“全部必需验证”只指由当前
impact_scope、风险、受影响边界、用户承诺和有效强度确定生成的最低有效集合。
不得用大量无关证据替代缺失的必需项。

## 8. 稳定决策语义

| 决策 | 最低语义 |
|---|---|
| `not_applicable` | 当前投影规则不适用于受治理事件 |
| `blocked` | 必要输入、义务或充分匹配证据缺失、冲突、失败或不完整 |
| `stale` | 规则、revision、相关上下文、影响范围、目标环境或制品不再匹配义务/证据 |
| `satisfied` | 每个适用义务都有与当前上下文匹配的充分证据 |

“没有发现违规”不等于 `satisfied`；只有全部适用义务被充分证明时才满足。

## 9. 权威关系

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

## 10. 规则与 Operation 合同

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

## 11. 16 个 Cell 的规范语义

| Cell | 规范语义 |
|---|---|
| `maintainer.generate.specification` | 定义并发布规格权威、优先级、范围、版本/摘要和确定性冲突阻断语义 |
| `maintainer.generate.implementation` | 定义并发布包含来源、类型、范围、系统边界、接口与数据契约的完整可追溯约束合同 |
| `maintainer.generate.verification` | 定义并发布由场景和影响驱动、具有完整覆盖映射且不机械全量执行的最低有效验证选择 |
| `maintainer.generate.delivery` | 定义并发布环境、生命周期阶段、制品、准入、前置、追溯和回滚语义 |
| `maintainer.enforce.specification` | 要求维护制品绑定当前权威规格，阻断缺失、冲突、不符合或 stale 的证据 |
| `maintainer.enforce.implementation` | 要求维护实现证据映射每条适用约束，阻断契约违反和系统越界 |
| `maintainer.enforce.verification` | 验收前要求可重复证据和完整影响覆盖，阻断失败、缺失、不充分或 stale 的结果 |
| `maintainer.enforce.delivery` | 分发前要求精确制品、环境、生命周期阶段、准入证据、追溯和回滚能力 |
| `consumer.generate.specification` | 解析并确定性投影一个包含优先级、范围、版本/摘要和冲突结果的来源可追溯规格权威 |
| `consumer.generate.implementation` | 解析并确定性投影完整适用的可追溯设计约束、系统边界、接口与数据契约 |
| `consumer.generate.verification` | 由需求、场景、实际影响和风险确定性投影最低有效验证集合与覆盖映射 |
| `consumer.generate.delivery` | 确定性投影精确环境、生命周期转换、制品、准入、前置、追溯和回滚合同 |
| `consumer.enforce.specification` | 要求结果绑定并符合当前规格身份和版本，拒绝缺失、冲突或 stale 的证据 |
| `consumer.enforce.implementation` | 要求每条适用约束都有证据，拒绝契约违反、系统越界、不完整映射或 stale 证据 |
| `consumer.enforce.verification` | 要求每项必需验证、断言、结果和受影响边界覆盖结论具有可重复的当前证据 |
| `consumer.enforce.delivery` | 仅在全部门禁、前置、追溯和回滚证据有效时，允许精确制品进入精确环境和阶段 |

`src/harness_core/model.py` 中的 `CELL_DIRECTIVES` 是以上 Cell 语义的机器 SSOT。

## 12. Enforce 最小机器闭环

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
