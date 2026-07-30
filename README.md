# SDD Harness

Harness 3.0 是一个本地规范治理脚手架（specification governance
scaffold）。它把仓库规则校验并投影为一个确定性的模型锁文件，供人和 Agent
读取。它不执行项目动作、不授予权限，也不连接远程 Provider（服务提供方）。

当前且唯一支持的契约版本是 `3.0.0`。

## 固定模型

模型由三条彼此正交的轴组成：

| 轴 | 中文含义 | 固定值 |
|---|---|---|
| Audience | 适用角色 | `maintainer`、`consumer` |
| Responsibility | 治理职责 | `generate`、`enforce` |
| Governance Domain | 治理域 | `specification`、`implementation`、`verification`、`delivery` |

三条轴的笛卡尔积固定产生 16 个 Cell（治理单元）。`2-2-4` 只是数量简称，
不是层级结构，也不是用户可配置项。

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
schema_version: 3.0.0
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

3.0.0 不读取、补全、迁移、映射、别名化或回退到 v1/v2。不存在双版本读取器、
弃用期或兼容包装器。已有外部 consumer（使用方）必须自行备份并清理旧 Harness
控制面，然后重新运行 `sdd-harness init`；Harness 不提供自动转换工具。

## 文档

- [规范说明](docs/specification.md)
- [快速开始](docs/quickstart.md)
- [仓库结构](docs/repository-structure.md)
- [行为验收追踪](docs/acceptance-traceability.md)
- [3.0.0 发布说明](docs/release-notes-3.0.0.md)

维护计划、状态、清单和验收结果只记录在
[GitHub Issue #32](https://github.com/bigsmartben/harness-scaffold/issues/32)
及其子 Issue。
