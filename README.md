# SDD Harness

Harness 是 Codex App / Codex CLI 中的仓库内 Agent 治理框架：它从仓库事实生成治理规范，并确保规范通过 Action、Gate 和 Evidence 被执行。当前规范版本为 `1.0.0`。

## 快速开始

```text
uv tool install <source-or-package>
sdd-harness init --yes
```

随后在目标仓库的 Codex App 或 Codex CLI 中显式调用：

```text
$harness
```

`sdd-harness init` 是确定性初始化入口，`$harness` 是正式工作入口。Plugin、Hook 和 MCP 只提供可选纵深防御，不保存治理状态，也不是基础前置条件。

## 工作方式

```text
Repository Snapshot
  → source-backed facts
  → Action Graph
  → Governance Projection (maintainer/consumer × 6 subdomains)
  → AGENTS.md + .codex + .agents + .harness/governance
  → Work Grant + G0–G7
  → accepted Evidence / stable blocker codes
```

| 层 | 作用 | 例子 |
|---|---|---|
| Agent 编排 | 理解目标、分解阶段、解释缺口 | `repo_mapper` 提取事实，`governed_worker` 单写 |
| 确定性 Core | 摘要、Schema、Resolver、Gate、Evidence | 相同快照产生相同 `projection_id` |
| 仓库 Artifact | 保存唯一治理状态 | `.harness/governance/rules.json` |

## 固定治理维度

- Audience：`maintainer`、`consumer`
- Subdomain：`agent-runtime`、`engineering-runtime`、`poc`、`source-code`、`test-code`、`other-tools`
- Responsibility：`generate`、`enforce`

例如 `uv run pytest` 是一个行为，不只是一个已安装工具：它同时受 `engineering-runtime` 和 `test-code` 约束，必须由仓库来源给出唯一调用绑定。

## 安全边界

- Harness 不发明技术栈、命令、权限或验证结论。
- Agent Request 不能携带任意 `command`，也不能覆盖 `argv`、`cwd`、Scope 或 Postconditions。
- 治理控制面写入先零写入预检，再按精确 Plan 单点发布。
- 常规行为在 Standing Policy + Work Grant 下自动过门禁；只有范围或外部权限跃迁才集中确认。
- 未分类、来源缺失、绑定歧义、投影过期、证据不全和执行漂移都会失败关闭。

## 文档

- [治理规范 SSOT](docs/specification.md)
- [快速上手](docs/quickstart.md)
- [仓库结构](docs/repository-structure.md)
- [可观察用户用例](uc.md)
- [实施状态](plan.md)

## 开发验证

本仓库的 Test / Build / CI 等语义必须通过 `.harness/tools.yaml` 中登记的 `task_ref` 路由；不要绕过 Harness 直接运行项目验证命令。
