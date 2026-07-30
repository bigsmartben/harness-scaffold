# Harness 3.0 快速开始

版本：`3.0.1`

## 1. 安装并初始化

Harness 需要 Python 3.12。

```text
uv tool install <source-or-package>
sdd-harness --version
cd <target-repository>
sdd-harness init --json
```

版本输出必须是：

```text
sdd-harness 3.0.1
```

初始化成功后只有三个 Harness 文件：

```text
.agents/skills/harness/SKILL.md
.harness/harness.yaml
.harness/governance/model.lock.json
```

检查结果：

```text
sdd-harness validate --json
sdd-harness inspect --json
```

## 2. 添加一条规则

编辑 `.harness/harness.yaml`：

```yaml
schema_version: 3.0.1
rule_instances:
  specification:
    - rule_id: acceptance-before-code
      directive: 实现前应给出可观察的验收条件。
      scope:
        - docs/**
        - src/**
  implementation: []
  verification: []
  delivery: []
```

然后投影并验证：

```text
sdd-harness project --json
sdd-harness validate --json
sdd-harness inspect --json
```

`project` 会把规则规范化为 `kind: guidance`，按域、`rule_id` 和 scope
确定性排序，再原子替换单一模型锁。

## 3. 理解四个治理域

| Governance Domain（治理域） | 用来描述 | 规则示例 |
|---|---|---|
| `specification` | 需求与验收边界 | 实现前定义可观察结果 |
| `implementation` | 源码实现指导 | 公共边界使用明确类型 |
| `verification` | 验证指导 | 修改后运行最近的契约测试 |
| `delivery` | 交付物说明指导 | 发布说明列出破坏性变更 |

规则是指导文本，不会运行测试、执行 Git、授予权限、选择分支或调用远程服务。

## 4. 处理诊断

例如，以下规则包含禁止字段：

```yaml
- rule_id: deploy-now
  directive: 发布新版本。
  scope: ['src/**']
  provider: github
```

`project --json` 返回退出码 `2` 和类似诊断：

```json
{
  "code": "RULE_FIELD_FORBIDDEN",
  "path": "/rule_instances/delivery/0/provider",
  "rule_id": "deploy-now"
}
```

失败时既有模型锁保持逐字节不变。

## 5. 从旧版本重新开始

Harness 3.0 不读取或迁移 v1/v2。请先备份需要保留的 consumer 文件，再手动移除
旧 Harness 配置、Artifact、Plugin、Hook 或 MCP 文件，确认目标不再包含旧控制面，
然后重新运行：

```text
sdd-harness init --json
```

这不是迁移教程：3.0 没有自动转换、双版本读取或兼容期。
