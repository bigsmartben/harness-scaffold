# SDD Harness 维护者手册

目标规范：Harness SDD 四域治理模型
当前运行时：`1.0.0`（迁移实施由 [Epic #22](https://github.com/bigsmartben/harness-scaffold/issues/22) 跟踪）

本仓库维护 SDD Harness：一个运行在 Codex App / Codex CLI 中、绑定仓库事实的 Agent 治理框架。它把仓库里的 Manifest、Workflow、测试入口和既有治理声明编译成可追溯规则，再用 Gate（门禁）和 Evidence（证据）约束执行。

如果你只想在自己的仓库中使用 Harness，请直接阅读[使用者快速上手](docs/quickstart.md)。

## 产品边界

| Harness 负责 | Harness 不负责 |
|---|---|
| 从固定仓库快照生成治理投影 | 发明项目技术栈、命令或权限 |
| 将行为解析到唯一 Action 和 Task | 接受 Agent 提交的任意 Shell 字符串 |
| 以 G0–G7 检查范围、绑定和执行结果 | 用自然语言总结代替验证证据 |
| 对关键外部动作要求确认和平台门禁 | 绕过分支保护直接 Push、Merge 或 Release |

`docs/specification.md` 是唯一规范来源（SSOT, Single Source of Truth）。代码、测试、Plugin 和其他文档只能实现或解释该规范，不能建立平行政策。

本仓库的维护者迭代统一使用 [GitHub Issues](https://github.com/bigsmartben/harness-scaffold/issues) 管理。GitHub Issue 是计划、状态、清单和验收结论的唯一权威来源；仓库内不保存可编辑的 Issue 正文副本。

## 工作方式

```text
Repository Snapshot（仓库快照）
  → source-backed facts（有来源事实）
  → Action Graph（行为图）
  → Governance Projection（治理投影）
  → Work Grant（工作授权）
  → G0–G7
  → accepted Evidence / stable blocker codes
```

| 层 | 维护内容 | 实例 |
|---|---|---|
| 编排层 | 理解目标、划定 Scope、选择角色 | `repo_mapper` 只读提取事实 |
| 确定性 Core | Schema、Resolver、Gate、摘要链 | 相同输入产生相同 `projection_id` |
| 仓库控制面 | Action Binding、Task、边界与 Evidence | `.harness/tools.yaml` 将行为绑定到 `task_ref` |

固定治理维度为两类 Audience（适用角色）× 两类 Responsibility（治理职责）× 四个 Governance Domain（治理域），共 16 个最小治理单元：

- Audience：`maintainer`、`consumer`
- Responsibility（职责）：`generate`、`enforce`
- Governance Domain：`specification`、`implementation`、`verification`、`delivery`

例如，用户要求“修改登录错误提示”时，Harness 分别确认需求与验收标准（Specification）、修改实现（Implementation）、执行最近的相关测试（Verification）；只有用户明确要求 Push、PR 或发布时才进入 Delivery。

Agent、Runtime、Action Binding、Tool、Project Profile 和 Evidence 是横向控制，不再作为顶层分类。PoC 是 Implementation 的开发模式，不是独立治理域；`other-tools` 剩余桶被删除，任何工具都必须绑定明确 Action。

## 仓库结构与所有权

```text
harness-scaffold/
├── docs/                         规范与使用文档
├── plugins/harness/              可选 Codex Plugin
├── skills/initialize-ai-coding-harness/
│   ├── assets/schemas/           JSON Schema
│   └── scripts/harness_core/     确定性 Core
├── scripts/                      分发验证脚本
├── tests/                        单元、集成与契约测试
├── .harness/                     本仓库 Action、Task、边界与 Pipeline
├── .github/workflows/            平台验证与交付门禁
├── pyproject.toml                Python 分发和 CLI 入口
└── uv.lock                       可复现依赖锁
```

更完整的路径说明见[仓库结构](docs/repository-structure.md)。主要所有权如下：

| 路径 | 权威来源 |
|---|---|
| `docs/specification.md` | Harness 规范 SSOT |
| `skills/initialize-ai-coding-harness/assets/schemas/` | 机器契约 |
| `.harness/*.yaml` | 本仓库 Action 与 Task 绑定 |
| `.harness/governance/` | 从当前事实生成的治理状态 |
| `.harness/reports/` | Task Evidence，不提交版本库 |

## 维护流程

依赖由 `pyproject.toml` 和 `uv.lock` 定义。首次准备本地环境时使用：

```text
uv sync --locked
```

之后在 Codex App 或 Codex CLI 中显式调用 `$harness`，并用 Task ID 描述需要的验证；不要直接绕过 Harness 运行 Test、Build、CI 或交付命令。

| Task ID | 自动化等级 | 用途 |
|---|---|---|
| `test:contracts` | routine | 验证 Schema、Core、文档和仓库契约 |
| `test:distribution-smoke` | routine | 构建 wheel，隔离安装并验证重复初始化 |
| `test:contracts-ci` | routine | 产生 PR Required Check |
| `ci:full` | expensive | 经当前确认运行完整 CI |
| `package:wheel` | routine | 从精确 commit 生成已验证的 Release artifact |
| `push:branch` | critical | Push 精确 commit，禁止强推 |
| `pull-request:create` | critical | 从精确 source ref 创建 PR |
| `merge:pull-request` | critical | Required Checks 通过后合并精确 PR head |
| `release:github` | critical | 发布绑定版本、commit、artifact 摘要和环境审批的 GitHub Release |

`main`、`release/**` 和 `hotfix/**` 是 controlled branch（受控分支）；`codex/**` 和 `agent/**` 是 private branch（私有工作分支）。受控分支上的 Push、PR、Merge 和 Release 必须绑定精确目标、commit、当前确认与平台 Evidence，缺一项即失败关闭。

## v1.0.0 发布流程

发布只走 `.harness/pipelines/publish.yaml`：

```text
test:contracts
  → test:distribution-smoke
  → package:wheel
  → release:github
```

1. 在私有分支完成变更，通过 routine Task 和经确认的 `ci:full`。
2. 以精确 SHA Push 并创建 PR；Required Checks 通过后独立确认 Merge。
3. 在合并后的 `main` 上运行 `package:wheel`。GitHub Actions 会构建、隔离安装并上传 wheel、`SHA256SUMS` 和机器报告。
4. 用 package run ID、wheel SHA-256、`version=1.0.0`、`target=refs/tags/v1.0.0`、`environment=production` 和 `main` commit 创建 Release 请求。
5. `release:github` 在受保护的 `production` Environment 获批后创建或核对 GitHub Release。已有 Tag、commit 或资产摘要冲突时禁止覆盖。

本项目不向 PyPI 发布：[PyPI 上的 `sdd-harness`](https://pypi.org/project/sdd-harness/) 属于另一个无关项目。正式安装源是本仓库的 GitHub Release。

## 规范与状态

- [治理规范 SSOT](docs/specification.md)
- [四域模型术语与规则](docs/harness-sdd-governance-terminology.md)
- [使用者快速上手](docs/quickstart.md)
- [仓库结构](docs/repository-structure.md)
- [重构 Epic #22](https://github.com/bigsmartben/harness-scaffold/issues/22)
