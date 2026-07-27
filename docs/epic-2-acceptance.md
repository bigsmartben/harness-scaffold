# Epic #2 验收证据索引

本索引把 Epic #2 的 H01–H13 实施契约映射到唯一规范、实现与自动化 Evidence。权威规则仍只来自 [`specification.md`](specification.md)；本文件不是第二套 SSOT。

| Issue | 交付物 | 主要实现 | 自动化 Evidence |
|---|---|---|---|
| H01 / #3 | 规范 SSOT、用例、0.3 迁移决议 | `docs/specification.md`, `uc.md` | `tests/unit/test_documentation.py`, `tests/unit/test_evals.py` |
| H02 / #4 | Governance Schema、canonical blocker enum、跨文件 Validator | `assets/schemas/governance.schema.json`, `harness_core/contracts.py` | `tests/unit/test_contracts.py`, `tests/unit/test_governance_core.py` |
| H03 / #5 | 固定 Snapshot 与 source-backed facts | `harness_core/snapshot.py`, `harness_core/facts.py` | `tests/integration/test_initialize_workflows.py`, `tests/unit/test_governance_core.py` |
| H04 / #6 | Action Graph 与 2 × 6 Projection Compiler | `harness_core/action_graph.py`, `harness_core/projection.py` | 工具密集 Fixture 与确定性矩阵测试 |
| H05 / #7 | Bootstrap / Adopt / Update、零写入预检、单写者发布 | `harness_core/initializer.py` | 初始化、回滚、幂等和多级 `AGENTS.md` 测试 |
| H06 / #8 | G0–G7、Work Grant、聚合确认 | `harness_core/gates.py` | 八个 Gate 的表驱动阻断分支与低交互测试 |
| H07 / #9 | Narrow Runner、Postcondition、Evidence 摘要链 | `harness_core/runner.py`, `harness_core/postconditions.py` | 真实最小测试 Action、绑定覆盖拒绝、不可解析报告拒绝测试 |
| H08 / #10 | Codex Plugin、版本握手、窄 MCP | `plugins/harness/`, `harness_core/mcp_server.py` | Plugin 结构、只读 MCP、缺失/不兼容握手测试 |
| H09 / #11 | 六类生命周期 Hook、旁路阻断、bootstrap-only | `harness_core/codex_adapter.py`, `plugins/harness/hooks/hooks.json` | 固定事件输出、Shell / apply_patch / MCP 旁路、Hook 不受信测试 |
| H10 / #12 | 旧 Tool / Task / Adapter / Pipeline 迁移 | `harness_core/automation.py`, `bindings.py`, `pipeline.py`, `platform.py` | `tests/unit/test_delivery.py`, `tests/unit/test_platform.py` |
| H11 / #13 | 集中集成矩阵、规范覆盖、前向评测 | `tests/fixtures/`, `tests/integration/`, `evals/coverage.yaml` | 2 × 6、工具密集、Monorepo、多级 `AGENTS.md`、公共入口适配链 |
| H12 / #14 | 文档统一、旧模型清理、完成索引 | `README.md`, `docs/`, `plan.md`, Skill references | 文档链接、术语、唯一 Runtime / SSOT 一致性测试 |
| H13 / #16 | `uv tool` Distribution 与 `sdd-harness init` | `pyproject.toml`, `harness_core/cli.py`, `scripts/smoke_distribution.py` | 隔离 wheel 安装、入口、init 幂等、Codex Adapter 与缺 Evidence 失败关闭 |

## 固定验证入口

仓库注册的最低充分验证为：

```text
test:contracts
test:distribution-smoke
```

`test:contracts` 必须覆盖规范规则映射；`test:distribution-smoke` 必须从 wheel 构建与 `uv tool install` 开始，经过 `sdd-harness init`、Projection 加载、Codex Hook 旁路阻断，并证明缺少 Evidence 时失败关闭。

测试通过只证明对应 commit 的本地确定性契约。Push、PR、Merge 和受保护平台结论仍必须使用各自 Harness Task 与 GitHub Platform Evidence。
