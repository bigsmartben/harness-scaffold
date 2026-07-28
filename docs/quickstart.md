# Harness 快速上手

版本：`2.0.0`

## 1. 安装与初始化

```text
uv tool install <source-or-package>
cd <target-repository>
sdd-harness --version
sdd-harness init .
```

`init` 首先返回零写入计划（plan）和 `plan_digest`。交互外的自动化可用：

```text
sdd-harness init . --yes
```

1.0 仓库例外：第一次调用只报告迁移范围，且拒绝 `--yes`。确认摘要未变化后：

```text
sdd-harness init . --approve-plan sha256:<plan-digest>
```

初始化生成：

```text
AGENTS.md
.agents/skills/harness/
.harness/harness.yaml
.harness/governance/
```

默认不生成 Hook、Plugin 或固定 Agent TOML。需要项目 Hook 时显式执行：

```text
sdd-harness init . --with-hooks --yes
```

项目 Hook 仍需按 Codex 的信任模型启用；没有 Hook 不影响基础流程。

## 2. 在 Codex 中工作

Codex App / CLI 会发现仓库内 Skill。可以直接描述任务，也可以显式写：

```text
$harness 修改解析器并运行最低充分验证
```

Harness 先运行：

```text
sdd-harness inspect . --json
```

状态为 `active` 后，普通本地工作连续执行。验证层级示例：

| 变化 | 层级 | 实例 |
|---|---|---|
| 文档或惰性文本 | T0 | `docs/quickstart.md` |
| 窄实现或单测试 | T1 | `src/widget.py` |
| 公共 Schema 或多文件组件 | T2 | `schemas/public.schema.json` |
| 核心、迁移、依赖、CI/CD | T3 | `src/harness_core/projection.py` |

## 3. 项目策略与本次决定

| 用户意图 | 保存方式 |
|---|---|
| “以后本项目的 Issue 都发到 GitHub” | 项目策略（Project policy） |
| “这次只提交 `src/a.py`” | 本次决定（Task decision） |

本次决定绑定 `task_id + projection_id + workspace_digest + exact_action +
target`。例如 Commit 的决定不能授权 Remote Issue，文件变化后旧决定也不能复用。

## 4. Commit 与 Issue

选择性 Commit 先生成计划：

```text
sdd-harness commit-plan . --path src/a.py --message "fix: parser"
```

确认后由临时 Git Index 创建只含 `src/a.py` 的提交。无关暂存保持原样；目标文件
已部分暂存时返回 `PARTIAL_STAGING_UNSUPPORTED`。

Issue 先生成 Provider 无关的 Issue Plan：

```text
sdd-harness issue-plan . --title "Parser error" --body "Reproduce..."
```

Consumer 默认写 `.harness/issues`。配置为 GitHub 时，Harness 只准备精确的
Provider Request；远端失败不会创建本地副本。

## 5. 常见阻断

| 阻断码 | 人话解释 | 处理 |
|---|---|---|
| `HARNESS_RUNTIME_INCOMPATIBLE` | PATH 上的程序或仓库 Skill 版本不一致 | 重新安装并运行 `init` |
| `GOVERNANCE_PROJECTION_STALE` | 项目策略或治理输入已变化 | 重新生成投影 |
| `TASK_DECISION_STALE` | 本次决定绑定的工作区、动作或目标变了 | 重新确认精确动作 |
| `CONTROLLED_BRANCH_GATE_REQUIRED` | 当前分支不能直接写入或交付 | 切到私有工作分支或走平台门禁 |
| `GOVERNANCE_COVERAGE_INCOMPLETE` | 16 Cell 存在缺失、重复或无来源 N/A | 修复来源后重新编译 |
