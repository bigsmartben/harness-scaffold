# Harness 快速上手

版本：`1.0.0`

## 1. 安装与初始化

```text
uv tool install <source-or-package>
cd <target-repository>
sdd-harness init
```

`init` 先读取仓库事实并展示 Plan。使用 `--yes` 可在自动化场景接受这一份精确 Plan：

```text
sdd-harness init --yes
```

成功后会生成或更新：

```text
AGENTS.md
.codex/config.toml
.codex/agents/*.toml
.agents/skills/harness/
.harness/governance/
```

它不会覆盖 `AGENTS.md` 和 `.codex/config.toml` 的用户内容；只管理带 Harness marker 的区块。角色文件已存在但无法证明由 Harness 管理时，初始化零写入并返回冲突。

## 2. 正式入口

在 Codex App 或 Codex CLI 打开目标仓库，显式输入：

```text
$harness
```

主 Agent 会读取当前 `projection.lock.json`，按需使用六个自定义 Agent：

| Agent | 权限默认值 | 单一职责 |
|---|---|---|
| `repo_mapper` | read-only | 产生有来源事实 |
| `governance_projector` | read-only | 处理一个 Audience × Subdomain |
| `projection_reconciler` | read-only | 归并候选并保留冲突 |
| `governance_validator` | read-only | 调用 Schema / Validator |
| `governed_worker` | workspace-write | 在唯一 Scope 内执行已解析 Action |
| `evidence_verifier` | read-only | 验证结果、漂移和 Evidence |

## 3. 日常任务示例

用户说“修改解析器并跑受影响测试”后，主 Agent 建立一次 Work Grant：

```json
{
  "projection_id": "sha256:...",
  "action_id": "test:contracts",
  "audience": "maintainer",
  "scope": ["skills/initialize-ai-coding-harness", "tests"],
  "parameters": {}
}
```

Agent 没有提交 Shell 字符串。Resolver 从 Action Graph 取得唯一 `argv`、`cwd` 和 Postconditions；随后自动检查 G0–G7。投影和 Scope 未变化时，常规测试不会重复请求确认。

## 4. 何时确认

| 情况 | 行为 |
|---|---|
| 只读分析、已登记测试、Scope 内源码修改 | 自动 Gate，不确认 |
| 扩大多个写路径 | 聚合成一次变更集确认 |
| Push、PR、Release 等关联动作 | 聚合成一次交付确认包 |
| 删除、强推、生产迁移 | 独立确认或平台门禁 |

确认只授权权限跃迁；不能把未知行为变成已分类行为，也不能替代 Evidence。

## 5. 常见失败

| 阻断码 | 人话解释 | 下一步 |
|---|---|---|
| `GOVERNANCE_PROJECTION_STALE` | 仓库事实变了 | 重新运行 `$harness` 更新投影 |
| `TOOL_ACTION_UNCLASSIFIED` | 找到工具但不知道具体行为 | 在仓库中声明 Action 来源 |
| `TOOL_BINDING_AMBIGUOUS` | 一个行为解析出多个入口 | 消除冲突绑定 |
| `AGENT_CONFIGURATION_UNTRUSTED` | 角色文件存在但不受 Harness 管理 | 人工核对并移交 |
| `GOVERNANCE_EVIDENCE_INCOMPLETE` | 执行结果不足以支撑结论 | 补齐后置条件或平台证据 |

缺口会一次性返回完整阻断包，不会变成连续追问。

## 6. 重复初始化

相同仓库快照、Schema、编译器版本和维护者声明会产生相同 `projection_id`。相同版本重复执行 `sdd-harness init --yes` 应产生空 Diff；如果治理输入改变，旧投影立即失效。
