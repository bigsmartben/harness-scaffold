# Harness 2.0 实施状态

规范版本：`2.0.0`

| 阶段 | 状态 | 主要产物 |
|---|---|---|
| P1 契约与包结构 | Implemented | `src/harness_core`、2.0 Schema、单一 Skill、只读 v1 迁移 |
| P2 四域编译器 | Implemented | Snapshot、Facts、Action Graph、16 Cell、显式 Coverage |
| P3 Skill-first 运行面 | Implemented | AGENTS、仓库 Skill、项目策略、本次决定、T0–T3 |
| P4 Commit / Issue / Delivery | Implemented | 临时 Index、Provider 分离、精确决定、分支边界 |
| P5 发布验收 | Validated locally | wheel、隔离 `uv tool install`、文档、Plugin 生成副本 |

发布前必须通过：

- `task_ref: test:contracts`
- `task_ref: test:distribution-smoke`
- wheel Skill 与目标仓库 Skill 逐字节一致
- 无 Hook 和显式 Hook 两条路径
- 1.0 零写入迁移与 stale digest 拒绝
- Commit、Issue、16 Cell、T0–T3 集成测试

本地 Evidence：`test:contracts` 22 项通过；`test:distribution-smoke` 通过
wheel 构建、隔离安装、Skill 字节一致、无 Hook / 显式 Hook、1.0 迁移和项目
Python 隔离检查。

Push、PR、Merge、Publish、Release、Deploy 不包含在本地实现授权中，仍需独立本次
决定和平台 Evidence。GitHub Full CI 与 #22/#23 远端回写也需各自的本次决定。
