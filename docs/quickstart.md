# SDD Harness 使用者快速上手

版本：`1.0.0`

这份指南面向 consumer（使用者）：你想把 Harness 安装到自己的仓库，并在 Codex App 或 Codex CLI 中用 `$harness` 执行受治理的开发任务。维护 Harness 本身请阅读[维护者手册](../README.md)。

Harness 主要替你防止五类问题：

| 常见问题 | Harness 的处理 |
|---|---|
| Agent 猜错项目命令 | 只调用仓库有来源的 Action Binding（行为绑定） |
| Agent 改了无关文件 | 用 Work Grant（工作授权）和 Scope（范围）限制写入 |
| “测试通过”没有证据 | 检查报告、Postcondition（后置条件）和 Evidence（证据） |
| 仓库变化后继续用旧计划 | 让旧 `projection_id` 和 Work Grant 失效 |
| 修代码时顺手 Push 或发布 | 把交付作为需要精确确认的独立权限跃迁 |

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

## 2. 初始化目标仓库

进入要接入 Harness 的目标仓库：

```text
cd <target-repository>
sdd-harness init .
```

命令会先生成并校验精确 Plan（计划），预检通过后直接写入目标仓库。

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

更推荐使用下面的模板：

```text
$harness

目标：
范围：
不要做：
完成标准：
交付边界：
```

例如：

```text
$harness

目标：订单创建接口增加可选的 delivery_note 字段。
范围：接口规范、订单请求模型和相关测试。
不要做：不改数据库，不升级依赖，不重构其他订单代码。
完成标准：兼容旧请求；长度最多 200；增加有效值和超长值测试。
交付边界：只完成本地修改和验证，不 Push，不创建 PR。
```

你不需要提供测试命令，也不需要指定内部 Agent。Harness 应从仓库事实中解析入口；如果入口缺失或存在歧义，它会阻断并告诉你需要补什么，而不是猜一个命令继续执行。

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

### 3.1 目标本地体验

以下是 Harness SDD 四域治理模型的目标体验，尚未全部进入当前运行契约：

- 在本地目录和 Private Branch 中连续推进，不逐文件、逐命令询问；
- 小改动只做最低充分验证，不自动运行完整测试；
- 内部保留 Gate 和 Evidence，用户默认只看人话摘要；
- `git commit` 是本地开发中唯一默认可见的检查点；
- Push、PR、Merge、Release 和 Deploy 仍是独立外部动作。

最低验证示例：

| 变化 | 默认验证 |
|---|---|
| 只改 Markdown | T0：检查内容和链接，不运行项目测试 |
| 修一个小函数 | T1：最近的单元测试 |
| 改公共接口或 Schema | T2：受影响组件或契约测试 |
| 改依赖锁、迁移、安全或 CI/CD | T3：完整测试或 CI |

完成时，用户默认看到：

```text
完成：修改 3 个文件
验证：T1，运行 6 个相关测试，全部通过
未运行：完整测试；本次未影响共享接口
剩余风险：无已知风险
```

原始 `projection_id`、Action ID、Gate 明细和 Evidence Digest 默认隐藏，需要时可以要求“展开技术证据”。

### 3.2 `git commit` 工作流

当你明确输入：

```text
git commit
```

Harness 会询问：

```text
是否对当前工作区全部未提交变更执行影响面分析？
默认 Issue 目标：local
如需远端 Issue，请同时提供或确认远端信息。
```

选择“不分析”时，只做必要的 Commit Scope、Secret、冲突和异常文件检查，不额外运行大范围测试。

选择“分析”时，Harness 会检查当前 `HEAD` 之后的全部 Staged、Unstaged 和 Untracked 变化。分析以工作区为准，因此可以跨对话。随后生成：

```text
标题：
目标：
当前变更：
影响模块：
兼容性风险：
Commit 包含：
Commit 排除：
最低验证范围：
完成标准：
```

你确认后，Harness 写入 Issue、执行计划和最低充分验证，然后完成原始 Commit。没有新的重大 Scope 变化时，不再要求第三次确认。

### 3.3 本地或远端 Issue

对普通消费者项目，Issue 目标由项目级 Harness 配置决定；没有远端配置时默认是本地：

```yaml
issue_planning:
  default_destination: local
  local_directory: .harness/issues
  remote:
    provider: null
    project: null
```

本地 Issue 用于跨对话保存计划，不会改变远端状态。

这是消费者项目的低门槛默认值，不适用于 Harness 产品自身的维护者迭代。Harness 维护统一使用本仓库 GitHub Issues；本地文档只保存链接，不复制 Issue 正文。

如需创建远端 Issue，你需要确认或提供：

- Provider，例如 GitHub、GitLab 或 Jira；
- Repository、Project 或 Project Key；
- 将要创建的标题和正文；
- 可选的 Label 和 Assignee。

不要在远端信息中粘贴 Token、密码或私钥。即使项目已经连接远端服务，Harness 也不能把“连接存在”当成创建 Issue 的授权。

远端 Issue 创建后，返回的 Issue ID/URL 会写回本地工作状态。`git commit` 不授权 Push、PR、Merge、Release 或 Deploy。

## 4. 如何判断任务完成

退出码为零不等于任务完成。只有 Schema、后置条件、摘要链和执行后漂移检查都通过，Evidence 才能支撑“测试通过”“构建成功”或“允许交付”等结论。

| 你看到的结果 | 含义 |
|---|---|
| `completed` 或 `passed` | 内部证据已接受；默认只展示人话摘要 |
| `confirmation-required` | 即将扩大范围或执行关键外部动作 |
| `blocked` + blocker codes | 输入、绑定、平台或证据不完整，未执行危险回退 |

默认用户界面不需要展示原始 Evidence。正常成功时只显示修改摘要、验证强度、未运行检查和剩余风险；出现阻断或用户主动要求时再展开技术细节。

## 5. 重复初始化与更新

相同仓库快照、Schema、编译器版本和维护者声明会产生相同 `projection_id`。再次执行：

```text
sdd-harness init .
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
