# SDD Harness 使用者快速上手

版本：`1.0.0`

这份指南面向 consumer（使用者）：你想把 Harness 安装到自己的仓库，并在 Codex App 或 Codex CLI 中用 `$harness` 执行受治理的开发任务。维护 Harness 本身请阅读[维护者手册](../README.md)。

## 1. 安装固定版本

先安装 [uv](https://docs.astral.sh/uv/getting-started/installation/)，再从 GitHub Release 安装经过验证的 wheel：

```text
uv tool install https://github.com/bigsmartben/harness-scaffold/releases/download/v1.0.0/sdd_harness-1.0.0-py3-none-any.whl
sdd-harness --version
```

预期输出：

```text
sdd-harness 1.0.0
```

如果当前环境不能直接下载 Release asset，可以固定到同一个 Git tag：

```text
uv tool install git+https://github.com/bigsmartben/harness-scaffold.git@v1.0.0
```

不要执行 `uv tool install sdd-harness`：PyPI 上的同名包不是本项目。

## 2. 预览初始化

进入要接入 Harness 的目标仓库：

```text
cd <target-repository>
sdd-harness init
```

第一次运行只生成 Plan（计划）并显示精确写入范围，不会直接修改仓库。确认 Plan 符合预期后执行：

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

初始化器只管理带 Harness marker 的区块，不覆盖 `AGENTS.md` 或 `.codex/config.toml` 中的用户内容。已有角色文件无法证明受 Harness 管理时，它会零写入并返回冲突。

## 3. 在 Codex 中使用

用 Codex App 或 Codex CLI 打开目标仓库，显式输入：

```text
$harness
```

随后直接描述结果，不需要手写命令。例如：

```text
修改解析器以支持新的配置字段，并运行受影响测试。
```

Harness 会完成以下闭环：

```text
仓库快照
  → 解析 Action（行为）和 Scope（范围）
  → 创建 Work Grant（工作授权）
  → 检查 G0–G7 Gate（门禁）
  → 执行已登记 Task
  → 验证 Postconditions（后置条件）
  → 生成 Evidence（证据）
```

常规只读分析、已登记测试和 Work Grant 范围内修改不会逐命令确认；扩大写路径或执行 Push、PR、Merge、Release 等权限跃迁时，Harness 会提交绑定精确事实的一次确认包。

## 4. 如何判断任务完成

退出码为零不等于任务完成。只有 Schema、后置条件、摘要链和执行后漂移检查都通过，Evidence 才能支撑“测试通过”“构建成功”或“允许交付”等结论。

| 你看到的结果 | 含义 |
|---|---|
| `passed` + Evidence | 结论有机器证据支撑 |
| `confirmation-required` | 即将扩大范围或执行关键外部动作 |
| `blocked` + blocker codes | 输入、绑定、平台或证据不完整，未执行危险回退 |

## 5. 重复初始化与更新

相同仓库快照、Schema、编译器版本和维护者声明会产生相同 `projection_id`。再次执行：

```text
sdd-harness init --yes
```

应该得到空 Diff。仓库 Manifest、Workflow 或治理声明发生变化后，重新运行初始化以更新投影；旧 Work Grant 会立即失效，不能继续授权执行。

## 6. 常见阻断

| 阻断码 | 人话解释 | 下一步 |
|---|---|---|
| `GOVERNANCE_PROJECTION_STALE` | 仓库事实变了，当前投影已过期 | 重新运行 `$harness` 或初始化 |
| `TOOL_ACTION_UNCLASSIFIED` | 找到了工具，但仓库没有声明它用于什么行为 | 补充有来源的 Action 定义 |
| `TOOL_BINDING_AMBIGUOUS` | 同一行为解析出了多个入口 | 消除冲突绑定 |
| `AGENT_CONFIGURATION_UNTRUSTED` | 自定义角色文件存在，但无法证明由 Harness 管理 | 人工核对并移交所有权 |
| `GOVERNANCE_EVIDENCE_INCOMPLETE` | 执行结果不足以支撑结论 | 补齐后置条件或平台 Evidence |
| `CONTROLLED_BRANCH_GATE_REQUIRED` | 目标是受控分支，但确认或平台门禁不完整 | 使用私有工作分支和受保护 PR 流程 |
| `HANDOFF_REQUIRED` | 需要人的决定或外部平台操作 | 按阻断包给出的精确目标继续 |

阻断会一次返回完整问题包；Harness 不会猜测缺失命令、权限或验证结论。
