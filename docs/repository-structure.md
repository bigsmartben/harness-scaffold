# Harness 3.0 仓库结构

版本：`3.0.1`

## 开发仓库

```text
harness/
├── src/harness_core/
│   ├── model.py                     固定三轴、16 Cell 与版本
│   ├── contracts.py                 配置和锁文件校验
│   ├── projection.py                确定性编译与原子替换
│   ├── initializer.py               最小零迁移初始化
│   ├── cli.py                       四命令本地 CLI
│   └── resources/
│       ├── schemas/                 v3 输入与锁 Schema
│       └── repo_skill/harness/      分发 Skill 唯一副本
├── tests/
│   ├── unit/                        契约、投影、篡改与原子写
│   ├── integration/                 CLI 与初始化
│   └── bdd/                         M-G / C-G 行为场景
├── scripts/smoke_distribution.py    wheel/sdist 干净环境验收
├── evals/manifest.yaml              场景到测试和 CI 的静态映射
├── .harness/
│   ├── harness.yaml                 本仓库的 v3 规则输入
│   └── governance/model.lock.json   本仓库的单一模型锁
└── pyproject.toml                   3.0.1 包与 CLI 入口
```

Python 包只包含八个模块：`__init__`、`artifacts`、`cli`、`contracts`、
`initializer`、`model`、`package_resources` 和 `projection`。

## 生成仓库

```text
target-repository/
├── .agents/
│   └── skills/
│       └── harness/
│           └── SKILL.md
└── .harness/
    ├── harness.yaml
    └── governance/
        └── model.lock.json
```

| 路径 | 内容 | 写者 |
|---|---|---|
| `.harness/harness.yaml` | 四域规则输入 | `init` 首次创建，之后由用户编辑 |
| `.harness/governance/model.lock.json` | 固定模型、规则及摘要 | `init` / `project` 原子写入 |
| `.agents/skills/harness/SKILL.md` | v3 使用边界 | `init` 从 wheel 资源复制 |

`validate` 和 `inspect` 不写任何文件。目标仓库不会生成 Plugin、Hook、MCP、
运行时决定、Action Graph 或多 Artifact 投影。

## 权威关系

```text
model.py ──────────────┐
harness.yaml ─────────┼─> projection.py ─> model.lock.json
schemas ───────────────┘

resources/repo_skill/harness/SKILL.md ─> init ─> target Skill
```

固定三轴和 16 个 Cell 只有 `model.py` 一个规范来源。用户规则只有
`.harness/harness.yaml` 一个输入来源。生成 Skill 必须与 wheel 内发布副本
逐字节一致。

## 不属于 3.0 的结构

3.0 不包含旧式 adapters、pipelines、tasks、tools、Plugin、Hook、MCP、运行器、
本地 Issue 镜像或五份治理 Artifact。外部 consumer 如果仍有这些路径，需要自行
备份并清理后重新初始化；Harness 不自动删除或迁移它们。
