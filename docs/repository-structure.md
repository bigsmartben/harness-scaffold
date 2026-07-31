# Harness 4 仓库结构

## 维护仓库

```text
harness/
├── src/harness_core/
│   ├── model.py                     固定三轴、Responsibility 与 16 Cell
│   ├── lifecycle.py                 规则生命周期与类型化 Operation
│   ├── load_core.py                 只读仓库事实发现与校准
│   ├── skill_adapter.py             自然语言治理意图适配
│   ├── scaffold.py                  权威状态、投影与执行保障
│   ├── bootstrap.py                 consumer load 与 3.0.1 归档
│   ├── cli.py                       load/operate/cancel/inspect
│   └── resources/
│       ├── schemas/                 Rule、Operation、Load、Evidence Schema
│       └── repo_skill/harness/      分发 Skill 唯一副本
├── tests/                            unit / integration / E2E
├── scripts/smoke_distribution.py    wheel/sdist 隔离安装验收
└── pyproject.toml                   4.0.0 包与双入口
```

维护仓库根目录不是 consumer，不能生成 `.harness/governance/state.json` 或
`.agents/skills/harness/SKILL.md`。维护者闭环由根 `AGENTS.md`、规范源码和测试
承担。

## Consumer 仓库

```text
target-repository/
├── .agents/skills/harness/SKILL.md
└── .harness/
    ├── governance/state.json
    └── legacy/<source-version>/     仅升级来源存在时生成
```

| 路径 | 权威性 | 写者 |
|---|---|---|
| `state.json` | 当前规则、Operation 与历史的唯一 SSOT | `load` / `operate` / `cancel` |
| `SKILL.md` | 用户治理意图接口 | `load` 从 wheel 资源安装 |
| `legacy/<source-version>/` | 只读来源归档，不生效；例如 `3.0.1/` | 成功升级时移动 |

规则投影和 enforcement decision 从 `state.json` 确定性重算，不是可编辑 SSOT。

## 依赖方向

```text
Skill Adapter ──> Operation / Load Request
                         │
Load bootstrap ──> Load Core ──> Scaffold ──> authoritative state
                                      ├─> deterministic projection
                                      └─> enforcement obligation / decision
```

Skill Adapter 不复制发现算法，bootstrap 不复制意图解析，分发层不复制状态机或
enforce 内核。
