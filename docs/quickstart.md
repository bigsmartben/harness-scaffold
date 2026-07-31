# Harness 4 快速开始

## 安装与首次 load

Harness 4 需要 Python 3.12：

```text
uv tool install "sdd-harness @ git+https://github.com/bigsmartben/harness-scaffold.git@v4.0.0"
harness --version
cd <consumer-repository>
harness load
```

版本输出为 `harness 4.0.0`。`harness` 与 `sdd-harness` 指向同一入口；前者是
仓库 Skill 尚不存在时的全局 bootstrap 表面。

load 会：

```text
仓库事实 + 已有治理来源
  → 四域候选
  → 冲突检查与校准
  → .harness/governance/state.json
  → .agents/skills/harness/SKILL.md
```

此后通过 `$harness` Skill 提交治理意图。bootstrap 与仓库 Skill 使用同一
Load Core、Operation 和权威状态，不形成双实现。

## 新旧仓库

新仓库即使没有仓库 Skill，也能直接运行 `harness load`。没有发现对应工程表面
时，四域 baseline 会明确记录“缺失”事实，而不是伪造已经存在的工具链。

3.0.1 consumer 的 `.harness/harness.yaml` 和 `model.lock.json` 会在无冲突导入
后移动到 `.harness/legacy/3.0.1/`；其他可识别旧版本按实际
`schema_version` 归档。新 `state.json` 是唯一当前规则 SSOT；归档
只用于来源追踪。

若旧规范重复、冲突或无法分类，load 返回稳定诊断并保持权威状态零写入。例如，
“Python 必须为 3.12”和“支持 Python 3.10+”不能被静默选边。

## 规则操作

| 用户意图 | 类型化操作 | 结果 |
|---|---|---|
| 新增规则 | `add` | revision=1、enabled |
| 更新规则 | `update` | 同一身份产生新 revision |
| 停用规则 | `disable` | 保留身份与历史，不再生效 |
| 恢复规则 | `enable` | 同一身份重新生效 |
| 删除规则 | `delete` | 移出当前集合，保留墓碑历史 |
| 取消 pending 操作 | `cancel` | 只改 Operation，规则零变化 |

Skill 形成类型化 OperationRequest 后，脚手架通过 `operate` 提交：

```text
harness operate --request-json '<OperationRequest JSON>'
harness cancel op-example
harness inspect
```

update、disable、enable 和 delete 必须绑定当前 `base_revision`。并发变化会返回
`BASE_REVISION_CONFLICT`，不会覆盖新状态。

## 职责边界

“新增规则，要求 API 改动后运行契约测试”的处理是：

1. Skill 提交 add 请求；
2. 脚手架保存并投影 verification 规则；
3. 外部测试 Worker 实际运行测试；
4. 脚手架核验 Worker 提交的类型化证据。

Skill 不运行第 3 步，脚手架也不把“已测试”的聊天文字当成第 4 步证据。

## 历史版本

维护历史 3.0.1 consumer 时参见
[3.0.1 发布说明](release-notes-3.0.1.md)。guidance-only 行为不属于 4.0.0
当前合同。
