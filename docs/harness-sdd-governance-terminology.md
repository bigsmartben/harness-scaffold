# Harness SDD 四域治理模型：术语、目标边界与规则

状态：**Accepted Target Specification（目标规范已接受，待实现）**  
决议日期：2026-07-28  
适用范围：Harness 治理规范、Schema、编译器、Skill、文档和测试

## 1. 决议

Harness 的目标治理模型正式命名为：

> **Harness SDD 四域治理模型**  
> Harness SDD Four-Domain Governance Model

不再使用“224 Harness”“226 Harness”“2 层 6 类”等数字名称作为正式术语。数字只能作为内部矩阵规模的简写，不能替代模型名称。

目标模型具有三个彼此正交的维度：

| 维度 | 正式术语 | 封闭枚举 | 回答的问题 |
|---|---|---|---|
| Audience | 适用角色 | `maintainer`, `consumer` | 规则约束谁 |
| Responsibility | 治理职责 | `generate`, `enforce` | 规则如何产生和落实 |
| Governance Domain | 治理域 | `specification`, `implementation`, `verification`, `delivery` | 规则治理哪个 SDD 阶段 |

一个 Governance Cell（治理单元）由一个 Audience、一个 Responsibility 和一个 Governance Domain 唯一确定。完整矩阵包含：

```text
2 Audience × 2 Responsibility × 4 Governance Domain
= 16 Governance Cells
```

如果你是 Harness 使用者，不需要先理解 16 个治理单元才能开始工作；可以直接阅读[第 18 节：给使用者的人话说明](#18-给使用者的人话说明)。

## 2. 两类适用角色

### 2.1 `maintainer`

`maintainer` 指维护 Harness 产品及其治理控制面的人。

典型活动：

- 修改 Harness 规范、Schema 和确定性 Core；
- 修改 Plugin、Skill、模板和初始化器；
- 验证并发布 Harness 自身。

### 2.2 `consumer`

`consumer` 指使用 Harness 治理目标项目的人。

典型活动：

- 在目标仓库中生成或更新治理投影；
- 使用 Work Grant（工作授权）完成 SDD 开发；
- 执行目标项目的验证和交付 Action（行为）。

角色名称始终相对于 Harness 产品解释。一个人可以同时是目标项目的维护者和 Harness 的 `consumer`，两者不冲突。

## 3. 两类治理职责

### 3.1 `generate`

`generate`（生成治理规范）负责从固定仓库快照和有来源事实生成可追溯的治理投影。

它回答：

- 当前仓库有哪些可证明的事实？
- 每个治理单元适用什么规则？
- 规则来自哪里，继承关系是什么？
- 当前投影是否完整、无冲突且可重复生成？

### 3.2 `enforce`

`enforce`（确保规范执行）负责以当前投影约束 Action 解析、执行、后置条件和 Evidence（证据）。

它回答：

- 请求是否落在有效 Work Grant 和 Scope（范围）内？
- Action 是否解析到唯一、不可覆盖的调用绑定？
- 前置门禁和平台门禁是否满足？
- 执行结果是否足以支撑治理结论？

`generate` 和 `enforce` 是治理职责，不称为“层”“阶段”或“模式”。Audit（审计）只是两类职责的只读观察面，不构成第三类职责。

## 4. 四个 SDD 治理域

### 4.1 `specification`

`specification`（规范治理域）治理“要做什么、为什么做、完成标准是什么”。

包括：

- 产品需求、用户故事和验收标准；
- 架构、接口、数据和安全设计；
- Schema、协议、约束和决策记录；
- 需求到实现、测试和交付的追溯关系。

示例：新增 API 字段前，先固化接口约束、兼容策略和验收条件。

### 4.2 `implementation`

`implementation`（实现治理域）治理“如何把已接受规范变成项目制品”。

包括：

- 产品源码和配置；
- 数据库迁移和基础设施代码；
- 生成代码、模板和资源；
- PoC（概念验证）和 Spike（技术探针）。

PoC 是 `development_mode=poc` 的开发模式，不是独立治理域。PoC 同样需要规范边界、实现范围和最低验证要求。

示例：根据已接受的接口规范修改解析器，并把写入限制在 Work Grant Scope 内。

### 4.3 `verification`

`verification`（验证治理域）治理“如何证明制品满足规范”。

包括：

- 单元、集成、端到端和验收测试；
- Lint、静态分析、类型检查和安全扫描；
- 模型评估、数据质量检查和回归比较；
- CI Required Check（必需检查）及其机器报告。

验证结论必须由可解析的 Postcondition（后置条件）和 Evidence 支撑。进程退出码为零本身不等于验证通过。

示例：测试 Action 只有在报告存在、Schema 有效且摘要链完整时，才能产生“测试通过”结论。

### 4.4 `delivery`

`delivery`（交付治理域）治理“如何把已验证制品交给外部系统或用户”。

包括：

- Build、Package 和制品签名；
- Push、Pull Request 和 Merge；
- Publish、Release 和 Deploy；
- 版本、目标、提交、制品摘要及平台审批。

示例：Release 必须绑定精确版本、Commit、制品摘要和受保护环境审批，不能用一次普通确认替代平台门禁。

## 5. 横向控制术语

以下概念作用于四个治理域，但不是新的 Governance Domain：

| 正式术语 | 中文 | 作用 |
|---|---|---|
| Agent Control | Agent 控制 | 约束角色、权限、Scope、Work Grant 和写入所有权 |
| Runtime Context | 运行上下文 | 声明 Runtime、工作目录、环境和资源约束 |
| Action Binding | 行为绑定 | 将 `action_id` 唯一解析为不可覆盖的调用 |
| Tool and Platform Control | 工具与平台控制 | 约束 CLI、MCP、API、CI/CD 和外部平台门禁 |
| Project Profile | 项目画像 | 表达不同项目类型的技术栈和领域差异 |
| Evidence | 证据 | 以 Schema、Postcondition 和摘要链支撑治理结论 |

使用规则：

```text
Governance Domain 决定“治理哪个 SDD 阶段”
Project Profile 决定“这是哪一种项目”
Action Binding 决定“允许调用什么”
Agent / Tool / Platform Control 决定“如何受控执行”
Evidence 决定“如何证明结果”
```

## 6. 项目画像

Library、Web、Backend、Mobile、Desktop、Data、ML 和 Infrastructure 不增加新的顶层治理域，而由 Project Profile 表达。

| Project Profile | 四域中的特有内容 |
|---|---|
| Library / SDK | API 兼容、语义化版本、包制品和发布仓库 |
| Web / Backend | API 契约、数据库迁移、环境配置和服务部署 |
| Mobile / Desktop | 平台构建、签名、商店审核和分阶段发布 |
| Data / ML | 数据血缘、数据质量、模型评估、模型和数据集版本 |
| Infrastructure | Plan / Apply、Provider Lock、状态、漂移和云平台审批 |
| Documentation | 内容规范、链接和格式验证、文档构建与发布 |

Project Profile 可以增加某个治理域的规则和绑定，但不得改变四个治理域的含义。

## 7. 覆盖定义

“矩阵中存在一条记录”只算名义覆盖。一个治理单元只有同时具备以下内容，才算有效覆盖：

```text
Source（来源）
  → Directive（单一指令）
  → Scope（适用范围）
  → Action Binding（唯一行为绑定，若该单元需要执行）
  → Preconditions（前置条件）
  → Postconditions（后置条件）
  → Evidence（证据）
  → Failure Semantics（失败语义）
```

覆盖等级固定为：

| 等级 | 名称 | 判断标准 |
|---|---|---|
| C0 | 名义覆盖 | 枚举中存在该治理单元 |
| C1 | 来源覆盖 | 存在可验证的 `source_ref` 和摘要 |
| C2 | 规则覆盖 | 存在明确 Directive、Scope 和失败语义 |
| C3 | 执行覆盖 | Action、Gate 和调用绑定可确定性解析 |
| C4 | 证据闭环 | Postcondition、Evidence 和执行后漂移验证完整 |

完整覆盖要求 16 个治理单元均达到其声明的目标等级。确实不适用的单元必须使用有来源、可审计的 N/A 决议；缺少规则不能被解释为 N/A。

Harness 只证明开发治理流程和证据链闭环，不证明业务需求本身正确，也不替代法律、安全、合规或产品负责人的领域裁决。

## 8. 自上而下的规范层级

Harness SDD 四域治理模型采用六级分解。下一级只能细化上一级，不能扩大上一级已经确定的权限或边界。

```text
L0 产品边界
└─ L1 三维治理模型：Audience × Responsibility × Governance Domain
   └─ L2 四个 SDD 治理域
      └─ L3 16 个 Governance Cell
         └─ L4 Cell 内的 Rule
            └─ L5 Action、Gate、Postcondition 与 Evidence
```

| 层级 | 决定什么 | 不决定什么 |
|---|---|---|
| L0 产品边界 | Harness 可以治理的对象和权威边界 | 具体项目命令 |
| L1 三维模型 | 谁、以什么职责、治理哪个域 | 项目技术栈 |
| L2 四域 | SDD 生命周期的稳定分类 | Agent、工具或平台权限 |
| L3 治理单元 | 一组规则的最小覆盖和验收单位 | 任意命令字符串 |
| L4 Rule | 来源、指令、Scope、前后置条件和失败语义 | 绕过 Action Binding 的调用 |
| L5 执行证据 | 实际调用、Gate Decision 和结果证据 | 新的长期授权 |

最小覆盖颗粒度固定为 Governance Cell。实现可以让一条 Rule 关联多个治理单元，但验证器仍必须分别计算每个单元的来源、规则、执行和证据覆盖，不能用“一条通用规则”直接宣告多个单元完成。

## 9. L0 产品目标与权威边界

### 9.1 目标

Harness 的目标是把仓库中的 SDD 活动变成可追溯、可约束、可验证的治理闭环：

```text
有来源的规范
  → 有范围的实现
  → 有证据的验证
  → 有门禁的交付
```

对于每项受治理活动，Harness 必须能够回答：

1. 活动基于什么来源事实？
2. 由哪类角色以什么治理职责发起？
3. 属于哪个 SDD 治理域？
4. 允许影响哪些 Scope？
5. 解析到哪个唯一 Action Binding？
6. 执行前后分别检查什么？
7. 什么 Evidence 足以支撑结论？
8. 失败时使用哪个稳定阻断码？

### 9.2 纳入边界

以下对象属于 Harness 目标治理范围：

- 仓库内的规范、源码、配置、测试、工作流和治理声明；
- Agent 的角色、委托、Scope、Work Grant 和写入所有权；
- 仓库声明的 Runtime、CLI、Shell、MCP、API 和项目脚本；
- Test、Build、CI、Push、Pull Request、Merge、Publish、Release 和 Deploy；
- 与上述 Action 直接关联的平台门禁、Postcondition 和 Evidence；
- 当前治理输入、执行结果和执行后漂移之间的摘要链。

### 9.3 排除边界

以下对象不属于 Harness 的自主决定范围：

- 产品目标、业务优先级和需求价值判断；
- 法律、合规、安全或财务责任人的专业裁决；
- 人工审批和外部平台保护规则本身；
- 未由仓库声明的账号、组织、密钥和云资源权限；
- 任意跨仓库、跨组织或跨环境的隐式写入权限；
- Session、Memory、Transcript 或 Agent 总结中的长期授权。

Harness 可以读取这些外部裁决的结构化结果并把它们作为前置条件或 Evidence，但不得替代权威主体作出裁决。

### 9.4 权威单向性

权限只能沿以下方向收窄：

```text
平台与用户权限
  ≥ 仓库 Standing Policy
  ≥ 当前 Governance Projection
  ≥ Work Grant
  ≥ Rule Scope
  ≥ 单次 Action Request
```

下游对象不得扩大上游权限。工具存在、Sandbox 可写、用户曾经确认或 Action 执行成功，都不能反向扩大 Governance Projection 或 Work Grant。

### 9.5 本地工作区与受控边界

Harness 必须按影响边界决定执行强度，不能把受控交付的高门槛照搬到本地开发。

| 边界 | 包含 | 目标体验 |
|---|---|---|
| Local Workspace（本地工作区） | 本地目录、未提交修改、Staged/Unstaged/Untracked 文件、`codex/**` 和 `agent/**` 等 Private Branch | 连续、低打扰、最低充分验证 |
| Controlled Boundary（受控边界） | Controlled/Unclassified Branch、远端仓库、制品仓库、外部 Issue、生产或共享环境 | 精确确认、平台门禁、完整交付证据 |

本地工作区内，Harness 应优先持续推进用户目标。只要修改仍位于工作区根目录、Private Branch 和当前目标的合理边界内，Scope 的内部细化或扩张只记录在内部工作状态中，不应逐次打断用户。

以下情况仍可中断本地工作：

- 即将执行不可恢复或明显破坏性的操作；
- 即将写出工作区、访问未授权资源或改变外部状态；
- 发现 Secret、凭据、恶意内容或重大安全风险；
- 缺少无法合理推断的业务、法律、合规或产品决策；
- 当前工作区位于 Controlled/Unclassified Branch，无法证明允许直接执行。

本地 `git commit` 是常规开发流程中唯一默认可见的决策检查点。Push、Pull Request、Merge、Release、Deploy 和远端 Issue 创建已经越过本地工作区，仍属于独立外部 Action。

## 10. L2 四域目标边界

| 治理域 | 必需输入 | 允许输出 | 明确排除 |
|---|---|---|---|
| `specification` | 目标、约束、既有规范、领域裁决 | 可追溯规范、验收标准、决策记录 | 代替业务负责人接受需求 |
| `implementation` | 已接受规范、Work Grant、项目画像 | Scope 内 Diff、配置、迁移或项目制品 | 无规范扩张、越界写入、隐式交付 |
| `verification` | 验收标准、变更集、已登记检查 | 机器报告、Gate Decision、验证 Evidence | 用退出码或自然语言代替证据 |
| `delivery` | 已验证 Commit、不可变制品、精确目标 | 外部状态变更及平台 Evidence | 隐式构建、隐式验证、覆盖冲突制品 |

### 10.1 域归属规则

一个 Action 可以影响多个治理域，但必须声明一个 Primary Domain（主治理域），其余作为 Related Domain（关联治理域）。

归属按 Action 的直接结果判断：

- 直接改变规范或验收标准：`specification`；
- 直接改变项目实现或生成项目制品：`implementation`；
- 直接产生质量结论或验证报告：`verification`；
- 直接改变远端、制品仓库或运行环境状态：`delivery`。

例如，构建命令如果只生成本地可测试制品，属于 `implementation`；如果生成准备发布的不可变制品，则属于 `delivery`。它是否通过测试由独立的 `verification` Rule 和 Evidence 决定。

### 10.2 禁止用工具名分类

治理域不能根据工具名称决定。同一个工具可以承载不同 Action：

```text
gh pr view       → verification 或只读观察
gh pr create     → delivery
gh pr merge      → delivery
```

必须先分类 Action 语义，再解析 Tool Binding；不能从“系统装了什么工具”推导“允许做什么”。

## 11. L4 全局规则不变量

以下规则适用于全部 16 个治理单元。

### 11.1 来源不变量

- 每条 Rule MUST 至少具有一个可验证的 `source_ref` 和内容摘要。
- 来源缺失、过期或冲突 MUST 失败关闭。
- Harness MUST NOT 把环境中偶然存在的工具或模型推测写成仓库事实。

### 11.2 身份不变量

- Rule MUST 明确声明一个 Audience、一个 Responsibility 和至少一个 Governance Domain。
- 请求中的 Audience MUST 与 Work Grant 和 Rule 一致。
- Agent 角色 MUST 使用机器可验证的单一职责契约；缺失或不受信时不得回退到通用 Agent。

### 11.3 投影不变量

- Rule、Work Grant、Action Request、Gate Decision 和 Evidence MUST 绑定同一 `projection_id`。
- 任一治理输入变化 MUST 使旧投影和旧 Work Grant 失效。
- Projection 不完整时只能进行只读诊断或投影修复，不能继续受治理写入。

### 11.4 Scope 不变量

- 每次写入 MUST 落在 Work Grant 和 Rule Scope 的交集内。
- 本地工作区、Private Branch 和当前用户目标内的 Scope 细化或扩张 MUST 内部记录，但不逐次要求用户确认。
- 写出工作区、进入 Controlled Boundary、改变外部状态或明显偏离用户目标的 Scope 扩张 MUST 形成绑定当前变更集的明确确认。
- 并行写者 MUST 具有可证明互不重叠的 Ownership；否则必须使用单写者。
- 未经明确接管，Harness MUST 保留工作区中与当前目标无关的用户修改。

### 11.5 调用不变量

- Agent 只能提交 `projection_id`、Work Grant、`action_id`、Audience、Scope 和类型化参数。
- Resolver MUST 唯一解析 `argv`、`cwd`、环境约束、平台目标和 Postcondition。
- Runner MUST 拒绝任意命令、参数拼接及对绑定字段的覆盖。

### 11.6 门禁不变量

- 修改状态或产生权威结论的 Action MUST 通过适用 Gate。
- Confirmation（确认）只能满足明确的范围或权限跃迁条件，不能替代分类、绑定、Postcondition 或平台门禁。
- 关键外部 Action MUST 绑定精确目标、Commit、制品摘要和当前确认。
- 本地普通编辑和最低充分验证 MUST 使用内部 Gate，不把 Gate 细节转化为逐工具用户确认。
- 用户明确输入 `git commit` 时，Harness MUST 把它识别为本地变更整理检查点，而不是 Push、Merge 或 Release 授权。

### 11.7 证据不变量

- 退出码为零、Agent 总结或界面显示不能单独支撑治理结论。
- Evidence MUST 包含请求、绑定、Gate Decision、实际结果、Postcondition 和必要的平台事实。
- 执行后 MUST 检查治理输入漂移；检测到漂移时不得沿用执行前结论。
- Evidence 是内部治理事实，不是默认用户界面。正常成功时只展示人话结果、实际修改范围、验证强度和剩余风险；原始摘要、Action ID、Gate 明细和报告路径仅在用户请求、失败诊断或审计场景中展开。

### 11.8 失败不变量

- 未知、未分类、缺失、歧义、过期、越界和证据不完整 MUST 失败关闭。
- 失败 MUST 返回稳定阻断码、阻断位置和可执行的 Handoff 条件。
- 验证器 MUST NOT 静默修复来源、冲突或执行结果。

## 12. L3 十六个治理单元

治理单元 ID 使用以下格式：

```text
<audience>.<responsibility>.<domain>
```

完整集合如下：

| Audience / Responsibility | `specification` | `implementation` | `verification` | `delivery` |
|---|---|---|---|---|
| `maintainer.generate` | MG-S | MG-I | MG-V | MG-D |
| `maintainer.enforce` | ME-S | ME-I | ME-V | ME-D |
| `consumer.generate` | CG-S | CG-I | CG-V | CG-D |
| `consumer.enforce` | CE-S | CE-I | CE-V | CE-D |

### 12.1 MG-S：`maintainer.generate.specification`

**目标**：为 Harness 自身的规范、Schema 和治理决议生成可追溯规则。

**输入边界**：规范 SSOT、Schema、已接受决议、版本信息及其摘要。

**MUST**：

- 识别规范 SSOT 与解释性文档的权威差异；
- 为术语、Rule 结构、兼容策略和完成定义生成来源绑定；
- 保留规范冲突并阻断发布，不能静默选择；
- 生成规范到 Schema、代码和测试的追溯要求。

**MUST NOT**：

- 把 README、计划或实现现状提升为平行政策；
- 从现有代码行为反向发明规范；
- 在缺少维护者决议时自动解决破坏性兼容问题。

**最低 Evidence**：规范文件摘要、决议状态、冲突报告、追溯矩阵和 Projection Lock。

### 12.2 MG-I：`maintainer.generate.implementation`

**目标**：为 Harness Core、Plugin、Skill、模板和生成器定义实现边界。

**输入边界**：已接受规范、Manifest、Lockfile、项目单元和 Ownership 声明。

**MUST**：

- 发现受管代码、生成代码、模板和配置路径；
- 生成写入 Scope、单写者或互斥 Ownership 规则；
- 从 Manifest 和仓库脚本生成有来源的 Action Binding；
- 区分普通代码修改、生成制品和控制面发布。

**MUST NOT**：

- 根据全局环境中存在的命令推导项目入口；
- 把任意 Shell 字符串登记为 Action；
- 允许生成器覆盖无法证明由 Harness 管理的用户内容。

**最低 Evidence**：项目单元清单、路径 Ownership、Action Graph、绑定来源和零写入预检结果。

### 12.3 MG-V：`maintainer.generate.verification`

**目标**：为 Harness 自身建立与影响范围匹配的验证规则。

**输入边界**：测试入口、CI Workflow、报告 Schema、影响规则和完成定义。

**MUST**：

- 区分 Inspect、Contract、Full 和 Platform Validation；
- 把验证语义绑定到唯一 Task 和预期报告；
- 为 Schema、Core、Plugin、文档和分发建立影响映射；
- 明确结论所需 Postcondition，不能只登记命令。

**MUST NOT**：

- 把未登记脚本当作正式验证；
- 用“命令成功”替代报告解析；
- 因验证成本高而自动降低必需验证级别。

**最低 Evidence**：测试和 CI 来源、影响映射、Task Binding、报告 Schema 和预期 Postcondition。

### 12.4 MG-D：`maintainer.generate.delivery`

**目标**：为 Harness 的 Push、PR、Merge、Package 和 Release 生成交付政策。

**输入边界**：分支规则、Workflow、环境保护、发布目标和制品策略。

**MUST**：

- 分类 Private 与 Controlled Branch；
- 为每类交付 Action 定义确认、平台门禁和精确参数；
- 分离 Build/Package 与 Publish/Release；
- 定义幂等重试和冲突制品处理政策。

**MUST NOT**：

- 把平台注册或工具连接视为交付授权；
- 生成 Force Push、绕过 Required Check 或覆盖冲突 Release 的绑定；
- 用本地成功结果代替平台 Evidence。

**最低 Evidence**：边界配置摘要、Workflow/Job 来源、环境保护要求、制品策略和交付 Action Graph。

### 12.5 ME-S：`maintainer.enforce.specification`

**目标**：确保 Harness 规范变更经过明确决议、精确 Scope 和一致性检查。

**输入边界**：当前投影、已接受术语或规范决议、变更 Plan 和文档 Scope。

**MUST**：

- 只修改 Plan 声明的规范和解释性文档；
- 保持 SSOT 唯一，并标明目标规范与现行运行契约的差异；
- 验证术语在规范、示例和完成定义中的一致性；
- 对破坏性语义变更产生明确迁移要求。

**MUST NOT**：

- 仅修改解释性文档却宣称运行政策已改变；
- 删除未被当前 Plan 接管的用户规则；
- 在规范冲突未解决时发布新 SSOT。

**最低 Evidence**：决议引用、实际文档 Diff、术语检查、迁移清单和执行后漂移结果。

### 12.6 ME-I：`maintainer.enforce.implementation`

**目标**：确保 Harness 实现只落实已接受规范并保持确定性、可回滚和最小写入。

**输入边界**：当前投影、实现 Work Grant、已接受规范、Ownership 和类型化参数。

**MUST**：

- 使用单写者或不重叠 Ownership；
- 保持相同输入产生语义稳定输出；
- 对初始化和生成操作执行零写入预检；
- 在写入失败时回滚受管路径并保留用户内容。

**MUST NOT**：

- 修改 Work Grant 外路径；
- 用代码实现静默解决规范冲突；
- 允许调用者覆盖 `argv`、`cwd`、环境或 Postcondition。

**最低 Evidence**：Action Request、Gate Decision、实际 Diff、幂等或回滚结果、Postcondition 和漂移检查。

### 12.7 ME-V：`maintainer.enforce.verification`

**目标**：确保 Harness 的质量结论来自已登记验证和机器可解析 Evidence。

**输入边界**：Impact Decision、验证 Task、当前 Commit/Projection 和报告要求。

**MUST**：

- 按影响范围选择最低充分但不低于政策要求的验证；
- 通过 `task_ref` 调用 Test、CI 或 Platform Validation；
- 校验报告 Schema、目标 Commit、Projection 和摘要链；
- 明确区分 Passed、Blocked、Failed 和 Confirmation Required。

**MUST NOT**：

- 直接绕过 Harness 运行具有 Test、Build 或 CI 语义的命令；
- 接受缺失报告的零退出码；
- 将旧 Commit 或旧 Projection 的报告复用于当前结论。

**最低 Evidence**：Impact Decision、Task Request、执行报告、Postcondition、Evidence Digest 和 G6–G7 结果。

### 12.8 ME-D：`maintainer.enforce.delivery`

**目标**：确保 Harness 自身交付绑定精确事实并经过独立确认和平台门禁。

**输入边界**：已验证 Commit、不可变制品、目标分支/Tag/环境及当前确认。

**MUST**：

- 分别处理 Push、PR、Merge 和 Release 的权限跃迁；
- Merge 使用独立确认并验证 Required Check；
- Release 绑定版本、Commit、制品摘要和受保护环境；
- 对重试执行幂等核对，冲突时失败关闭。

**MUST NOT**：

- Force Push 或直接绕过受控分支；
- 在 Release Action 内隐式重新构建制品；
- 覆盖 Commit、Tag 或摘要冲突的既有 Release。

**最低 Evidence**：精确请求摘要、确认包、平台 Gate、远端结果、制品摘要和交付报告。

### 12.9 CG-S：`consumer.generate.specification`

**目标**：从目标仓库事实生成适用于产品规范活动的治理规则。

**输入边界**：目标项目需求、设计、协议、约束、验收标准和既有治理声明。

**MUST**：

- 识别项目中的规范来源、权威顺序和继承边界；
- 建立需求、实现、验证和交付之间的追溯要求；
- 把缺失验收标准或冲突规范显式记录为 Governance Gap；
- 保留项目维护者的领域裁决，不擅自改写。

**MUST NOT**：

- 为目标项目发明业务需求或优先级；
- 把普通说明文档默认提升为规范 SSOT；
- 以通用最佳实践覆盖项目的显式决策。

**最低 Evidence**：规范来源清单、权威关系、追溯要求、Gap 列表和 Projection Lock。

### 12.10 CG-I：`consumer.generate.implementation`

**目标**：为目标项目的源码、配置、迁移、基础设施代码和 PoC 生成实现规则。

**输入边界**：项目 Manifest、Lockfile、源码结构、生成器、仓库脚本和 Project Profile。

**MUST**：

- 发现项目单元、受管路径和生成路径；
- 生成与规范、技术栈和风险匹配的实现 Scope；
- 把 PoC 标记为开发模式并声明隔离和退出条件；
- 为可执行实现行为生成唯一 Action Binding。

**MUST NOT**：

- 从 Agent 习惯或全局工具推测项目命令；
- 把 PoC 当作免除 Scope、验证或安全规则的理由；
- 在无法确定 Ownership 时允许并行写入。

**最低 Evidence**：项目画像、Manifest 来源、路径/Ownership、实现 Action Graph 和未解析 Gap。

### 12.11 CG-V：`consumer.generate.verification`

**目标**：为目标项目生成覆盖规范验收标准和变更影响的验证规则。

**输入边界**：验收标准、测试入口、质量工具、CI Workflow、报告格式和风险画像。

**MUST**：

- 将规范验收标准映射到可执行或人工 Handoff 的验证项；
- 区分单元、集成、端到端、安全、性能和领域评估；
- 为变更路径生成 Impact Rule 和最低验证集；
- 把缺失测试入口、报告或平台能力声明为阻断 Gap。

**MUST NOT**：

- 为项目虚构测试命令或质量阈值；
- 把存在测试目录等同于具有有效测试 Evidence；
- 自动跳过无法在本地执行的平台验证。

**最低 Evidence**：验收映射、测试/CI 来源、Impact Rule、报告要求和平台 Handoff 条件。

### 12.12 CG-D：`consumer.generate.delivery`

**目标**：为目标项目生成与其 Project Profile 匹配的交付规则。

**输入边界**：分支政策、CI/CD、制品仓库、运行环境、签名和审批配置。

**MUST**：

- 识别项目实际支持的交付 Action 和平台；
- 为 Library、Web、Mobile、ML、Infrastructure 等画像生成差异化参数约束；
- 明确不可变制品、环境晋级和回滚要求；
- 把外部权限或平台门禁缺失转为 Handoff。

**MUST NOT**：

- 因连接了 GitHub、云平台或商店账号而推定发布授权；
- 生成未在仓库或平台配置中声明的部署目标；
- 把 Build、Verification 和 Delivery 合并成不可审计的单一命令。

**最低 Evidence**：交付平台来源、环境/目标清单、制品策略、Action Binding 和 Handoff 要求。

### 12.13 CE-S：`consumer.enforce.specification`

**目标**：确保目标项目的规范变更有来源、可追溯且不越过领域权威。

**输入边界**：当前投影、规范 Work Grant、用户目标、领域约束和文档 Scope。

**MUST**：

- 在修改实现前固化必要的目标、约束和验收标准；
- 保留需求到实现和验证的追溯链接；
- 在本地工作区内持续记录 Scope、兼容性或验收标准变化；用户在 `git commit` 检查点选择影响分析时，再聚合呈现；
- 对进入受控边界或明显改变用户目标的变化请求一次变更集确认；
- 把需要产品、法律或安全裁决的问题移交权威主体。

**MUST NOT**：

- 替用户接受需求或宣称业务目标正确；
- 用代码行为反向覆盖显式规范；
- 将未解决问题静默改写成实现假设。

**最低 Evidence**：规范 Diff、来源引用、追溯关系、决议/Handoff 和漂移检查。

### 12.14 CE-I：`consumer.enforce.implementation`

**目标**：确保目标项目实现严格落在已接受规范和 Work Grant Scope 内。

**输入边界**：当前投影、实现 Work Grant、已接受规范、Project Profile 和 Action Request。

**MUST**：

- 只修改 Scope 和 Ownership 允许的路径；
- 使用仓库约定的架构、依赖和生成入口；
- 将 PoC 隔离、标记并记录退出或产品化条件；
- 记录实际 Diff，并在执行后检查治理输入漂移。

**MUST NOT**：

- 扩大需求、添加未授权功能或进行无关重构；
- 修改未声明的环境、账号或远端资源；
- 绕过绑定直接执行任意写命令。

**最低 Evidence**：Action Request、Gate Decision、实际 Diff、Scope/Ownership 校验、Postcondition 和漂移结果。

### 12.15 CE-V：`consumer.enforce.verification`

**目标**：确保目标项目的验证结论覆盖受影响规范和实现，并具有机器证据。

**输入边界**：当前投影、变更集、Impact Decision、已登记验证 Task 和验收标准。

**MUST**：

- 执行影响规则要求的最低验证集；
- 解析并验证报告内容，而不是只检查进程状态；
- 显式报告未验证范围、跳过项和平台 Handoff；
- 将 Evidence 绑定当前 Commit、Projection、Scope 和 Action。

**MUST NOT**：

- 把“未发现测试”解释为“无需测试”；
- 用旧报告、人工摘要或截图替代要求的机器报告；
- 在验证不完整时宣称可以交付。

**最低 Evidence**：Impact Decision、测试/检查报告、验收映射、跳过或 Handoff 列表和 G6–G7 结果。

### 12.16 CE-D：`consumer.enforce.delivery`

**目标**：确保目标项目交付使用已验证的不可变输入，并遵守精确确认和平台保护。

**输入边界**：已验证 Commit/Artifact、精确目标、当前确认、平台 Gate 和回滚条件。

**MUST**：

- 将 Build、Verification、Promotion 和 Delivery 的 Evidence 串联；
- 对 Push、PR、Merge、Publish、Release 和 Deploy 分别解析权限；
- 验证目标、版本、Commit、制品摘要、环境和审批；
- 返回远端状态、平台运行 ID 和可核对的最终 Evidence。

**MUST NOT**：

- 对未验证或在验证后发生漂移的输入执行交付；
- 在交付时隐式替换 Commit、制品或目标；
- 绕过分支保护、环境审批、签名或商店审核。

**最低 Evidence**：交付请求摘要、当前确认、上游验证链、平台 Gate、远端结果、制品摘要和漂移检查。

## 13. L4 Rule 最小结构

每条 Rule 至少包含：

| 字段 | 要求 |
|---|---|
| `rule_id` | 在当前 Projection 中唯一且稳定 |
| `audience` | 精确一个：`maintainer` 或 `consumer` |
| `responsibility` | 精确一个：`generate` 或 `enforce` |
| `domains` | 至少一个，并声明唯一 Primary Domain |
| `projection_id` | 与当前 Projection Lock 一致 |
| `source_refs` | 至少一个可验证来源 |
| `directive` | 单一、可判断的 MUST 或 MUST NOT 指令 |
| `scope` | 路径、资源或目标的封闭范围 |
| `inheritance` | 继承来源与冲突时失败策略 |
| `action_id` / `invocation` | 需要执行时必须唯一绑定；纯规则可为空 |
| `preconditions` | 执行或结论成立前必须满足的事实 |
| `postconditions` | 结果和结论必须满足的可验证条件 |
| `enforcement_level` | `documented`、`verified` 或 `enforced` |
| `confirmation_policy` | 无、按变更集一次或按交付包一次 |
| `evidence` | 必需 Evidence 类型和摘要关系 |
| `failure` | 稳定阻断码和 Handoff 条件 |

一条 Rule 如果只写“遵循最佳实践”“适当测试”或“必要时确认”，因无法确定性判断，不构成有效规则覆盖。

## 14. 跨域流转规则

### 14.1 正向流转

```text
Specification Baseline
  → Implementation Change Set
  → Verification Evidence
  → Delivery Artifact / Remote State
```

| 流转 | 必需条件 | 禁止捷径 |
|---|---|---|
| Specification → Implementation | 目标、Scope、约束和验收标准可追溯 | 直接把模糊意图当作写入授权 |
| Implementation → Verification | 实际 Diff、影响范围和当前 Projection 已确定 | 只按计划范围选测试，不看实际 Diff |
| Verification → Delivery | 必需检查通过，Evidence 绑定精确输入 | 用本地口头结论替代平台 Required Check |
| Delivery → Conclusion | 远端状态、目标和制品摘要核对完成 | 仅凭请求已发送宣称交付成功 |

### 14.2 反向反馈

以下情况必须返回上游治理域：

- 实现发现规范歧义：返回 `specification`；
- 验证发现实现缺陷：返回 `implementation`；
- 验证发现验收标准不足：返回 `specification`；
- 交付发现制品或平台配置错误：根据原因返回 `implementation`、`verification` 或 `specification`。

反向反馈产生新的变更集或 Scope 时，旧确认不得自动沿用。

### 14.3 跨域原子性

跨域 Pipeline 可以统一编排多个 Action，但每个 Action 仍必须保留独立的：

- Primary Domain；
- Action Binding；
- Gate Decision；
- Postcondition；
- Evidence；
- 失败状态。

Pipeline 成功不能掩盖某个阶段缺少 Evidence；Pipeline 失败也不能把尚未执行的后续阶段标记为失败执行。

## 15. 十六单元覆盖验收

### 15.1 单元验收记录

每个 Governance Cell 必须生成独立 Coverage Record：

| 字段 | 含义 |
|---|---|
| `cell_id` | 完整三维治理单元 ID |
| `target_level` | 目标覆盖等级 |
| `observed_level` | 当前实际覆盖等级 |
| `rule_ids` | 支撑该单元的 Rule |
| `source_digests` | 来源摘要 |
| `action_ids` | 需要执行时的 Action Binding |
| `evidence_requirements` | 达到目标等级所需 Evidence |
| `gaps` | 缺失、歧义或不可执行项 |
| `status` | `covered`、`gap` 或 `not-applicable` |

### 15.2 完整覆盖判定

目标模型的完成条件是：

```text
16 个 Cell 均有唯一 Coverage Record
AND 每个 Cell 的 observed_level ≥ target_level
AND 所有 Gap 已关闭
AND 所有 N/A 具有来源和权威决议
AND 不存在未分类 Action 或旁路
```

目标状态下，16 个单元均应具备达到 C4 的治理能力。C4 表示该单元能够在需要时形成完整证据闭环，不表示每次本地小改动都必须运行最高强度测试或向用户展示全部 Evidence。

单次 Action 的实际执行强度必须服从影响范围和边界：

- 本地低风险修改可以只执行 T0/T1；
- 组件或契约变化使用 T2；
- 只有高风险、受控交付或用户明确要求时才升级到 T3；
- 迁移期间可以声明阶段性覆盖目标，但不得把缺少必要能力的 C0–C3 表述为完整治理闭环。

### 15.3 N/A 边界

N/A 只能用于项目事实上不存在某类行为的情况，不能用于规避治理成本。

允许示例：纯本地实验仓库没有任何外部 Delivery Action，因此对应 Delivery Cell 由维护者声明 N/A，并提供仓库边界和无交付绑定的 Evidence。

禁止示例：项目存在生产部署，但因为尚未配置平台门禁而把 Delivery Cell 标记为 N/A。此时状态必须是 Gap，并阻断生产交付。

### 15.4 项目画像覆盖

Project Profile 不改变 16 个单元，但可以增加单元内规则：

| Project Profile | 必须增加的典型规则 |
|---|---|
| Library / SDK | API 兼容、版本、包完整性和发布仓库 |
| Web / Backend | API/数据迁移、环境配置、部署和回滚 |
| Mobile / Desktop | 平台构建、签名、商店审核和分阶段发布 |
| Data / ML | 数据血缘、评估基线、模型/数据集版本和模型发布 |
| Infrastructure | Plan/Apply 分离、状态保护、漂移和云审批 |
| Documentation | 内容规范、链接/格式验证、构建和发布 |

如果项目同时匹配多个 Profile，规则取并集；冲突必须显式解决，不能按更宽松规则静默覆盖。

## 16. 旧术语迁移

| 旧术语 | 目标术语或定位 |
|---|---|
| `agent-runtime` | `Agent Control` 横向控制 |
| `engineering-runtime` | `Runtime Context`，并按行为进入实现、验证或交付域 |
| `poc` | `implementation` 域中的 `development_mode=poc` |
| `source-code` | `implementation` |
| `test-code` | `verification` |
| `other-tools` | 删除；工具必须具有明确 Action Binding 和治理域 |
| `2 × 6 Projection` | `2 × 2 × 4 Governance Matrix` |
| “2 层 6 类” | 禁止使用；三个维度不存在上下层级关系 |

## 17. 规范状态与实施边界

本文件锁定目标术语和迁移方向，但不单独建立运行时政策。

在以下构件完成同一变更集迁移并通过契约验证前，`docs/specification.md` 负责定义已接受目标；现有 1.0 Schema、编译器和 2 × 6 Artifact 仍是实际运行协议：

- 规范 SSOT；
- Common 与 Governance Schema；
- Source Facts 和 Action Graph 分类；
- Projection 编译器与覆盖验证器；
- Agent 编排、Skill 和初始化模板；
- 契约测试、评估和用户文档。

任何单独替换枚举、但没有同步迁移绑定、Gate、Evidence 和测试的实现，都不得宣称符合 Harness SDD 四域治理模型。

## 18. 给使用者的人话说明

### 18.1 一句话解释

Harness 不是替你写一套更复杂的开发流程，而是给 Agent 加上四条护栏：

```text
先说清楚要做什么
  → 只改允许改的地方
  → 用仓库认可的方法验证
  → 没有明确确认就不交付到外部
```

你负责描述目标和作出业务决定；Harness 负责从仓库中找出真实入口、控制修改范围、验证结果并阻止危险捷径。

### 18.2 它帮你解决什么问题

| 你原来容易遇到的问题 | Harness 怎么处理 | 你得到什么 |
|---|---|---|
| 不知道项目该运行哪个命令 | 只使用仓库有来源的 Action Binding | 不靠 Agent 猜命令 |
| Agent 顺手改了无关文件 | 用 Work Grant、Scope 和 Ownership 限制写入 | Diff 更小、更容易审查 |
| 需求、代码和测试互相对不上 | 按规范、实现、验证、交付四域建立追溯 | 知道每项修改为什么存在 |
| Agent 说“测试通过”，但只有退出码 | 检查报告、Postcondition 和 Evidence | 结论可以核对 |
| 修代码时顺手 Push、Merge 或 Deploy | 把交付视为独立权限跃迁 | 没有精确确认就不改变远端 |
| 仓库已经变化，Agent 还沿用旧计划 | 用 `projection_id` 和执行后漂移检查 | 旧授权自动失效 |
| 缺少工具、门禁或平台权限 | 返回稳定阻断码和 Handoff | 明确知道缺什么，不危险回退 |

### 18.3 你不需要做什么

正常使用时，你不需要：

- 手工选择 16 个 Governance Cell；
- 猜测测试、构建或发布命令；
- 自己拼接 `argv`、`cwd` 或环境变量；
- 逐条批准普通只读操作和 Scope 内修改；
- 根据 Agent 的自然语言总结判断测试是否真的通过。

这些内容应该由当前治理投影、Action Resolver、Gate 和 Evidence 决定。

### 18.4 你需要告诉 Harness 什么

一个高质量请求通常包含五件事：

| 信息 | 要回答的问题 | 示例 |
|---|---|---|
| 目标 | 最终要产生什么变化 | 订单接口支持配送备注 |
| 范围 | 已知要影响哪里 | API、订单模型和相关测试 |
| 非目标 | 明确不要顺手做什么 | 不改数据库，不升级依赖 |
| 验证 | 你关心什么完成标准 | 兼容旧请求，并有回归测试 |
| 交付边界 | 是否允许改变外部状态 | 本次不 Push、不创建 PR |

推荐输入模板：

```text
$harness

目标：
范围：
不要做：
完成标准：
交付边界：
```

范围不确定时可以留空，并要求 Harness 先只读分析。不要为了“写完整提示词”自己发明仓库路径或命令。

### 18.5 Harness 会怎样处理你的请求

以“给订单接口增加配送备注”为例：

```text
你的目标
  → 读取当前仓库事实和治理投影
  → 找到相关规范、源码和测试
  → 生成本次 Work Grant 与 Scope
  → 修改规范或确认现有验收标准
  → 在 Scope 内修改实现
  → 运行受影响的已登记验证
  → 检查报告与执行后漂移
  → 返回修改摘要、最低验证、剩余风险或阻断原因
```

如果你明确写了“本次不 Push”，流程会停在验证完成，不进入 Delivery（交付）域。

### 18.6 示例一：普通功能开发

**你的输入：**

```text
$harness

目标：订单创建接口增加可选的 delivery_note 字段。
范围：接口规范、订单请求模型和相关测试。
不要做：不改数据库结构，不升级依赖，不重构其他订单代码。
完成标准：旧请求保持兼容；新字段长度最多 200；增加有效值和超长值测试。
交付边界：只完成本地修改和验证，不 Push，不创建 PR。
```

**四域如何工作：**

| 治理域 | Harness 应做什么 |
|---|---|
| 规范 | 找到或补充字段类型、长度、可选性和兼容要求 |
| 实现 | 只修改请求模型和直接相关代码 |
| 验证 | 运行受影响测试并解析报告 |
| 交付 | 因明确禁止 Push/PR，本次不进入 |

**你最终应该看到：**

- 改了哪些文件以及为什么；
- 做了什么最低充分验证；
- 哪些完成标准已覆盖，哪些没有验证；
- 是否存在剩余风险；
- 明确说明没有改变远端状态。

### 18.7 示例二：修复 Bug

**你的输入：**

```text
$harness

修复夏令时切换当天订单时间显示早一小时的问题。
先定位根因，再做最小修复并增加回归测试。
不要改变公共 API，不升级日期时间依赖，也不要顺手统一全项目时间格式。
验证通过后停止，不 Push。
```

**Harness 帮你控制的风险：**

- “最小修复”会变成明确 Scope，而不是大范围重构；
- 如果根因与现有规范冲突，先返回规范问题，不擅自选择业务时区；
- 回归测试必须覆盖复现条件；
- 没有报告或报告不属于当前变更时，不能宣称修复完成。

### 18.8 示例三：PoC

**你的输入：**

```text
$harness

做一个检索方案 PoC，比较关键词检索和向量检索的效果。
所有代码放在 experiments/retrieval 下，不接入生产入口，不修改线上依赖。
使用一小组脱敏样例，输出比较结果和已知局限。
只做最低可重复验证，不部署。
```

**Harness 应该如何理解：**

- PoC 属于 Implementation（实现）域的一种开发模式，不是“什么规则都可以省略”；
- Scope 被隔离在实验目录；
- 仍要记录输入样例、比较指标和最低复现步骤；
- 因为禁止部署，不能调用任何 Delivery Action；
- 如果实验需要真实生产数据或新云权限，应返回 Handoff，而不是自行获取。

### 18.9 示例四：准备发布

**你的输入：**

```text
$harness

检查版本 2.3.0 是否满足发布条件。
先核对规范、变更、测试、制品和目标 Commit，给出发布准备报告。
在我确认前不要 Push Tag、创建 Release 或部署。
```

**Harness 应分成两步：**

1. 只读检查和 Verification：核对版本、Commit、必需检查、制品摘要和缺口；
2. Delivery：只有你确认精确目标和制品后，才执行已登记发布 Action。

“准备发布”不等于“授权发布”。如果检查发现制品是在另一个 Commit 上构建的，应阻断而不是重新构建后直接发布。

### 18.10 示例五：正确的阻断

假设你说：

```text
$harness

运行完整测试并告诉我是否可以发布。
```

但仓库没有登记完整测试入口或报告格式。Harness 的正确行为不是猜一个 `pytest`、`npm test` 或 `make test`，而是返回类似：

```text
blocked
TOOL_ACTION_UNCLASSIFIED 或 GOVERNANCE_EVIDENCE_INCOMPLETE

缺少：
- 有来源的完整测试 Action；
- 可以解析的测试报告；
- “允许发布”所需的平台或制品 Evidence。
```

阻断不是任务失败，而是 Harness 成功阻止了一个没有证据支撑的结论。

### 18.11 什么时候需要你确认

| 情况 | 是否通常需要确认 |
|---|---|
| 只读查看仓库 | 不需要 |
| 在本地工作区和当前目标内修改 | 不逐命令确认 |
| 运行已登记的常规验证 | 不逐工具确认 |
| 本地 Scope 内部细化或合理扩张 | 内部记录，不打断 |
| 用户输入 `git commit` | 询问是否执行工作区级影响分析 |
| 写出工作区、偏离目标或进入受控边界 | 需要按变更集确认 |
| 创建远端 Issue | 必须确认具体远端信息和 Issue 内容 |
| Push、创建 PR、Merge、Release、Deploy | 需要绑定精确事实的交付确认 |
| 外部平台审批 | 必须由平台或权威人员完成 |

确认只批准明确的范围或权限跃迁。它不能把未知命令、失败测试、缺失 Evidence 或过期 Projection 变成有效结果。

### 18.12 如何看结果

| 结果 | 人话解释 | 你接下来做什么 |
|---|---|---|
| `completed` | 本地工作完成，已做最低充分验证 | 查看修改摘要和剩余风险 |
| `confirmation-required` | 即将扩大范围或改变外部状态 | 核对目标、Scope、Commit 和制品 |
| `blocked` | 缺少来源、绑定、门禁或必要结果 | 按人话说明补资料或完成 Handoff |
| `failed` | Action 已执行但结果未通过 | 修复后重新生成当前 Evidence |

默认摘要至少应告诉你：

- 改了什么；
- 使用了 T0、T1、T2 还是 T3 验证；
- 哪些检查没有运行以及原因；
- 剩余风险是什么；
- 没有未经授权的远端状态变化。

Projection、Action Binding、Gate 和 Evidence Digest 继续在内部保留，但正常成功时不要求用户阅读。用户可以主动要求“展开技术证据”查看详情。

### 18.13 当前能力与目标模型

当前 Harness 1.0 已提供仓库事实发现、Action Binding、Work Grant、G0–G7、Evidence 和关键交付门禁。

本文件定义的四域和 16 个治理单元是下一版目标分类与覆盖标准。在规范 SSOT、Schema、编译器和测试完成同步迁移前：

- 你今天仍然通过 `$harness` 描述任务并使用当前运行契约；
- 不需要在请求中写 `MG-S`、`CE-I` 等 Cell ID；
- 文档中的四域可以帮助你说清目标和验收标准；
- 不应把“文档已经定义”误解为“四域运行时已经全部实现”。

## 19. 本地工作区连续执行与 Commit 检查点

### 19.1 目标体验

本地工作区的默认体验是：

```text
用户描述目标
  → Harness 连续分析、编辑和做最低充分验证
  → 用简短人话汇报结果
  → 等待用户明确输入 git commit
```

Harness 不应因为读取文件、调整本地 Scope、修改 Private Branch 或执行已登记的低成本检查而频繁询问用户。

### 19.2 最低充分验证

本地验证强度固定分为四级：

| 等级 | 适用变化 | 默认动作 |
|---|---|---|
| T0 Inspect | 文档、注释、小型非运行配置 | 只读检查，不运行测试 |
| T1 Nearest | 单函数、单组件、小范围 Bug | 最近的单元测试、语法或类型检查 |
| T2 Component | 公共接口、共享模块、Schema 或跨文件行为 | 受影响组件、契约或集成测试 |
| T3 Full | 核心框架、依赖锁、迁移、安全、CI/CD 或受控交付 | 完整测试、完整 CI 或平台验证 |

选择规则：

- 默认从 T0 开始，只在影响事实要求时升级；
- 测试数量多不等于更充分，必须能够解释它与实际 Diff 的关系；
- 小改动不得仅因“更安全”而自动运行 T3；
- 仓库已有 Pre-commit Hook 时不得绕过，但 Harness 不额外重复同等验证；
- 用户可以明确要求更高或更低验证强度；低于仓库硬性门禁时只能用于本地实验，不能支撑受控交付。

正常结果只展示：

```text
完成：修改 3 个文件
验证：T1，运行 6 个相关测试，全部通过
未运行：完整测试；本次未影响共享接口
剩余风险：无已知风险
```

### 19.3 `git commit` 的唯一常规触发语义

只有用户明确发出 `git commit`、提交这些修改或等价指令时，Harness 才进入本地 Commit 检查点。

进入后只询问一次：

```text
是否对当前工作区全部未提交变更执行影响面分析？
默认 Issue 目标：local
如需远端 Issue，请同时提供或确认远端信息。
```

如果用户选择“不分析”：

1. 确认 Commit Scope；
2. 检查明显 Secret、冲突、异常大文件和未解决合并状态；
3. 不额外运行大范围测试；
4. 保留“未做工作区级影响分析”的本地记录；
5. 完成 Commit。

如果用户选择“分析”：

1. 快照当前工作区；
2. 分析从当前 `HEAD` 到工作区的全部 Staged、Unstaged 和 Untracked 变化；
3. 按规范、实现、验证、交付四域整理影响；
4. 生成 Issue 格式计划、Commit Scope 和最低验证建议；
5. 展示 Issue 目标及内容，向用户确认一次；
6. 确认后写入本地或远端 Issue；
7. 执行已确认计划和最低充分验证；
8. 没有新的重大 Scope 变化时，直接完成原始 Commit，不再追加第三次确认。

影响分析以工作区实际状态为事实来源，因此天然跨对话。Session、Memory 和 Transcript 只能帮助解释意图，不能代替当前文件状态。

### 19.4 分析范围与 Commit 范围

Workspace Impact Scope（工作区影响分析范围）覆盖：

```text
当前 HEAD
  → Staged 修改
  → Unstaged 修改
  → Untracked 文件
```

Commit Scope（提交范围）由已确认 Issue 计划决定，可以小于工作区影响分析范围。

Harness MUST：

- 识别并分组不同目标或不同来源的变更；
- 保留与当前目标无关的用户修改；
- 不自动 Stage 未经计划接管的文件；
- 在 Issue 计划中列出本次 Commit 包含和排除的范围。

### 19.5 Issue 格式计划

影响分析结果至少整理为：

```text
标题：
目标：
当前变更：
影响模块：
规范影响：
兼容性风险：
建议补充修改：
Commit 包含：
Commit 排除：
最低验证范围：
明确不执行：
完成标准：
```

Issue 不是新的需求授权。Issue 内容超出原始用户目标时，必须在确认前明确标注。

### 19.6 项目级 Issue 配置

对普通消费者项目，Issue 目标是项目级 Harness 配置；没有远端配置时默认使用本地 Issue。以下为目标配置示例，尚未进入当前 Schema：

```yaml
issue_planning:
  default_destination: local
  local_directory: .harness/issues
  remote:
    provider: null
    project: null
```

字段含义：

| 字段 | 含义 |
|---|---|
| `default_destination` | `local` 或 `remote`；缺失时必须视为 `local` |
| `local_directory` | 本地 Issue 的持久化目录 |
| `remote.provider` | GitHub、GitLab、Jira 或其他受支持 Provider |
| `remote.project` | `owner/repository`、Project Key 或等价远端标识 |

远端信息不得包含 Token、密码或私钥。认证由已连接的 Provider、平台或用户环境负责。

Harness 产品自身采用更严格的维护约定：维护者迭代统一使用 `bigsmartben/harness-scaffold` 的 GitHub Issues 作为唯一 SSOT。本地文档只链接远端 Issue，不复制标题、正文、状态或清单形成第二份可编辑记录。

### 19.7 本地 Issue

默认本地 Issue 写入项目配置指定的目录，例如：

```text
.harness/issues/2026-07-28-order-delivery-note.md
```

本地 Issue 用于：

- 跨对话保存已确认的工作区计划；
- 记录 Commit Scope、最低验证和完成状态；
- 让后续 Agent 从工作区事实继续执行；
- 在没有远端项目管理系统时保持可追溯性。

本地 Issue 创建和更新仍限制在工作区内，不代表允许 Push 或发布。

### 19.8 远端 Issue

创建远端 Issue 会改变外部状态，必须同时满足：

- 用户选择或确认 `remote`；
- 明确 Provider；
- 明确 Repository、Project 或 Project Key；
- 展示将要创建的标题和正文；
- 用户确认该精确目标和内容；
- 存在可用的远端连接，但不能从“连接存在”推定授权。

确认包至少包含：

```text
Provider：
Remote Project：
Issue Title：
Issue Body Summary：
Labels / Assignee（若有）：
```

用户确认后，Harness 才能创建远端 Issue，并把返回的 Issue ID/URL 写入本地工作状态。

如果远端信息缺失或创建失败，Harness MUST 请求补充或 Handoff，不能静默退回本地 Issue，也不能改投另一个远端。

### 19.9 受控动作不继承 Commit 授权

`git commit` 只授权本地 Commit 流程，不授权：

- Push；
- 创建 Pull Request；
- Merge；
- Publish、Release 或 Deploy；
- 创建未在确认包中声明的远端 Issue；
- 修改 Controlled/Unclassified Branch 的保护政策。

这些 Action 仍按 Controlled Boundary 的规则独立确认和验证。
