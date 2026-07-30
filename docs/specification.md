# Harness 3.0 规范

规范版本：`3.0.0`

## 1. 产品边界

Harness 是本地规范治理脚手架。它接收一个封闭配置，验证固定模型与用户规则，
再生成一个可重复验证的模型锁文件。

```text
.harness/harness.yaml
        │ validate
        ▼
固定 2-2-4 模型 + guidance 规则
        │ project
        ▼
.harness/governance/model.lock.json
```

Harness 只表达规范与指导。它不是任务运行器、授权系统、交付系统或远程
Provider 客户端。

## 2. 规范术语

| 正式术语 | 中文 | 固定值 |
|---|---|---|
| Audience | 适用角色 | `maintainer \| consumer` |
| Responsibility | 治理职责 | `generate \| enforce` |
| Governance Domain | 治理域 | `specification \| implementation \| verification \| delivery` |
| Cell | 治理单元 | 三条轴的一个精确组合 |
| Rule Instance | 规则实例 | 用户在某个治理域下声明的一条指导 |

三条轴互相正交，固定产生 16 个 Cell。Cell ID 采用：

```text
<audience>.<responsibility>.<domain>
```

顺序固定为 Audience → Responsibility → Governance Domain，并按上表中每组值的
声明顺序枚举。`2-2-4` 只表示三组值的数量，不表示父子层级。

## 3. 唯一输入契约

最小合法配置必须显式包含四个空数组：

```yaml
schema_version: 3.0.0
rule_instances:
  specification: []
  implementation: []
  verification: []
  delivery: []
```

根对象、`rule_instances` 和每条规则都禁止额外字段。缺失任一治理域不是合法
输入，程序不会在内存中补默认值。

每条规则只允许：

| 字段 | 约束 | 示例 |
|---|---|---|
| `rule_id` | 全局唯一的小写 kebab-case，最多 64 字符 | `acceptance-before-code` |
| `directive` | 去除首尾空白后非空 | `先定义可观察验收条件。` |
| `scope` | 非空且无重复的仓库相对可移植 glob | `docs/**` |

`scope` 使用 `/`，禁止绝对路径、盘符、反斜杠、空路径段、`.`、`..` 及不受支持
的扩展 glob 语法。

以下字段没有配置语义并稳定拒绝：`audience`、`responsibility`、`kind`、
`blocking`、action、permission、branch、delivery、Provider、验证等级、
前后置条件、失败语义和 coverage 状态。

## 4. 单一模型锁

合法配置投影为：

```text
.harness/governance/model.lock.json
```

锁文件包含：

- 精确版本组件；
- 固定三轴及 16 个 Cell；
- 规范化、排序后的规则；
- `source_digest`（源摘要）；
- `projection_digest`（投影摘要）。

每条投影规则固定为：

```json
{
  "domain": "specification",
  "kind": "guidance",
  "rule_id": "acceptance-before-code",
  "directive": "实现前应给出可观察的验收条件。",
  "scope": ["docs/**", "src/**"],
  "source_ref": ".harness/harness.yaml#/rule_instances/specification/acceptance-before-code"
}
```

规则和 scope 的输入顺序不影响输出字节。增、删、改任一规则都会改变源摘要和
投影摘要。校验器从配置重算完整锁文件，因此篡改内容后重新计算自摘要也不能
隐藏漂移。

## 5. 命令语义

| 命令 | 成功条件 | 失败边界 |
|---|---|---|
| `init` | 目标目录存在，且没有冲突或旧输入 | 校验失败时写入为零 |
| `project` | 配置合法，临时文件可被原子替换 | 原锁文件保持逐字节不变 |
| `validate` | 配置、锁结构、固定模型和摘要全部一致 | 只返回诊断，不写文件 |
| `inspect` | 与 `validate` 相同 | 只返回版本、摘要、数量和诊断 |

诊断包含稳定错误码、JSON Pointer 路径、消息，以及适用时的 `rule_id`、
`expected` 和 `actual`。

## 6. 初始化结果

`init` 只管理：

```text
.harness/harness.yaml
.harness/governance/model.lock.json
.agents/skills/harness/SKILL.md
```

现有不同内容的 Skill、v1/v2 配置或旧治理 Artifact 会在任何写入前被拒绝。
Harness 不删除 consumer 文件，也不生成兼容产物。

## 7. 版本与无兼容边界

Core、Schema、模型锁、包元数据、CLI 和分发 Skill 的版本必须精确等于
`3.0.0`。

3.0.0 不实现迁移器、双读、字段映射、别名、默认补全、弃用期、兼容包装器或
回退。外部 consumer 需要自行备份并移除旧控制面，再以干净目标重新执行
`sdd-harness init`。
