# Issue #28 — Harness 2.0 消费者验收证据映射

版本：`2.0.0`

本文件把 Issue #28 的 US-01～US-11 映射到可重复执行的仓库场景。正式放行
只引用通过的 Harness Evidence、GitHub Actions 回执和 Issue 回写记录。

## 可重复入口

| 验证 | Harness `task_ref` | 报告 |
|---|---|---|
| 契约、单元、真实 Git Fixture 与本地 Adapter | `test:contracts` | `.harness/reports/contracts.json` |
| wheel、隔离安装、两阶段初始化与安装失败 | `test:distribution-smoke` | `.harness/reports/distribution-smoke.json` |
| 完整远端 CI | `ci:full` | GitHub Actions Workflow Run |

## 场景映射

| Evidence 组 | 场景 | 自动化来源 |
|---|---|---|
| E-01 安装 | S01.1、S01.2 | `scripts/smoke_distribution.py`：空目录版本检查、唯一入口、不可用源零入口 |
| E-02 初始化 | S02.1～S02.4 | `tests/integration/test_initializer.py`、Distribution Smoke |
| E-03 模式与计划 | S03.1～S03.4 | `test_entrypoint_and_projection_are_two_exact_phases`、`test_projection_plan_stales_when_a_source_changes` |
| E-04 Blue 投影 | S04.1、S04.2 | `test_entrypoint_and_projection_are_two_exact_phases`、`test_four_domain_projection_has_exactly_sixteen_records` |
| E-05 Gray 投影 | S05.1～S05.3 | `tests/integration/test_consumer_projection.py` 的 Gray、Monorepo、冲突场景 |
| E-06 用户核验 | S06.1～S06.4 | `test_status_reports_current_artifacts_and_exact_stale_source`、两阶段幂等场景 |
| E-07 本地工作 | S07.1～S07.3 | `tests/integration/test_local_action.py`：解析器真实修改、最近 Action、缺失绑定与等级拒绝 |
| E-08 最低验证 | S08.1～S08.5 | `test_t0_t3_selector_uses_minimum_sufficient_validation`、本地 Action 成功/失败 Evidence |
| E-09 Commit | S09.1～S09.3 | `tests/integration/test_commit.py`：临时 Index、无关暂存、部分暂存、分支门禁 |
| E-10 Issue | S10.1～S10.4 | `test_local_and_remote_issue_adapters_do_not_fallback` 及 Remote Receipt 契约 |
| E-11 受控交付 | S11.1～S11.6 | `tests/integration/test_push.py`、`tests/unit/test_controlled_delivery.py` |

## Evidence 字段来源

每个 Fixture 测试以临时目录或临时裸 Git Remote 从干净副本开始。以下字段由
测试断言、Harness 报告或平台回执共同提供：

| Issue 要求字段 | 来源 |
|---|---|
| `fixture_id`、`scenario_id` | 上表测试 Node ID 与场景名称 |
| `initial_tree_digest`、`final_tree_digest` | 初始化/Distribution Smoke 的字节级树摘要与计划摘要 |
| `initial_git_status`、`final_git_status` | 集成测试中的真实 `git status` 断言 |
| `user_request`、`user_visible_result` | Skill 路由、CLI JSON 摘要与 Issue 场景固定输入 |
| `changed_paths`、`preserved_paths` | 初始化、投影、Commit 和本地 Action 结果 |
| `validation_actions`、`blocker_codes` | Action Evidence 和失败关闭断言 |
| `provider_call_count`、`provider_receipt` | Issue/Delivery 单次 Provider 模拟与 Git/平台真实回执 |

`.harness/reports/`、`.harness/evidence/`、`.harness/runtime/` 和
`.harness/cache/` 均为 Git 忽略的运行 Evidence，不进入产品源码 Diff。

## 放行规则

只有以下三项同时通过，才可把 Issue #28 从 `proposed` 回写为 `accepted`，并
更新 #22 的 W10 / P5：

1. `test:contracts` 全部通过；
2. `test:distribution-smoke` 通过；
3. 当前放行 Commit 的 `ci:full` GitHub Actions 回执为成功。

任何失败均保留失败 Evidence，不更新 accepted 状态。
