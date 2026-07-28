# Issue #22 / #23 — Harness 2.0 验收映射

| 需求 | 实现 | Evidence |
|---|---|---|
| 标准包结构 | `src/harness_core`、包内 Schema/Skill 资源 | wheel 与隔离安装烟测 |
| 单一仓库 Skill | `resources/repo_skill/harness` | Plugin 和初始化目标逐字节比较 |
| 四域与 16 Cell | `facts.py`、`action_graph.py`、`projection.py` | 缺失、重复、N/A 来源测试 |
| Skill-first / Hook 可选 | `initializer.py`、`codex_adapter.py` | 无 Hook active；启用后仅加固 |
| 项目策略 / 本次决定 | `policy.py`、`decisions.py` | 工作区、投影、动作、目标 stale 测试 |
| T0–T3 | `selection.py` | 文档、实现、Schema、Core/CI 表驱动测试 |
| Commit | `commit.py` | 临时 Index、无关暂存、部分暂存、受控分支 |
| Issue Provider | `issues.py` | Local / GitHub 分离、精确 receipt、无回退 |
| 版本边界 | `initializer.py` | 非 2.0 配置零写入拒绝，不提供历史迁移 |
| 分发 | `pyproject.toml`、`scripts/smoke_distribution.py` | `uv tool install` 隔离环境验收 |

Issue 回写只引用通过的自动化 Evidence；本地未通过或未执行的检查不得标记完成。

当前本地结果：`test:contracts` 23 项通过，`test:distribution-smoke` 通过。GitHub
Full CI 与远端 Issue 回写尚未执行。
