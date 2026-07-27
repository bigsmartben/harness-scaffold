# AI Coding Harness 用户用例

版本：`0.3.0`
状态：P3–P4 Available（P4 本地产品验收）；P5 In Progress
最后更新：2026-07-24

本文把 [`docs/specification.md`](docs/specification.md) 中的规范规则投影为用户可观察、可验收的行为。本文不重新定义政策；出现冲突时，以规范为准。

## 目录

- [用例约定](#用例约定)
- [用例索引](#用例索引)
- [UC-001：接管已有 CI/CD 项目](#uc-001接管已有-cicd-项目)
- [UC-002：为无 CI/CD 项目建立最小交付体系](#uc-002为无-cicd-项目建立最小交付体系)
- [UC-003：查询并直接使用已注册普通工具](#uc-003查询并直接使用已注册普通工具)
- [UC-004：Agent 在批准写入范围内完成修改](#uc-004agent-在批准写入范围内完成修改)
- [UC-005：根据变更选择最低充分验证集](#uc-005根据变更选择最低充分验证集)
- [UC-006：执行内部 Merge Pipeline](#uc-006执行内部-merge-pipeline)
- [UC-007：处理外部触发请求](#uc-007处理外部触发请求)
- [UC-008：使用结构化 Evidence 诊断失败任务](#uc-008使用结构化-evidence-诊断失败任务)
- [UC-009：用户确认后执行 Publish](#uc-009用户确认后执行-publish)
- [UC-010：审查或更新已有 Harness 配置](#uc-010审查或更新已有-harness-配置)
- [UC-011：写入范围扩大后重新 Handoff](#uc-011写入范围扩大后重新-handoff)
- [UC-012：由 CI/CD 平台阻止未授权正式交付](#uc-012由-cicd-平台阻止未授权正式交付)
- [规则覆盖索引](#规则覆盖索引)

## 用例约定

### 参与者

| 参与者 | 职责 |
|---|---|
| 用户（User） | 提出目标、批准写入范围、确认 `expensive` 与 `critical` CI/CD 动作 |
| Agent / Skill | 分析项目、执行边界内修改、提交 Change Manifest、消费 Evidence |
| Harness | 维护配置、按语义分类 CI/CD Task、生成 Request、调度已允许 Backend、生成 Evidence |
| Backend | 实际执行 Local 或 CI 任务，例如 GitHub Actions、pytest、npm |
| CI/CD 平台 | 隔离正式交付凭证，执行 Required Checks、Protected Environment 和平台审批 |
| 外部系统 | 产生 Push、PR、Webhook 或 Schedule 事件 |

### 自动化等级

| 等级 | 含义 |
|---|---|
| `routine` | 低成本常规检查；项目明确 `auto_allowed` 后可自动执行 |
| `expensive` | Integration、E2E、Full CI、大型 Build；每次必须确认 |
| `critical` | Push、Merge、Publish、Release、Deploy；每次确认并经过平台门禁 |

### 验收表达

每项验收条件都必须能通过自动化测试、结构化 Evidence 或明确的人工确认记录判定。不得使用“看起来合理”“足够完整”等无法复现的判断。

## 用例索引

| ID | 用户目标 | 阶段 | 主要结果 |
|---|---|---|---|
| `UC-001` | 接管已有 CI/CD | P2–P4 | 建立引用映射，识别平台门禁，不无条件重写 Workflow |
| `UC-002` | 为新项目建立交付体系 | P2–P4 | 生成最小 Harness 配置 |
| `UC-003` | 找到并调用普通能力 | P2–P3 | 一次查询得到确定入口，不触发逐次审批 |
| `UC-004` | 在批准范围内修改 | P2–P3 | 范围内自由，范围扩张时停止并 Handoff |
| `UC-005` | 运行最低充分验证 | P3 | 选择验证级别，并按自动化等级执行或请求确认 |
| `UC-006` | 完成 Merge | P3–P4 | 本次确认且 Required Checks 通过后由平台 Merge |
| `UC-007` | 处理外部事件 | P3–P4 | 事件按 CI/CD 语义和等级形成 Request |
| `UC-008` | 诊断失败任务 | P3 | 先读摘要，必要时渐进读取日志 |
| `UC-009` | 发布制品或部署 | P3–P4 | 本次独立确认及 Protected Environment 门禁 |
| `UC-010` | 审查或更新 Harness | P2–P3 | 幂等更新并显式报告漂移 |
| `UC-011` | 扩大写入范围 | P2–P3 | 原 Grant 失效并重新 Handoff |
| `UC-012` | 阻止未授权正式交付 | P4 | CI/CD 凭证隔离和平台门禁拒绝副作用 |

## UC-001：接管已有 CI/CD 项目

- **阶段**：P2–P4
- **主要参与者**：用户
- **协作参与者**：Agent / Skill、Harness、现有 Backend
- **用户目标**：让 Harness 接管现有项目的工具发现和交付入口，同时保留已有 Workflow、脚本和构建实现。
- **关联规则**：`TR-001`、`TR-002`、`TR-003`、`TR-007`、`DM-006`、`DM-010`、`HF-001`、`EV-002`、`EV-005`

### 前置条件

- 项目至少存在一个可识别的 Runtime、包脚本、构建文件或 CI/CD 定义。
- 用户已请求 `initialize-ai-coding-harness` 对当前项目执行 Adopt。
- Harness 尚未获得修改现有 Workflow 内容的授权。

### 触发条件

用户确认开始只读发现。

### 主成功流程

1. Harness 只读扫描 Runtime、CLI、MCP 配置、仓库脚本、包脚本、`AGENTS.md` 和 CI/CD 文件。
2. Harness 记录每项发现的来源路径，不把推断当作事实。
3. Harness 检查受保护 Workflow 是否仍由外部事件直接启动。
4. Harness 生成 Adopt Plan，列出计划创建或最小合并的 `AGENTS.md`，以及 Registry、Task、Impact、Pipeline 和 Adapter 映射。
5. 用户批准计划及写入范围。
6. Harness 创建 `.harness/` 配置，并引用已有 Workflow 或脚本。
7. Harness 校验所有引用存在、工具入口可解析、外部触发受控且配置关系有效。
8. Harness 返回 Adopt Evidence。

### 替代与失败流程

- 发现多个冲突的 Runtime 版本时，返回 `CONFIG_INVALID` 并列出来源，不自行选择。
- 所需工具没有可靠入口时，返回 `TOOL_NOT_REGISTERED`。
- 计划要求改写已有 Workflow 时，必须单独列入写入范围；未确认则不改写。
- 已有 `AGENTS.md` 时，Plan 必须展示保留原指令的合并 Diff；无法安全合并或用户未确认时保持 `blocked`，不得用模板覆盖。
- 受保护 Workflow 仍由 Push、PR、Webhook 或 Schedule 直接启动时，返回 `PROTECTED_TRIGGER_UNCONTROLLED`。用户未批准改造前可以完成索引，但 Adopt 状态保持 `blocked`。
- Backend 暂时不可用时，配置可以生成，但验证状态为 `blocked`，并返回 `BACKEND_UNAVAILABLE`。

### 结束状态与 Evidence

- `.harness/` 中存在可验证的工具、任务、影响和 Pipeline 映射。
- 已有 Workflow 内容保持不变，除非用户明确批准修改。
- 已有 `AGENTS.md` 指令保持不变；Harness 只添加已在 Plan 中展示并获批的轻量入口。
- Evidence 包含发现来源、创建文件、引用 Backend、校验结果和 blocker codes。

### 验收条件

- 给定一个包含 `package.json` 和 `.github/workflows/ci.yml` 的 Fixture，Adopt 后原文件内容校验和不变。
- 给定已有自定义 `AGENTS.md` 的 Fixture，Adopt 后原指令仍存在，且未披露的覆盖写入为零。
- `tasks.yaml` 能追溯到现有包脚本或 Workflow。
- 直接外部触发的受保护 Workflow 在未改造前不能得到 `passed` Adopt Evidence。
- 同一输入重复 Adopt 不产生无意义 Diff。

## UC-002：为无 CI/CD 项目建立最小交付体系

- **阶段**：P2–P4
- **主要参与者**：用户
- **协作参与者**：Agent / Skill、Harness
- **用户目标**：为没有 CI/CD 的项目建立与实际技术栈匹配的最小工具索引和交付体系。
- **关联规则**：`TR-001`、`TR-002`、`TR-007`、`DM-003`、`DM-007`、`HF-001`、`EV-002`、`EV-005`

### 前置条件

- 项目没有可接管的 CI/CD Pipeline。
- 项目存在可验证的 Python 或 Node 技术栈事实。
- 用户已请求 Bootstrap。

### 触发条件

用户允许 Harness 进行只读技术栈发现。

### 主成功流程

1. Harness 读取 Python 或 Node 的版本、依赖和现有脚本事实。
2. Harness 选择 Local 或 GitHub Actions 的最小 Adapter。
3. Harness 生成 Bootstrap Plan，列出计划创建的配置和任何新建 Workflow。
4. 用户批准写入范围和 Backend 选择。
5. Harness 创建最小 `.harness/` 配置。
6. 只有用户批准 GitHub Actions 时，才创建对应 Workflow。
7. Harness 运行结构与引用校验，并返回 Bootstrap Evidence。

### 替代与失败流程

- 同时存在 Python 与 Node 且无法确定主要交付单元时，返回 `IMPACT_UNRESOLVED`。
- 没有可验证技术栈事实时，停止并列出缺失信息。
- 用户只批准 Local 时，不创建 `.github/workflows/`。
- 生成路径超出批准范围时，转入 `UC-011`。

### 结束状态与 Evidence

- 项目拥有最小 Tool Registry、Task Catalog、Impact、Merge 和 Publish 配置。
- 未被选择的技术栈和 Backend 不产生模板文件。
- Evidence 记录技术栈事实源、所选 Adapter、创建文件和校验状态。

### 验收条件

- 纯 Python Fixture 只生成 Python 相关条目。
- 纯 Node Fixture 只生成 Node 相关条目。
- 未批准 GitHub Actions 时不存在新 Workflow。
- 重复 Bootstrap 保持幂等。

## UC-003：查询并直接使用已注册普通工具

- **阶段**：P2–P3
- **主要参与者**：Agent / Skill
- **协作参与者**：Harness Tool Registry
- **用户目标**：让 Agent 不再猜测 Runtime、CLI、Shell、MCP 或 API 的名称、版本、入口和调用方式，同时不把 Registry 变成权限代理。
- **关联规则**：`WB-002`、`TR-001`、`TR-002`、`TR-003`、`TR-004`、`TR-005`、`TR-006`、`TR-007`、`DM-001`、`DM-008`

### 前置条件

- 项目存在通过 Schema 校验的 `tools.yaml`。
- Agent / Skill 已知所需能力，例如 `repository-search`。

### 触发条件

Agent / Skill 按能力查询 Registry。

### 主成功流程

1. Registry 返回匹配工具的稳定 ID、用途、版本事实源、入口、工作目录和用法。
2. Agent / Skill 根据条目直接调用普通工具。
3. 调用产生写入时进入 `UC-004`，将计划或实际 Diff 与 Work Grant 比较；Harness 不宣称宿主级拦截普通工具写入。
4. Agent / Skill 使用结果继续领域工作，无需普通工具逐次授权。

### 替代与失败流程

- 能力未注册时，返回 `TOOL_NOT_REGISTERED`，不得连续试用多个未知二进制。
- 入口不存在或版本事实源失效时，返回 `TOOL_ENTRY_STALE`。
- MCP Server 存在但 Tool 未索引时，按未注册 Tool 处理。
- 查询动作命中 Test、Build、CI、Push、Merge、Publish、Release 或 Deploy 语义时，Registry 返回对应 `task_ref`，Agent 把 CI/CD 意图交给 Harness。

### 结束状态与 Evidence

- Agent 使用确定入口完成普通工具调用，或得到稳定 blocker code。
- Registry 查询不产生身份审批记录。

### 验收条件

- `repository-search` 一次解析为 `rg` 的正确项目入口。
- Python 条目能追溯到项目版本事实源。
- MCP 查询能定位到具体 Tool，而不只返回 Server。
- `npm test`、Shell 中的等价测试命令或 `github.create_release` 等动作按语义解析为同类 Task。
- 普通 CLI、Shell、MCP Tool 和只读分析动作可直接调用，不产生逐次 Harness 审批。
- Registry Schema 拒绝 `allowed_agents`、`denied_agents` 等身份授权字段。

## UC-004：Agent 在批准写入范围内完成修改

- **阶段**：P2–P3
- **主要参与者**：Agent / Skill
- **协作参与者**：用户、Harness
- **用户目标**：允许 Agent 在任务范围内自由实现，同时避免修改扩散到无关路径。
- **关联规则**：`WB-001`、`WB-002`、`WB-003`、`WB-004`、`WB-005`、`WB-006`、`HF-001`、`EV-004`

### 前置条件

- 用户已批准包含目标、写入路径和 Merge 目标的 Work Grant。
- Agent 已读取适用的项目事实与工具 Registry。

### 触发条件

Agent 开始修改工作区。

### 主成功流程

1. Harness 向 Agent 提供当前可写路径。
2. Agent 在范围内自由选择实现与普通工具。
3. Agent 完成修改并提交 Change Manifest。
4. Harness 将计划路径与实际 Diff 同写入范围比较。
5. 所有实际修改均在范围内，工作进入 `UC-005`。

### 替代与失败流程

- Agent 计划写入新路径时，转入 `UC-011`。
- 计划阶段发现越界时停止写入并转入 `UC-011`。
- 事后发现越界时，将交付状态标记为 `blocked`，不得进入 Merge。
- 批量格式化或生成影响范围扩大时，同样转入 `UC-011`。

### 结束状态与 Evidence

- Change Manifest 与实际 Diff 可相互校验。
- Evidence 记录生效写入范围、实际路径和校验结果。

### 验收条件

- 只修改批准路径时边界检查通过。
- 修改一个未批准路径时 Merge 保持 `blocked`。
- 文档不把该检查描述为普通文件写入的宿主级硬拦截。

## UC-005：根据变更选择最低充分验证集

- **阶段**：P3
- **主要参与者**：Harness
- **协作参与者**：Agent / Skill、Backend
- **用户目标**：以覆盖风险所需的最小成本验证修改，避免 Agent 默认运行全量 CI。
- **关联规则**：`DM-002`、`DM-003`、`DM-004`、`DM-005`、`DM-009`、`DM-011`、`HF-006`、`EV-002`、`EV-004`、`EV-005`

### 前置条件

- 存在有效的 Change Manifest、实际 Diff、Task Catalog 和 Impact Rules。
- 写边界校验已通过。

### 触发条件

Agent 提交执行意图，或 Work 流程进入验证阶段。

### 主成功流程

1. Harness 比较 Agent 声明与实际 Diff。
2. Harness 读取模块、依赖、公共契约和构建配置事实。
3. Harness 根据 `impact.yaml` 选择 `inspect`、`affected`、`contract`、`integration` 或 `full`。
4. Harness 为每个所选 Task 解析 `routine`、`expensive` 或 `critical`，记录规则来源和升级原因。
5. 只有显式 `auto_allowed: true` 的 `routine` Task 可以自动执行。
6. `expensive`、`critical` 或未明确允许自动执行的 Task 只生成 Request；获得本次确认和适用平台门禁后才调用 Backend。
7. Harness 返回验证 Evidence 或待确认 Request。

### 替代与失败流程

- Agent 推荐 `full` 但没有 DM-004 事实时，Harness 忽略升级建议。
- 影响事实缺失或冲突时，返回 `IMPACT_UNRESOLVED`，不静默执行全量 CI。
- 推荐 `full` 时仍必须把 Full CI 作为 `expensive`；没有本次确认时 Backend 调用次数为零。
- Task 未声明自动化等级或无法分类时，返回 `HANDOFF_REQUIRED`，不启动 Backend。
- Task Backend 不可用时，返回 `BACKEND_UNAVAILABLE`。

### 结束状态与 Evidence

- Evidence 或 Request 包含验证级别、自动化等级、选中和跳过的 Task、选择依据、确认状态、持续时间及结果。
- 失败时提供 blocker code 或首个有效错误。

### 验收条件

- 文档修改选择 `inspect`。
- 单模块内部修改选择 `affected`。
- 公共 API 修改至少选择 `contract`。
- 只有满足 DM-004 时选择 `full`。
- 无法判断影响时不启动全量 CI。
- 显式允许的低成本 `routine` Unit Test 可以自动执行。
- Integration、E2E、Full CI 或大型 Build 无本次确认时 Backend 调用次数为零。
- 同一测试语义经 Shell、CLI、MCP 或 API 表达时得到相同自动化等级。

## UC-006：执行内部 Merge Pipeline

- **阶段**：P3–P4
- **主要参与者**：用户
- **协作参与者**：Harness、Backend、Agent / Skill
- **用户目标**：完成必要验证后看清本次受控分支 Merge 目标，并在强确认和平台 Required Checks 通过后合并。
- **关联规则**：`TR-008`、`DM-001`、`DM-008`、`DM-010`、`HF-001`、`HF-003`、`HF-005`、`EV-004`、`EV-006`

### 前置条件

- Work Grant 有效。
- 写边界检查和 `UC-005` 所选必要验证全部通过。
- Merge 目标没有发生变化。

### 触发条件

Harness 收到进入 Merge Pipeline 的执行意图。

### 主成功流程

1. Harness 校验 Grant、Change Manifest 和验证 Evidence。
2. Harness 运行已允许的 `routine` 门禁；需要 `expensive` 验证时先走 UC-005 的确认。
3. Harness 将目标分类为受控分支，生成绑定 Task、动作语义、完整目标 ref、commit SHA、策略版本、Request digest 和验证 Evidence 的 Merge Request。
4. 用户对上述未变化绑定作出本次强确认。
5. GitHub Required Checks 与 Branch Protection 决定平台是否允许 Merge。
6. 平台执行 Merge 并返回 Run、提交和审批状态。
7. Harness 归一化正式 Merge Evidence。

### 替代与失败流程

- 任一必要 Task 失败时停止 Merge。
- Evidence 不完整时返回 `EVIDENCE_INCOMPLETE`。
- Merge 目标或写入范围改变时返回 `HANDOFF_REQUIRED`。
- 缺少本次 Merge 确认时，Merge Backend 调用次数为零。
- 本地或 `git-remote` Backend 试图直接修改受控或未分类分支时，返回 `CONTROLLED_BRANCH_GATE_REQUIRED` 与 `HANDOFF_REQUIRED`，调用次数为零。
- Required Checks 缺失或失败时 Merge 保持 `blocked`。
- 本地 Merge 命令的结果只能用于调试，不能生成正式 Merge Evidence。

### 结束状态与 Evidence

- 成功时存在与 Change Manifest、本次确认、目标分支、提交摘要和平台门禁绑定的 Merge Evidence。
- 失败时工作区保持可修复状态，Evidence 指向失败 Task。

### 验收条件

- 已确认的一次 Merge Request 不为其内部每个 `routine` Job 重复请求确认。
- Work Grant 或验证通过不能替代本次 Merge 确认。
- 缺失一项必要 Evidence 时不能报告 Merge Ready。
- Required Checks 未满足时平台不完成 Merge。
- Merge 失败不会自动转入 Publish。

## UC-007：处理外部触发请求

- **阶段**：P3–P4
- **主要参与者**：用户
- **协作参与者**：外部系统、Harness
- **用户目标**：让外部事件按 CI/CD 动作语义创建 Request，不能绕过相应自动化等级和平台门禁。
- **关联规则**：`HF-002`、`HF-005`、`HF-006`、`EV-002`、`EV-004`、`EV-005`

### 前置条件

- Harness 已注册相应外部事件来源。
- 事件目标属于受保护 Pipeline。

### 触发条件

发生 Push、PR、Webhook 或 Schedule 事件。

### 主成功流程

1. Harness 接收事件并创建只读 Request。
2. Harness 解析来源、动作语义、目标、候选 Pipeline、预计验证级别和自动化等级。
3. 若只是显式自动允许的 `routine` Task，可以按政策自动 Dispatch。
4. 若为 `expensive` 或 `critical`，Harness 返回 `HANDOFF_REQUIRED`。
5. 用户查看摘要并批准或拒绝。
6. 批准后生成与 Request 摘要绑定的确认，再进入相应 CI/CD 流程。

### 替代与失败流程

- 事件来源无法验证时，Request 保持 `blocked`。
- 用户拒绝或超时，`expensive` 或 `critical` Pipeline 不启动。
- 事件内容在确认前发生变化时，旧 Request 失效。

### 结束状态与 Evidence

- 批准时 Evidence 记录外部事件、用户确认和生成的 Grant。
- 拒绝时记录关闭原因，不产生交付副作用。

### 验收条件

- 外部事件本身不绕过确认直接触发 Push、Merge、Publish、Release 或 Deploy。
- 外部事件触发 `expensive` Task 时，无本次确认的 Backend 调用次数为零。
- Request 摘要变化后必须重新确认。
- 只有显式自动允许的 `routine` Task 可由外部事件自动 Dispatch。

## UC-008：使用结构化 Evidence 诊断失败任务

- **阶段**：P3
- **主要参与者**：Agent / Skill
- **协作参与者**：Harness、Backend
- **用户目标**：用最少上下文定位失败，同时保留完整审计材料。
- **关联规则**：`EV-001`、`EV-002`、`EV-003`、`EV-004`、`EV-005`、`EV-006`

### 前置条件

- 一个 CI/CD Task 返回 `failed` 或 `blocked`。
- Backend 产生了日志或失败状态。

### 触发条件

Harness 开始归一化 Backend 结果。

### 主成功流程

1. Harness 保存完整日志或稳定日志引用。
2. Harness 提取失败 Task、首个有效错误、相关文件行号、失败用例和 blocker codes。
3. Agent 先读取结构化摘要并尝试修复。
4. 只有摘要不足时，Agent 请求与问题相关的日志片段。
5. 修复后重新执行 Harness 选择的必要 Task。

### 替代与失败流程

- Backend 没有提供完整日志时，返回 `EVIDENCE_INCOMPLETE`。
- 无法解析主错误时，摘要必须说明解析失败并保留日志引用，不得捏造文件或行号。
- 日志路径不存在时，Evidence 状态为 `blocked`。

### 结束状态与 Evidence

- Agent 上下文默认只包含摘要和必要日志片段。
- 完整日志仍可通过 `run_id` 追溯。

### 验收条件

- 默认响应不嵌入完整日志。
- 摘要包含 EV-002 要求的字段。
- 解析失败时不会产生虚假的 `primary_error`。

## UC-009：用户确认后执行 Publish

- **阶段**：P3–P4
- **主要参与者**：用户
- **协作参与者**：Harness、Backend
- **用户目标**：仅在看清本次版本、制品和目标后执行正式发布或部署。
- **关联规则**：`DM-001`、`DM-008`、`DM-010`、`HF-004`、`HF-005`、`HF-006`、`EV-004`、`EV-006`

### 前置条件

- Merge 已完成，且存在完整 Merge Evidence。
- Publish Plan 已解析版本、制品、目标环境和所需任务。

### 触发条件

用户请求准备 Publish。

### 主成功流程

1. Harness 生成 Publish Plan 和影响摘要。
2. Harness 返回 `PUBLISH_CONFIRMATION_REQUIRED`。
3. 用户明确确认本次版本、制品和目标。
4. CI/CD 平台校验 Protected Environment、审批状态和最小权限凭证。
5. 平台允许后才执行 `pipelines/publish.yaml`。
6. Backend 返回发布 Run、结果和制品引用。
7. Harness 生成 Publish Evidence。

### 替代与失败流程

- 用户只批准过 Work 或 Merge 时，仍必须停止并请求 Publish 确认。
- 版本、制品或目标在确认后变化时，旧确认失效。
- Protected Environment 未批准时 Publish / Deploy Job 不启动。
- Agent / Skill 能读取发布 Secret 或高权限 Token 时保持 `blocked`。
- 发布 Task 失败时不得把部分成功描述为完整成功。
- 用户拒绝或未响应时，不调用 Publish Backend。

### 结束状态与 Evidence

- 成功时 Evidence 绑定本次确认、版本、制品、目标、Workflow、提交摘要、平台审批和 Backend 结果。
- 失败时保留已产生副作用的清单和后续恢复入口。

### 验收条件

- Work Grant 和 Merge Evidence 不能替代 Publish 确认。
- 确认摘要变化后必须重新确认。
- 没有本次明确确认时 Publish Backend 调用次数为零。
- Protected Environment 未批准时目标系统不产生 Publish / Deploy 副作用。
- 本地发布命令结果不能替代平台签发的正式 Publish Evidence。

## UC-010：审查或更新已有 Harness 配置

- **阶段**：P2–P3
- **主要参与者**：用户
- **协作参与者**：Agent / Skill、Harness
- **用户目标**：检查 AGENTS 治理区块、工作区 / 分支边界、Registry、Task、Impact 和 Pipeline 是否仍与项目事实一致，并安全应用必要更新。
- **关联规则**：`TR-006`、`TR-007`、`DM-005`、`DM-006`、`DM-007`、`HF-001`、`EV-002`、`EV-005`

### 前置条件

- 项目已经存在 `.harness/`。
- 用户请求 Audit 或 Update。

### 触发条件

Harness 开始只读比较配置与当前仓库事实。

### 主成功流程

1. Harness 校验 YAML 结构和跨文件引用。
2. Harness 比较 `AGENTS.md` 标记完整性、私有 / 受控分支模式、工具版本事实源、任务入口、Workflow 和模块影响规则。
3. Harness 报告有效项、漂移项、缺失项和已失效项。
4. 对需要写入的修复生成字段级 Drift Plan，并标出保留与修改的字段。
5. 用户批准写入范围。
6. Harness 保留自定义 Tools、Tasks、Adapters、项目 `mode` 和 `AGENTS.md` 标记外指令，只替换唯一成对标记内的治理入口，并应用明确批准的最小变更后重新校验。

### 替代与失败流程

- 只请求 Audit 时不得写文件。
- 配置不是 `0.3.0` 时返回 `CONFIG_INVALID`，要求重新 Adopt 或 Bootstrap，不自动迁移。
- 配置与事实冲突但无法自动决定时，返回 `CONFIG_INVALID`，保留差异。
- `AGENTS.md` 标记缺失、重复或无法无损合并时，返回 `CONFIG_INVALID` 与 `HANDOFF_REQUIRED`，写入次数为零。
- Update Plan 扩大写入范围时转入 `UC-011`。

### 结束状态与 Evidence

- Audit 产生只读报告；Update 产生变更 Diff 和校验 Evidence。
- 未发生漂移时重复 Update 不产生文件变化。

### 验收条件

- Audit 模式文件校验和全部不变。
- 入口失效时报告 `TOOL_ENTRY_STALE`。
- 自定义配置与 Harness 标记外的项目指令保持不变。
- 幂等 Update 的第二次执行 Diff 为空。

## UC-011：写入范围扩大后重新 Handoff

- **阶段**：P2–P3
- **主要参与者**：用户
- **协作参与者**：Agent / Skill、Harness
- **用户目标**：在任务确实需要新增写入路径时，看清原因与影响后再决定是否扩大范围。
- **关联规则**：`WB-003`、`WB-004`、`WB-005`、`HF-005`、`HF-006`、`EV-004`、`EV-005`

### 前置条件

- 存在有效 Work Grant。
- Agent、生成器或 Task 计划写入未批准路径。

### 触发条件

Harness 发现计划路径或实际 Diff 超出边界。

### 主成功流程

1. Harness 停止当前受控流程。
2. Harness 返回同时包含 `WRITE_SCOPE_EXPANDED` 和 `HANDOFF_REQUIRED` 的 blocker codes，列出新增路径、原因和影响。
3. 当前 Grant 标记失效。
4. 用户批准、缩小或拒绝扩张。
5. 批准时生成新 Grant；拒绝时 Agent 调整实现或终止任务。

### 替代与失败流程

- 事后发现越界时，Merge 必须保持 `blocked`。
- Harness 不承诺对普通文件写入提供宿主级前置拦截。
- 用户只批准部分路径时，新 Grant 只能包含批准子集。

### 结束状态与 Evidence

- Evidence 记录旧范围、拟新增范围、用户决策和新 Grant。
- 未批准路径不得进入后续 Merge Evidence。

### 验收条件

- Harness 不会静默扩大 glob。
- 用户拒绝时保持 Merge `blocked`，保留用户工作区现状且不得自动回滚。
- 新 Grant 能追溯到本次 Handoff。

## UC-012：由 CI/CD 平台阻止未授权正式交付

- **阶段**：P4
- **主要参与者**：CI/CD 平台
- **协作参与者**：Agent / Skill、Harness、用户
- **用户目标**：即使 Agent 不遵循 Skill 指令，也只能在本地工作区和私有分支内使用 Harness 直接执行；受控或未分类分支无法绕过强确认与平台门禁。
- **关联规则**：`DM-008`、`DM-011`、`HF-003`、`HF-004`、`HF-006`、`EV-004`、`EV-005`、`EV-006`

### 前置条件

- GitHub Actions 使用最小权限 Token 或短期 OIDC 身份。
- 高权限 Push、Merge、Publish 和 Deploy 凭证不暴露给 Agent / Skill。
- Branch Protection、Required Checks 和适用的 Protected Environment 已启用。
- Harness Request、本次确认和平台审批状态可追溯。

### 触发条件

Agent / Skill 请求执行 `critical` 动作，或未经确认尝试推动正式交付状态。

### 主成功流程

1. Harness 按动作语义将请求分类为 `critical`。
2. Harness 分类目标分支；受控模式优先，未分类按受控失败关闭。
3. Harness 生成绑定本次 Task、动作语义、完整目标 ref、提交摘要、策略版本、Request digest、版本、制品和环境的 Request。
4. 没有匹配强确认时，Harness 不调用直接 Backend，并返回 `CONTROLLED_BRANCH_GATE_REQUIRED` 与 `HANDOFF_REQUIRED`。
5. 强确认后，CI/CD 平台继续校验 Required Checks、Branch Protection、Protected Environment 和平台审批。
6. 任一平台门禁不满足时，正式副作用不发生。
7. 平台允许后执行动作，并返回可追溯 Run 与审批状态。
8. Harness 归一化正式交付 Evidence。

### 替代与失败流程

- CI/CD 动作无法分类时返回 `ACTION_CLASSIFICATION_UNRESOLVED` 和 `HANDOFF_REQUIRED`，Backend 调用次数为零。
- 受保护 Workflow 可被未经确认的外部事件直接启动时返回 `PROTECTED_TRIGGER_UNCONTROLLED`。
- Agent / Skill 能读取高权限凭证时，相关动作保持 `blocked`。
- Protected Environment 缺少审批时返回 `PUBLISH_CONFIRMATION_REQUIRED` 或 `HANDOFF_REQUIRED`。
- 普通 MCP、网络、Shell、Runtime、CLI 或本地文件写入不属于本用例的强制范围。

### 结束状态与 Evidence

- 未满足确认或平台门禁的正式交付动作没有目标系统副作用。
- Evidence 记录 Task、自动化等级、Workflow、Run ID、提交摘要、本次确认、审批状态和适用的制品摘要。

### 验收条件

- 未确认的 Integration、E2E、Full CI 或大型 Build 不产生 CI/CD Run。
- 未确认的 Push、Merge、Publish、Release 或 Deploy 不产生目标系统副作用。
- 受控或未分类分支不能通过 Local 或 `git-remote` Backend 直接修改。
- Required Checks 缺失时 Merge 保持 `blocked`。
- Protected Environment 未批准时 Publish / Deploy Job 不启动。
- Agent / Skill 没有可直接使用的高权限交付凭证。
- 普通 MCP、CLI、Shell 和网络调用不经过 Harness 权限代理。
- 本地执行结果不能伪造正式 CI/CD Evidence。
- Git Remote Push 是仅面向私有分支的窄化正式 Push 通道：例如确认 `origin + refs/heads/codex/demo + abc123` 后，只能非强推该 commit 到该 ref；`main` 和未分类分支必须被拒绝，其 Evidence 不代表 Merge、Publish、Release 或 Deploy 已获准。

### P4 平台闭环验收

- 使用本地 `ready` 平台事实 Fixture 验证完整配置返回 `ready`。
- 使用本地 `blocked` Fixture 分别验证过宽凭证、缺失 Required Checks、未受控触发器和缺失环境审批返回稳定 blocker codes。
- 未确认或门禁失败的 Fixture 断言 Backend 调用次数为零。
- 在全新本地目录完成最小 Local Bootstrap、Schema / 跨文件验证，并重复应用确认 Diff 为空。
- 上述本地验收只验证 Adapter 接口、状态迁移和 Evidence 绑定，不授予正式交付权限。
- P4 的本地产品验收已通过并标记为 `Available`。具体正式交付动作仍必须取得真实 GitHub Run、Required Checks、平台审批、受保护分支或环境及适用制品摘要；本地验收不授予该次交付权限。

## 规则覆盖索引

| 规则域 | 覆盖用例 |
|---|---|
| `WB-*` | `UC-003`、`UC-004`、`UC-011` |
| `TR-*` | `UC-001`、`UC-002`、`UC-003`、`UC-010` |
| `DM-*` | `UC-001`、`UC-002`、`UC-005`、`UC-006`、`UC-009`、`UC-010`、`UC-012` |
| `HF-*` | `UC-001`、`UC-002`、`UC-004`、`UC-006`、`UC-007`、`UC-009`、`UC-011`、`UC-012` |
| `EV-*` | 所有执行和失败相关用例，重点为 `UC-005` 至 `UC-012` |
