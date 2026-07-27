# AI Coding Harness Quickstart

版本：`0.3.0`
文档与初始化状态：P0–P2 Available
产品流程状态：P3–P4 Available（P4 本地产品验收）；P5 In Progress
最后更新：2026-07-24

本文按最终产品体验串联四条用户路径：

1. 接管已有 GitHub Actions 的 Node 项目。
2. 为无 CI/CD 的 Python 项目建立 Harness。
3. 完成一次局部修改、最低充分验证和 Merge。
4. 完成一次需要独立用户确认的 Publish。

文中的 Skill 输入、配置和 Evidence 都是已确定的目标接口。能力尚未达到对应阶段时，不应把示例理解为当前可执行命令。

## 目录

- [0. 能力状态与共同约定](#0-能力状态与共同约定)
- [1. 接管已有 GitHub Actions 的 Node 项目](#1-接管已有-github-actions-的-node-项目)
- [2. 为无 CI/CD 的 Python 项目建立 Harness](#2-为无-cicd-的-python-项目建立-harness)
- [3. 局部修改、受影响验证与 Merge](#3-局部修改受影响验证与-merge)
- [4. 用户确认后 Publish](#4-用户确认后-publish)
- [5. 结果检查清单](#5-结果检查清单)

## 0. 能力状态与共同约定

### 0.1 状态

| 本文能力 | 状态 | 实施阶段 |
|---|---|---|
| 目标接口的文档示例 | Available | P0 |
| YAML Schema 和目标模板 | Available | P1 |
| Adopt、Bootstrap、Audit、Update Skill 流程 | Available | P2 |
| Work、Verify、Merge、Publish 路由；三级自动化策略 | Available | P3 |
| CI/CD 平台闭环 | Available | P4 |
| 安装与正式发布 | In Progress | P5 |

阶段进度以 [`plan.md`](../plan.md) 为准。

P4 已通过本地 Fixture、Fake Adapter、零调用断言和独立目录产品验收。真实 GitHub Run、Required Checks、Protected Environment 与审批 Evidence 仍在具体正式交付时逐次校验。Push 可使用窄化的 Git Remote Backend：例如本次确认只绑定 `origin`、`refs/heads/codex/demo` 和一个精确 commit，并且禁止 force；该 Evidence 不能替代 Merge、Publish、Release 或 Deploy 的平台门禁。P5 已确认私有发布和当前用户安装目标，尚未 Push、Release 或安装。

### 0.3 用户入口

最终用户通过 `initialize-ai-coding-harness` Skill 触发流程，不需要记忆独立 CLI。

Harness 必须先完成只读发现和计划，再执行写入：

```text
用户请求
  → 只读发现
  → Adopt / Bootstrap / Update Plan
  → 用户确认写入范围
  → 确定性 Python 应用
  → Schema 与跨文件校验
  → Evidence
```

### 0.3 治理边界与三级 CI/CD 自动化

| 范围 / 能力 | 使用方式 | 示例 |
|---|---|---|
| `AGENTS.md` 治理区块 | Harness 只替换成对标记内入口，保留标记外项目规范 | Adopt / Update |
| 本地工作区 | 按 Work Grant 声明并检查写入范围 | 局部实现与验证 |
| 私有分支 | 当前确认后执行精确、非强推操作 | `refs/heads/codex/demo` |
| 受控或未分类分支 | 禁止直接 Backend；强确认后交给平台门禁 | `main`、`release/*` |
| 普通能力 | 查询 Registry 后直接调用，不逐次审批 | `rg`、Python、Shell、普通 MCP Tool |
| `routine` | 只有项目明确允许时自动执行 | 快速 Unit Test |
| `expensive` | 每次生成 Request 并等待确认 | Integration、E2E、Full CI、大型 Build |
| `critical` | 每次确认，并同时满足 CI/CD 平台门禁 | Push、Merge、Publish、Release、Deploy |

分类依据是动作语义，不是 Shell、CLI、MCP 或 API 等调用通道。普通能力不需要 Harness 逐次授权；产生的文件写入仍受当前 Work Grant 的声明与检查约束。

## 1. 接管已有 GitHub Actions 的 Node 项目

**状态**：P2 Adopt Available；P3 GitHub Actions 调用管理 Available  
**对应用户用例**：[`UC-001`](../uc.md)  
**核心规则**：`TR-001` 至 `TR-003`、`DM-006`、`HF-001`、`EV-002`

### 1.1 示例项目

```text
shop-api/
├── package.json
├── package-lock.json
├── src/
├── test/
└── .github/
    └── workflows/
        └── ci.yml
```

`package.json` 已包含 `lint`、`test` 和 `build`，`ci.yml` 已经调用这些脚本，并通过 `workflow_dispatch` 提供给 Harness 在 Handoff 后调度；它没有直接的 `push`、`pull_request` 或 `schedule` 触发器。GitHub 将 `workflow_dispatch` 定义为可手动或经 API 触发的事件，Harness 使用的是受控 API 入口，参见 [触发 Workflow 的事件](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_dispatch) 与 [Create a workflow dispatch event](https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event)。

### 1.2 触发 Adopt

用户输入：

```text
请使用 initialize-ai-coding-harness 接管当前 Node 项目已有的工具和 GitHub Actions。
先只读发现，保留现有 Workflow；给出 Adopt Plan，得到我确认后再写入。
```

Harness 的第一步只能读取，不能修改 `package.json` 或 `ci.yml`。

### 1.3 查看只读发现

目标发现摘要：

```yaml
repository_root: C:/work/shop-api
project_types:
  - node
fact_sources:
  node: package.json
project_units:
  - id: node-root
    type: node
    root: .
    manifest: package.json
    commands:
      - name: test
        category: test
        source: package.json#scripts.test
workflows:
  - path: .github/workflows/ci.yml
    triggers: [workflow_dispatch]
    controlled_entry: true
    protected_trigger_uncontrolled: false
    jobs:
      - id: test
        category: test
        source: .github/workflows/ci.yml#jobs.test
referenced_scripts: []
gaps: []
```

如果版本来源冲突、脚本不存在或 Workflow 无法解析，Harness 必须在此阶段报告缺口，不得选择一个“看起来正确”的值。

### 1.4 查看 Adopt Plan

保存的 Plan 是 `artifact_type: plan`、`schema_version: 0.3.0` 的机器对象。用户界面至少展示：

| 字段 | 本例内容 |
|---|---|
| `plan_type` | `adopt` |
| `repository_root` | `C:/work/shop-api` |
| `source_facts_digest` / `source_state` | 发现摘要，以及 `package.json`、Workflow 等事实源的修改前 SHA-256 |
| `write_scope` | `AGENTS.md` 与每个将创建的 `.harness/...` 精确文件路径 |
| `actions` | 每个目标的 `action`、`path`、`template`、`merge`、`before_digest`、`after_digest` |
| `preserve` | `package.json`、`package-lock.json`、`.github/workflows/ci.yml` |
| `blocker_codes` / `drift` | 当前阻塞码与字段级决策 |
| `plan_digest` | 排除自身字段后计算的规范 JSON SHA-256 |

Plan 不包含可手改的 `approved` 布尔值。`write_scope` 必须与 `actions[].path` 精确相等；`preserve` 防止“接管”被解释成“重写”。本例的只读发现确认 `AGENTS.md` 不存在，因此对应 Action 是 `create`。

如果项目已有 `AGENTS.md`，计划必须改为：

```yaml
create:
  - .harness/harness.yaml
  # ...其余 .harness/ 文件

update:
  - path: AGENTS.md
    strategy: merge-lightweight-harness-entry
    diff: |
      # 展示将新增的最小入口；已有项目指令保持原样
```

用户必须能在确认前看到这个 Diff。无法安全合并时，Adopt 保持 `blocked`；Harness 不能用模板覆盖已有项目指令。

### 1.5 用户确认

用户输入：

```text
确认当前 Adopt Plan（plan_digest 如下）。
只允许执行 Plan 中列出的精确路径；不要修改 package.json、package-lock.json 或现有 Workflow。
```

这次确认形成独立 Plan Approval，而不是 Work Grant：

```yaml
artifact_type: plan-approval
schema_version: 0.3.0
plan_digest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
confirmation_status: confirmed
confirmed_at: 2026-07-24T09:00:00+08:00
```

Apply 必须同时读取未变化的 Plan 与 Approval。若发现必须改写 `.github/workflows/ci.yml`，必须重新生成 Plan 并再次确认。

### 1.6 预期结果

```text
shop-api/
├── AGENTS.md
├── package.json
├── package-lock.json
├── .github/workflows/ci.yml
└── .harness/
    ├── harness.yaml
    ├── boundaries.yaml
    ├── tools.yaml
    ├── tasks.yaml
    ├── impact.yaml
    ├── pipelines/
    │   ├── merge.yaml
    │   └── publish.yaml
    ├── adapters/
    │   └── github-actions.yaml
    └── .gitignore
```

`tools.yaml` 的 Node 和搜索能力示例：

```yaml
tools:
  - id: repository-search
    type: cli
    purpose: repository-text-search
    capability: repository-search
    action_semantics: ordinary
    entrypoint: rg
    invocation_mode: direct
    version_source:
      command: rg
      arguments:
        - --version
    working_directory: repository-root
    use_when:
      - search source, tests, or configuration
    do_not_use_when:
      - execute project validation
    inputs: {}
    outputs: {}
    constraints: [read-only]

  - id: runtime-node-root
    type: runtime
    purpose: run-read-only-node-analysis-for-node-root
    capability: node-analysis
    action_semantics: ordinary
    entrypoint: node
    invocation_mode: direct
    version_source: package.json#engines.node
    working_directory: repository-root
    use_when:
      - run a registered read-only Node analysis script
    do_not_use_when:
      - lint, test, build, package, merge, or publish
    inputs:
      script: read-only
    outputs:
      result: text-or-json
    constraints: [ordinary-analysis-only]

  - id: run-test-node-root
    type: project-action
    purpose: validate-node-project
    capability: project-test
    action_semantics: test
    invocation_mode: managed
    task_ref: test:node-root
    working_directory: repository-root
    use_when:
      - run the registered Node test
    do_not_use_when:
      - perform ordinary repository inspection
    inputs:
      scope: validation-level
    outputs:
      evidence: Harness Evidence
    constraints:
      - invoke only through Harness
```

示例没有 `allowed_agents`、`denied_agents` 或逐次授权字段。

`tasks.yaml` 引用现有事实源：

```yaml
tasks:
  - id: test:node-root
    category: test
    automation_level: routine
    auto_allowed: true
    command_source: package.json#scripts.test
    command: [npm, run, test]
    backend: local
    working_directory: repository-root
    supports_scope: contract
    timeout: 5m
    outputs:
      report: .harness/reports/node-tests.json

  - id: test:github-ci-test
    category: test
    automation_level: routine
    auto_allowed: true
    source: .github/workflows/ci.yml#jobs.test
    backend: github-actions
    working_directory: repository-root
    supports_scope: contract
    timeout: 15m
    outputs:
      report: .harness/reports/github-actions-ci.json
```

### 1.7 Apply 结果

```yaml
status: applied
plan_digest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
changed:
  - AGENTS.md
  - .harness/tools.yaml
  - .harness/tasks.yaml
  - .harness/adapters/github-actions.yaml
unchanged: []
```

`preserve` 仍从 Plan 报告；Apply 结果不伪装成 Task Evidence。

### 1.8 失败与恢复

| 失败 | Harness 结果 | 用户恢复方式 |
|---|---|---|
| Node 版本来源冲突 | `CONFIG_INVALID` | 指定哪个现有文件是版本事实源 |
| Workflow 引用不存在的包脚本 | `CONFIG_INVALID` | 先修复项目事实或批准单独修复计划 |
| 受保护 Workflow 仍由外部事件直接启动 | `PROTECTED_TRIGGER_UNCONTROLLED` | 批准独立触发器改造计划；只有来源事实证明它不是 CI/CD 时才能排除 |
| 已有 `AGENTS.md` 无法安全合并 | `HANDOFF_REQUIRED` | 查看合并 Diff，调整最小入口或拒绝本次更新 |
| GitHub Actions 不可访问 | `BACKEND_UNAVAILABLE` | 保留配置，恢复 Backend 后重新校验 |
| 所需写入超出 `AGENTS.md` 与 `.harness/**` | `WRITE_SCOPE_EXPANDED` | 查看新增路径并重新 Handoff |

## 2. 为无 CI/CD 的 Python 项目建立 Harness

**状态**：P2 Bootstrap Available；P3 Local / GitHub Actions 调用管理 Available  
**对应用户用例**：[`UC-002`](../uc.md)  
**核心规则**：`TR-001`、`TR-002`、`DM-003`、`DM-007`、`HF-001`、`EV-002`

### 2.1 示例项目

```text
invoice-service/
├── pyproject.toml
├── uv.lock
├── src/
│   └── invoice_service/
└── tests/
```

项目没有 `.github/workflows/`，但 `pyproject.toml` 和 `uv.lock` 可以证明 Python 与 `uv` 是当前事实。

### 2.2 触发 Bootstrap

用户输入：

```text
请使用 initialize-ai-coding-harness 为当前 Python 项目建立最小 Harness。
先只读识别 Runtime、包管理器和已有测试入口，给出 Bootstrap Plan。
默认使用 Local Backend；GitHub Actions 必须单独列出并等待我选择。
```

### 2.3 查看发现结果

```yaml
repository_root: C:/work/invoice-service
project_types:
  - python
fact_sources:
  python: pyproject.toml
project_units:
  - id: python-root
    type: python
    root: .
    manifest: pyproject.toml
    commands:
      - name: test
        category: test
        argv: [uv, run, pytest]
        source: pyproject.toml#pytest-dependency
source_roots: [src]
test_roots: [tests]
workflows: []
gaps: []
```

没有 CI Workflow 不是错误；默认 Plan 只选择 Local Adapter。

### 2.4 查看 Bootstrap Plan

Plan 使用与 Adopt 相同的 0.3 机器契约，`plan_type` 为 `bootstrap`。本例的 `actions` 与精确 `write_scope` 包含 `AGENTS.md`、所需 `.harness/` 文件和 `.harness/adapters/local.yaml`；不包含 `.github/**`。`source_state` 绑定 `pyproject.toml`，每个 Action 绑定修改前与渲染后摘要。

### 2.5 用户确认

```text
确认当前 Bootstrap Plan 的 plan_digest。
只允许执行 Plan 中列出的精确路径；本次不创建 GitHub Actions。
```

Harness 创建独立 Plan Approval 后才能 Apply，不能因为未来可能需要云端 CI 而创建未选择的 Workflow。

### 2.6 预期配置

`tools.yaml` 示例：

```yaml
tools:
  - id: runtime-python-root
    type: runtime
    purpose: run-read-only-python-analysis-for-python-root
    capability: python-analysis
    action_semantics: ordinary
    entrypoint: python
    invocation_mode: direct
    version_source:
      command: python
      arguments: [--version]
    working_directory: repository-root
    use_when:
      - run a registered read-only Python analysis script
    do_not_use_when:
      - lint, test, build, package, merge, or publish
    inputs:
      script: read-only
    outputs:
      result: text-or-json
    constraints: [ordinary-analysis-only]

  - id: repository-search
    type: cli
    purpose: repository-text-search
    capability: repository-search
    action_semantics: ordinary
    entrypoint: rg
    invocation_mode: direct
    version_source:
      command: rg
      arguments:
        - --version
    working_directory: repository-root
    use_when: [search source, tests, or configuration]
    do_not_use_when: [execute project validation]
    inputs: {}
    outputs: {}
    constraints: [read-only]

  - id: run-test-python-root
    type: project-action
    purpose: validate-python-project
    capability: project-test
    action_semantics: test
    invocation_mode: managed
    task_ref: test:python-root
    working_directory: repository-root
    use_when: [run the registered Python test]
    do_not_use_when: [perform ordinary repository inspection]
    inputs:
      scope: validation-level
    outputs:
      evidence: Harness Evidence
    constraints: [invoke-only-through-Harness]
```

`tasks.yaml` 示例：

```yaml
tasks:
  - id: test:python-root
    category: test
    automation_level: routine
    auto_allowed: true
    backend: local
    working_directory: repository-root
    command_source: pyproject.toml#pytest-dependency
    command: [uv, run, pytest]
    supports_scope: contract
    timeout: 5m
    outputs:
      report: .harness/reports/python-tests.json
```

`impact.yaml` 示例：

```yaml
rules:
  - id: docs-only
    paths:
      - "**/*.md"
    validation_level: inspect

  - id: python-module
    paths:
      - src/invoice_service/**
      - tests/**
    validation_level: affected
    tasks:
      - test:python-root
```

### 2.7 Apply 结果

```yaml
status: applied
plan_digest: sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
changed:
  - AGENTS.md
  - .harness/harness.yaml
  - .harness/tools.yaml
  - .harness/tasks.yaml
  - .harness/impact.yaml
unchanged: []
```

### 2.8 失败与恢复

| 失败 | Harness 结果 | 用户恢复方式 |
|---|---|---|
| 找不到 Python 版本事实源 | `CONFIG_INVALID` | 在现有项目配置中声明 Runtime 版本 |
| Workspace 单元缺少可分类命令 | `ACTION_CLASSIFICATION_UNRESOLVED` | 在 Manifest 中声明命令后重新 Discover |
| 用户未选择 Backend | `HANDOFF_REQUIRED` | 选择 Local 或 GitHub Actions |
| 生成配置无法通过 Schema | `CONFIG_INVALID` | 不报告成功；修复生成器后重新执行 |

## 3. 局部修改、受影响验证与 Merge

**状态**：P3 Available（三级自动化与 Merge 每次确认）；P4 平台契约 Available
**对应用户用例**：[`UC-003`](../uc.md)、[`UC-004`](../uc.md)、[`UC-005`](../uc.md)、[`UC-006`](../uc.md)、[`UC-008`](../uc.md)、[`UC-011`](../uc.md)  
**核心规则**：`WB-001` 至 `WB-005`、`TR-004` 至 `TR-006`、`DM-002` 至 `DM-005`、`HF-003`、`EV-001` 至 `EV-006`

本路径继续使用第 2 条路径生成的 `invoice-service`。第 1 条 Node Adopt 是另一种初始化入口，与第 2 条二选一；完成任一初始化后都可以进入日常 Work。

### 3.1 批准 Work Grant

用户输入：

```text
请通过 initialize-ai-coding-harness 管理本次修改。
修复发票总额舍入问题。
允许写 src/invoice_service/** 和 tests/**，Merge 目标为当前分支。
本次交付目标为当前分支，风险等级为 low。
完成修改后由 Harness 选择最低充分验证；不要自行运行全量 CI。
```

目标 Grant：

```yaml
artifact_type: work-grant
schema_version: 0.3.0
grant_id: work-invoice-001
goal: fix-invoice-total-rounding
write_scope:
  - src/invoice_service/**
  - tests/**
merge_target: current-branch
validation_policy: minimum-sufficient
delivery_target: current-branch
risk_level: low
status: active
grant_digest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
```

### 3.2 查询普通工具

Agent 需要搜索订单状态定义时，先按能力查询 Registry：

```text
capability: repository-search
```

Registry 返回：

```yaml
id: repository-search
entrypoint: rg
working_directory: repository-root
example:
  - rg "round|Decimal|total" src/invoice_service tests
```

Agent 直接调用 `rg`，不需要普通工具授权。

### 3.3 修改并提交 Change Manifest

```yaml
artifact_type: change-manifest
schema_version: 0.3.0
manifest_id: change-invoice-001
grant_digest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
base_commit: example-sha
changed_paths:
  - src/invoice_service/calculation.py
  - tests/test_calculation.py
affected_modules:
  - invoice-service
public_contract_changed: false
dependency_changed: false
build_config_changed: false
recommended_tasks:
  - test:invoice
manifest_digest: sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
```

Harness 必须用实际 Diff 校验该声明，不能完全信任 Agent 自报。

### 3.4 选择最低充分验证

目标选择结果：

```yaml
artifact_type: selection
schema_version: 0.3.0
selection_id: selection-invoice-001
manifest_digest: sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
diff_digest: sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
status: selected
validation_level: affected
selected_tasks:
  - task_id: lint:invoice
    automation_level: routine
    decision: automatic
    reason: invoice module changed
  - task_id: test:invoice
    automation_level: routine
    decision: automatic
    reason: invoice behavior changed
skipped_tasks:
  - task_id: test:all
    reason: not required by current impact
  - task_id: integration:all
    reason: not required by current impact
reasons:
  - invoice-module matched the actual Diff
blocker_codes: []
selection_digest: sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd
```

Agent 即使建议 `full`，只要没有 [`DM-004`](specification.md#dm-004全量验证升级条件) 的事实，Harness 也不能升级。即使存在升级事实，Full CI 仍属于 `expensive`；没有本次确认时只能生成 Request，Backend 调用次数为零。

### 3.5 执行任务并读取 Evidence

成功示例：

```yaml
artifact_type: evidence
schema_version: 0.3.0
run_id: verify-invoice-001
task_id: validation:affected
status: passed
validation_level: affected
duration: 38s
summary: Invoice lint and unit tests passed.
primary_error: null
artifacts:
  - .harness/reports/invoice-tests.json
full_log: .harness/runs/verify-invoice-001/full.log
blocker_codes: []
backend: local
grant_digest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
manifest_digest: sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
diff_digest: sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
selection_digest: sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd
request_digest: sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee
commit_sha: example-sha
confirmation_status: not-required-by-explicit-policy
automation_level: routine
backend_calls: 1
formal_authority: false
platform: null
evidence_digest: sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff
```

失败示例：

```yaml
artifact_type: evidence
schema_version: 0.3.0
run_id: verify-invoice-002
task_id: test:invoice
status: failed
validation_level: affected
duration: 31s
summary: One invoice calculation test failed.
primary_error: "tests/test_calculation.py:74: expected 10.01, received 10.00"
artifacts:
  - .harness/reports/invoice-tests.json
full_log: .harness/runs/verify-invoice-002/full.log
blocker_codes: []
backend: local
grant_digest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
manifest_digest: sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
diff_digest: sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
selection_digest: sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd
request_digest: sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee
commit_sha: example-sha
confirmation_status: not-required-by-explicit-policy
automation_level: routine
backend_calls: 1
formal_authority: false
platform: null
evidence_digest: sha256:9999999999999999999999999999999999999999999999999999999999999999
```

Agent 默认只读取摘要。只有摘要不足时，才请求 `full_log` 的相关片段。

### 3.6 进入 Merge

必要验证通过后，Harness 先检查：

- Work Grant 仍有效。
- 实际 Diff 没有超出写边界。
- Change Manifest、验证选择和 Evidence 可追溯。
- Merge 目标没有变化。
- 所需 Required Checks 已声明。

满足这些条件只表示可以生成 Merge Request。Merge 目标属于受控分支，Harness
必须展示目标分支、提交摘要和验证 Evidence，并等待强确认：确认绑定 Task、动作语义、
完整目标 ref、commit SHA、策略版本与 Request digest。Harness 不得用本地或
`git-remote` Backend 直接修改该分支；确认后仍由 Branch Protection 和 Required
Checks 决定是否合并。

```yaml
artifact_type: task-request
schema_version: 0.3.0
request_id: merge-invoice-001
task_id: merge:pull-request
action_semantics: merge
validation_level: affected
target: main
commit_sha: example-sha
version: null
artifact_digest: null
environment: null
automation_level: critical
policy_version: 0.3.0
grant_digest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
manifest_digest: sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
selection_digest: sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd
request_digest: sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee
```

此时 Pipeline Readiness（就绪检查）只能是 `confirmation-required`；确认匹配后可变为 `ready-for-dispatch`，真实 Adapter 调用后才是 `dispatched`，平台 Evidence 完整后才能是 `passed`。

### 3.7 失败与恢复

| 失败 | Harness 结果 | 恢复方式 |
|---|---|---|
| Agent 修改 `src/customer/**` | `WRITE_SCOPE_EXPANDED` + `HANDOFF_REQUIRED` | 停止并重新 Handoff；不自动回滚用户工作区 |
| Impact Rules 无法覆盖路径 | `IMPACT_UNRESOLVED` | 补充项目事实，或用户明确选择验证级别 |
| Full CI 无本次确认 | `HANDOFF_REQUIRED`，Backend 调用次数为零 | 查看并确认 `expensive` Request |
| Merge 无本次确认 | `HANDOFF_REQUIRED`，Merge 调用次数为零 | 查看并确认 `critical` Request |
| 受控或未分类分支尝试直接 Push | `CONTROLLED_BRANCH_GATE_REQUIRED` + `HANDOFF_REQUIRED`，调用次数为零 | 生成强确认 Request 并改走平台门禁 |
| Required Checks 缺失 | `EVIDENCE_INCOMPLETE`，Merge 保持 `blocked` | 修复 Branch Protection 或补齐检查 |
| 必要测试失败 | `failed` Evidence | 按摘要修复并重跑所选 Task |
| Evidence 缺少日志引用 | `EVIDENCE_INCOMPLETE` | 修复 Backend 结果归一化 |

## 4. 用户确认后 Publish

**状态**：P3 Publish Request Available；P4 平台契约 Available；具体目标的平台审批按运行时事实判定
**对应用户用例**：[`UC-007`](../uc.md)、[`UC-009`](../uc.md)、[`UC-012`](../uc.md)  
**核心规则**：`DM-008`、`HF-002`、`HF-004` 至 `HF-006`、`EV-004`、`EV-006`

本路径继续使用第 3 条路径已经验证并 Merge 的 `invoice-service`。用户仍通过 `initialize-ai-coding-harness` 触发 Publish 准备；Merge 批准不能替代 Publish 确认。

### 4.1 请求准备 Publish

用户输入：

```text
请通过 initialize-ai-coding-harness 为当前已合并版本准备 Publish Plan。
先列出版本、制品、目标环境和执行任务，不要开始发布。
```

目标计划：

```yaml
artifact_type: task-request
schema_version: 0.3.0
request_id: publish-20260724-001
task_id: publish:registry
action_semantics: publish
validation_level: publish
target: package-registry
commit_sha: example-sha
version: 1.0.0
artifact_digest: sha256:7777777777777777777777777777777777777777777777777777777777777777
environment: production
automation_level: critical
policy_version: 0.3.0
grant_digest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
manifest_digest: sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
selection_digest: sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd
request_digest: sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee
```

### 4.2 独立确认

用户确认必须绑定本次版本、制品和目标：

```text
确认执行 publish-20260724-001：
版本 1.0.0，制品 dist/invoice-service-1.0.0.whl，
目标为 production package registry。
```

Harness 将确认保存为独立对象，只绑定当前 Request：

```yaml
artifact_type: confirmation
schema_version: 0.3.0
request_digest: sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee
confirmation_status: confirmed
confirmed_at: 2026-07-24T10:00:00+08:00
```

以下内容都不能替代该确认：

- “继续完成任务。”
- 之前的 Work Grant。
- Merge 批准。
- 其他版本或环境的 Publish 确认。

### 4.3 执行与 Evidence

用户确认后，GitHub Protected Environment 仍必须批准 production Job。发布 Secret、OIDC 身份或高权限 Token 只能由 CI/CD 平台交给受保护 Job，不能暴露给 Agent / Skill。

```yaml
artifact_type: evidence
schema_version: 0.3.0
run_id: publish-20260724-001
task_id: publish:registry
status: passed
validation_level: publish
duration: 74s
summary: Version 1.0.0 published to the production package registry.
primary_error: null
artifacts:
  - dist/invoice-service-1.0.0.whl
  - registry://invoice-service/1.0.0
full_log: .harness/runs/publish-20260724-001/full.log
blocker_codes: []
backend: github-actions
grant_digest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
manifest_digest: sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
diff_digest: sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
selection_digest: sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd
request_digest: sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee
commit_sha: example-sha
confirmation_status: confirmed
automation_level: critical
backend_calls: 1
formal_authority: true
platform:
  artifact_type: platform-evidence
  schema_version: 0.3.0
  platform: github-actions
  workflow: .github/workflows/publish.yml
  run_id: "123456"
  commit_sha: example-sha
  request_digest: sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee
  confirmation_status: confirmed
  approval_status: approved
  required_checks: passed
  protected_ref: null
  protected_environment: production
  artifact_digest: sha256:7777777777777777777777777777777777777777777777777777777777777777
  source_ref: refs/tags/v1.0.0
  platform_evidence_digest: sha256:8888888888888888888888888888888888888888888888888888888888888888
evidence_digest: sha256:9999999999999999999999999999999999999999999999999999999999999999
```

仓库内 Request 和确认记录只描述 Harness 流程，不能替代平台权限。正式 Publish / Deploy 是否获准，必须以 CI/CD 平台的 Protected Environment、审批状态、最小权限凭证和实际 Run 为准。本地执行结果只能用于调试，不能生成正式发布 Evidence。

### 4.4 外部事件

如果 Publish 来源是 Git Tag、Webhook 或 Schedule：

```text
外部事件
  → 按 Publish 语义创建 critical Request
  → 返回 HANDOFF_REQUIRED
  → 用户查看并独立确认
  → CI/CD 平台校验 Protected Environment 与审批
  → 执行 Publish Pipeline
```

外部事件本身不能直接启动受保护 Pipeline。

### 4.5 失败与恢复

| 失败 | Harness 结果 | 恢复方式 |
|---|---|---|
| 官方 Harness 路径缺少本次明确确认 | `PUBLISH_CONFIRMATION_REQUIRED` | 查看并确认当前 Publish Plan |
| 确认后版本或目标变化 | `HANDOFF_REQUIRED` | 重新生成和确认计划 |
| Protected Environment 未批准 | `blocked`，Publish Job 不启动 | 在 CI/CD 平台完成或拒绝审批 |
| Agent / Skill 可读取发布凭证 | `blocked` | 将 Secret / OIDC 身份隔离到受保护 Job |
| Publish Task 部分失败 | `failed` Evidence | 查看已产生副作用和恢复入口 |
| Agent 自建确认文件 | 不能替代平台审批 | 通过本次 Request 和 CI/CD 平台审批 |
| Backend 不可用 | `BACKEND_UNAVAILABLE` | 不报告成功，恢复 Backend 后重试 |

## 5. 结果检查清单

完成四条路径后，项目必须满足：

- [ ] Adopt 没有无确认重写已有 Workflow。
- [ ] Bootstrap 只生成用户选择的技术栈和 Backend。
- [ ] `tools.yaml` 能回答工具用途、入口、事实源和用法。
- [ ] `tools.yaml` 不包含 Agent / Skill 身份授权矩阵。
- [ ] CI/CD 动作按语义分类，不因 Shell、CLI、MCP 或 API 通道改变等级。
- [ ] 普通 CLI、Shell、MCP 和只读分析动作不触发 Harness 逐次审批。
- [ ] 小范围修改默认选择 `affected`，没有静默全量 CI。
- [ ] 只有显式自动允许的 `routine` Task 可以自动执行。
- [ ] Integration、E2E、Full CI 和大型 Build 未确认时 Backend 调用次数为零。
- [ ] 私有分支 Push 只允许精确非强推；受控或未分类分支要求强确认与平台门禁。
- [ ] 影响范围不明时返回 `IMPACT_UNRESOLVED`。
- [ ] 写入范围扩大时停止并重新 Handoff。
- [ ] Merge Evidence 与 Work Grant、Diff、本次确认、Required Checks 和提交摘要可追溯。
- [ ] 外部事件不能绕过自动化等级和平台门禁。
- [ ] Publish 必须获得绑定本次请求的独立确认。
- [ ] Protected Environment 未批准时 Publish / Deploy Job 不启动。
- [ ] 正式交付凭证不暴露给 Agent / Skill。
- [ ] Agent 默认只读取结构化错误摘要。
- [ ] 完整日志可通过 `run_id` 追溯。
- [ ] 文档不声称强制控制普通 MCP、网络、Shell、Runtime、CLI 或本地文件写入。

完整规则见 [`specification.md`](specification.md)，实施阶段见 [`plan.md`](../plan.md)。
