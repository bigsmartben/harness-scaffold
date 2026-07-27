# Harness 1.0 实施状态

规范版本：`1.0.0`

## 状态

Issue #2 的 H01–H13 实现已在 `codex/issue-2-rebaseline` 完成：

| 工作包 | 状态 | 主要产物 |
|---|---|---|
| H01–H04 | Available | 规范 SSOT、Schema、Snapshot、Facts、Action Graph、Projection |
| H05–H07 | Available | Plan-bound 发布、G0–G7、Work Grant、Runner、Postconditions、Evidence |
| H08–H10 | Available | Codex Plugin、Hooks、MCP 查询面、旧 Tool/Task/Adapter 适配 |
| H11 | Available | 2 × 6、Agent、确定性、旁路、App/CLI 语义契约测试 |
| H12 | Available | 文档和 Skill 统一为 Agent-bound 1.0；0.3 仅保留内部兼容读取 |
| H13 | Available | `uv tool install` 分发与 `sdd-harness init` |

## 验证门禁

- Plugin manifest 必须通过官方 `validate_plugin.py`。
- 项目验证必须通过 `.harness/tools.yaml` 登记的 `task_ref: test:contracts`。
- 分发冒烟必须从构建后的 wheel 安装，执行 `sdd-harness init --yes` 两次，并证明第二次为空 Diff。
- Push、PR、Merge、Publish、Release、Deploy 不在实现授权内，仍需独立确认和平台 Evidence。
