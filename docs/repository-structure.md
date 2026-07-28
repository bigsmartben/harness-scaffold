# Harness 仓库结构

目标规范：Harness SDD 四域治理模型
当前运行时：`1.0.0`

## 开发仓库

```text
harness/
├── docs/                         规范说明与使用文档
├── plugins/harness/              Codex Plugin（可选纵深防御）
├── skills/initialize-ai-coding-harness/
│   ├── assets/schemas/           JSON Schema
│   └── scripts/harness_core/     确定性契约内核
├── tests/                        单元与集成契约
├── .harness/                     本仓库自己的 Action 绑定与 Evidence
├── pyproject.toml                sdd-harness 分发和入口
└── uv.lock                       可复现依赖锁
```

`docs/specification.md` 是唯一规范 SSOT；代码、测试、Plugin 和其他文档都是该规范的投影或验证。

## 目标仓库

`sdd-harness init` 发布以下控制面：

```text
target-repository/
├── AGENTS.md
├── .codex/
│   ├── config.toml
│   └── agents/
│       ├── repo-mapper.toml
│       ├── governance-projector.toml
│       ├── projection-reconciler.toml
│       ├── governance-validator.toml
│       ├── governed-worker.toml
│       └── evidence-verifier.toml
├── .agents/skills/harness/
│   ├── SKILL.md
│   ├── agents/openai.yaml
│   ├── scripts/
│   ├── schemas/
│   └── references/
└── .harness/
    ├── governance/
    │   ├── sources.lock.json
    │   ├── action-graph.json
    │   ├── rules.json
    │   └── projection.lock.json
    ├── reports/
    └── evidence/
```

## Ownership（写入所有权）

| 路径 | 权威写者 | 规则 |
|---|---|---|
| Harness 管理的 `AGENTS.md` 区块 | 初始化器 / 主 Agent | Plan-bound 单写者 |
| `.codex/agents/*.toml` | 初始化器 / 主 Agent | 受管标记；冲突零写入 |
| `.agents/skills/harness/` | 初始化器 / 主 Agent | 整体版本化发布 |
| `.harness/governance/` | 投影发布器 | 验证通过后原子写入 |
| 业务源码与测试 | `governed_worker` | Work Grant Scope 内单写或互斥 ownership |
| Evidence | Runner / Verifier | 追加并绑定摘要链 |

`.harness/tools.yaml`、`tasks.yaml`、`boundaries.yaml`、`impact.yaml`、`pipelines.yaml` 和 Adapter 不再形成平行政策；它们是 Action Graph 和 Rule 的 source-backed 绑定输入。
