# Harness 2.0 实施状态

规范版本：`2.0.0`

| 阶段 | 状态 | 主要产物 |
|---|---|---|
| P1 契约与包结构 | Implemented | `src/harness_core`、2.0 Schema、单一 Skill、无历史兼容 |
| P2 四域编译器 | Implemented | Snapshot、Facts、Action Graph、16 Cell、显式 Coverage |
| P3 Skill-first 运行面 | Implemented | AGENTS、仓库 Skill、项目策略、本次决定、T0–T3 |
| P4 Commit / Issue / Delivery | Implemented | 临时 Index、Provider 分离、策略/决定生命周期、平台门禁、精确交付回执 |
| P5 发布验收 | Validated locally | wheel、隔离 `uv tool install`、文档、Plugin 生成副本 |

发布前必须通过：

- `task_ref: test:contracts`
- `task_ref: test:distribution-smoke`
- wheel Skill 与目标仓库 Skill 逐字节一致
- 无 Hook 和显式 Hook 两条路径
- 非 2.0 配置零写入拒绝与 stale plan digest 拒绝
- Commit、Issue、策略、决定、受控交付、16 Cell、T0–T3 集成测试

本地 Evidence：`test:contracts` 39 项通过；`test:distribution-smoke` 通过
wheel 构建、隔离安装、Skill 字节一致、无 Hook / 显式 Hook、历史配置拒绝和项目
Python 隔离检查。

PR、Merge、Publish、Release、Deploy 已有统一的确定性计划、平台门禁、Provider
请求和回执校验适配层；每次实际远端执行仍需独立本次决定。GitHub Full CI 与
#22/#23 远端回写也需各自的本次决定。
