# SDD Harness

Harness 3.0 是一个面向人机协同的本地规范治理脚手架（specification
governance scaffold）。它帮助人与智能体（Agent）围绕同一套仓库自定义指导
开展协作，而不是把仓库改造成由 Harness 强制控制 Agent 行为的环境。

仓库所有者在 `.harness/harness.yaml` 中定义适合当前项目的指导；Harness
校验这些指导的结构，并将其确定性投影到模型锁文件，供人和 Agent 共同读取。
固定的是治理框架和数据契约，自定义的是每个仓库真正关心的规则内容。

当前且唯一支持的契约版本是 `3.0.1`。

## 仓库定位

Harness 位于“仓库约定”和“人机协作”之间：它为双方提供一个本地、明确且可验证
的共同上下文，但不接管任何一方的判断或操作。

| 定位维度 | Harness 的选择 | 具体示例 |
|---|---|---|
| 协作目标 | 让人和 Agent 读取同一套仓库指导 | 双方都能看到“修改公共 API 后应运行契约测试” |
| 自定义主体 | 由仓库所有者定义项目规则 | Python 库和前端应用可以声明不同的实现指导 |
| 固定边界 | 固定三轴模型、字段契约和投影算法 | 所有仓库都有四个治理域，但每个域中的规则可不同 |
| 交付形式 | 生成可重算的本地模型锁 | 相同配置始终得到相同的 `model.lock.json` |
| Agent 关系 | 为 Agent 提供上下文，不控制 Agent | Harness 能校验规则格式，不能强迫 Agent 运行命令 |

例如，仓库所有者可以写入：

```yaml
verification:
  - rule_id: contract-tests
    directive: 修改公共 API 后应运行契约测试。
    scope:
      - src/**
      - tests/**
```

人和 Agent 都可以读取这条指导。Harness 能确认它位于 verification（验证）域、
字段合法且投影结果没有漂移，但不会运行测试、判断 Agent 是否遵守，也不会阻止
代码合并。

## 想要解决的问题

| 问题 | 常见表现 | Harness 的处理方式 |
|---|---|---|
| 协作上下文分散 | 规则散落在聊天、口头约定和多份文档中，换人或换 Agent 后丢失 | 用一个显式配置作为仓库规则输入 |
| 规范与动作混杂 | “应运行测试”被误解为工具获得了执行或阻断权限 | 规则固定为 `kind: guidance`（指导），不携带动作或授权 |
| 自定义规则缺少共同结构 | 每个仓库都有自己的约定，但人和 Agent 无法稳定定位 | 用 specification、implementation、verification、delivery 四个治理域分类 |
| 生成结果容易漂移 | 调整顺序、手工改锁文件或版本不一致后难以判断结果是否可信 | 规范化排序、记录摘要，并从源配置重算完整模型锁 |
| 治理工具侵入仓库 | 为共享几条指导而被迫引入任务运行器、远程服务或复杂控制面 | 只管理配置、模型锁和分发 Skill 三个本地文件 |

这里的目标不是替团队决定“正确做法”，而是让团队自行定义的做法能够被人和
Agent 一致地发现、理解和复核。例如，Harness 可以保存“提交前应运行单元测试”
这条指导，但是否采用该规则、怎样运行测试以及失败后如何处理，仍由仓库团队和
自己的工具链决定。

## 适用与不适用

| 适合使用 Harness | 不适合由 Harness 承担 |
|---|---|
| 人和 Agent 需要共享仓库级自定义指导 | 强制控制 Agent 的决策和行为 |
| 多个协作者需要稳定理解规则所属领域 | 执行测试、构建、发布或 Git 操作 |
| 希望规则投影可以重算并检测漂移 | 提供身份认证、角色权限或审批 |
| 希望保持本地、最小且不依赖远程 Provider | 编排 CI/CD 或替代项目工作流系统 |

右栏需求可以由专门的权限、自动化和 CI/CD 工具承担，并与 Harness 保存的指导
并存。例如，Harness 记录“发布前应通过测试”，CI 系统负责实际执行和阻断。

## 固定模型

模型由三条彼此正交的轴组成：

| 轴 | 中文含义 | 固定值 |
|---|---|---|
| Audience | 适用角色 | `maintainer`、`consumer` |
| Responsibility | 治理职责 | `generate`、`enforce` |
| Governance Domain | 治理域 | `specification`、`implementation`、`verification`、`delivery` |

三条轴的笛卡尔积固定产生 16 个 Cell（治理单元）。`2-2-4` 只是数量简称，
不是层级结构，也不是用户可配置项。

Responsibility 中的 `enforce`（契约约束）只表示严格校验固定模型并拒绝漂移，
不表示强制 Agent 执行仓库指导。例如，篡改 Cell ID 会导致 `validate` 失败；
Agent 没有运行某条指导中的测试命令，则不属于 Harness 能够判定的事项。

## 快速开始

```text
uv tool install <source-or-package>
cd <target-repository>
sdd-harness init
sdd-harness validate
sdd-harness inspect
```

`init` 只创建三个文件：

```text
.harness/harness.yaml
.harness/governance/model.lock.json
.agents/skills/harness/SKILL.md
```

配置中的唯一扩展点是四个治理域下的规则实例：

```yaml
schema_version: 3.0.1
rule_instances:
  specification:
    - rule_id: acceptance-before-code
      directive: 实现前应给出可观察的验收条件。
      scope: ['docs/**', 'src/**']
  implementation: []
  verification: []
  delivery: []
```

修改配置后运行：

```text
sdd-harness project
sdd-harness validate
sdd-harness inspect
```

`project` 原子替换单一锁文件；`validate` 和 `inspect` 都是只读操作。规则固定
投影为 `kind: guidance`，不能带有动作、授权、分支、交付、验证等级或 Provider
字段。

## 四个命令

| 命令 | 作用 | 写入 |
|---|---|---|
| `init` | 初始化最小 v3 配置、Skill 和锁文件 | 仅创建缺失的三个目标文件 |
| `project` | 从合法配置重建确定性锁文件 | 原子替换一个锁文件 |
| `validate` | 验证配置、固定模型、规则和摘要 | 无 |
| `inspect` | 查看版本、摘要、规则数量和诊断 | 无 |

## 破坏性变更

3.0.1 不读取、补全、迁移、映射、别名化或回退到 v1/v2。不存在双版本读取器、
弃用期或兼容包装器。已有外部 consumer（使用方）必须自行备份并清理旧 Harness
控制面，然后重新运行 `sdd-harness init`；Harness 不提供自动转换工具。

## 文档

- [2-2-4 治理模型白皮书](docs/harness-2x2x4-governance-model-whitepaper.md)
- [规范说明](docs/specification.md)
- [快速开始](docs/quickstart.md)
- [仓库结构](docs/repository-structure.md)
- [行为验收追踪](docs/acceptance-traceability.md)
- [3.0.1 发布说明](docs/release-notes-3.0.1.md)
- [3.0.0 发布说明](docs/release-notes-3.0.0.md)

维护计划、状态、清单和验收结果只记录在
[GitHub Issue #32](https://github.com/bigsmartben/harness-scaffold/issues/32)
及其子 Issue。
