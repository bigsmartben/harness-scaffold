# Harness 仓库结构

版本：`2.0.0`

## 开发仓库

```text
harness/
├── src/harness_core/
│   ├── resources/schemas/           2.0 JSON Schema
│   ├── resources/repo_skill/harness 唯一规范仓库 Skill
│   ├── compat/v1/                   只读迁移检测
│   └── *.py                         确定性内核和 CLI Adapter
├── plugins/harness/                 可选 Plugin；Skill 为生成副本
├── tests/                           单元、集成与分发契约
├── scripts/smoke_distribution.py    隔离 uv tool 验收
├── .harness/                        本仓库项目策略和 task_ref
└── pyproject.toml                   wheel 与 sdd-harness 入口
```

Python 包与 Skill 资源都进入 wheel。目标仓库中的 Skill 必须与
`resources/repo_skill/harness` 逐字节一致。

## 目标仓库

```text
target-repository/
├── AGENTS.md                         短路由与永久约束
├── .agents/skills/harness/
│   ├── SKILL.md
│   ├── agents/openai.yaml
│   └── references/
└── .harness/
    ├── harness.yaml                  项目策略
    ├── governance/
    │   ├── sources.lock.json
    │   ├── action-graph.json
    │   ├── rules.json
    │   ├── projection.lock.json
    │   └── compatibility.json
    ├── runtime/<task_id>/            本次决定；Git 忽略
    ├── issues/                        默认本地 Issue
    └── reports/                       验证 Evidence；Git 忽略
```

使用 `--with-hooks` 时才额外管理 `.codex/config.toml` 的 Hooks 开关和
`.codex/hooks.json`。Plugin / MCP 不写治理 SSOT。

## 权威与写入

| 路径 | 权威写者 | 约束 |
|---|---|---|
| `AGENTS.md` 中的 Harness marker | 初始化器 | 保留 marker 外用户内容 |
| `.agents/skills/harness` | 初始化器 | 只复制 wheel 内规范资源 |
| `.harness/harness.yaml` | 初始化器 / 用户确认的项目策略变更 | 变化产生新 `projection_id` |
| `.harness/governance` | 确定性编译器 | 模型不能生成权威 Projection |
| `.harness/runtime` | 精确动作 Adapter | 不版本化，不跨动作复用 |
| 业务源码 | Codex / 用户工具 | 仅在私有工作边界内直接写 |
