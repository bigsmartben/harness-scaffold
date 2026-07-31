# Epic #49 验收追踪

权威计划、状态和验收结论见
[GitHub Epic #49](https://github.com/bigsmartben/harness-scaffold/issues/49)。
本文件只提供代码内稳定追踪关系，不复制 Issue 清单。

| 场景 | 所有者 | Schema / 实现 | 自动化 Evidence |
|---|---|---|---|
| 固定 2-2-4 与新 generate/enforce 语义 | #50 | `model.py` | `test_issue_50_model_semantics.py` |
| Rule / Operation / cancel | #51 | `rule.schema.json`、`operation.schema.json`、`lifecycle.py` | `test_issue_51_lifecycle.py` |
| 新旧仓库 load 与校准 | #52 | `load.schema.json`、`load-result.schema.json`、`load_core.py` | `test_issue_52_load_core.py` |
| Skill 自然语言边界 | #53 | `skill_adapter.py`、分发 `SKILL.md` | `test_issue_53_skill_adapter.py` |
| 投影与 enforce 闭环 | #54 | `enforcement.schema.json`、`scaffold.py` | `test_issue_54_scaffold.py` |
| bootstrap、升级与分发 | #55 | `bootstrap.py`、`cli.py`、wheel/sdist | `test_issue_55_bootstrap_cli.py`、`smoke_distribution.py` |
| 跨层用户行为 | #56 | 上述同版合同 | `test_issue_49_reconstruction.py`（含 App→CLI operate、CLI→App cancel） |

CI 的 `contracts` job 顺序执行全量 pytest、构建以及隔离 wheel/sdist smoke。
