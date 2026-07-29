# Harness 3.0 行为验收追踪

权威需求：
[GitHub Issue #40](https://github.com/bigsmartben/harness-scaffold/issues/40)。
本文件只提供稳定的行为—测试—CI 映射，不记录可编辑的 Issue 状态或验收结论。

| 场景 | 自动化测试 | 补充证据 | CI job |
|---|---|---|---|
| `M-G01` | `tests/bdd/test_issue_40_scenarios.py::test_m_g01_fixed_model_is_exactly_sixteen_differentiated_cells` | `tests/unit/test_projection_v3.py` 的独立完整字面量 | `contracts` |
| `M-G02` | `tests/bdd/test_issue_40_scenarios.py::test_m_g02_fixed_model_tampering_is_read_only_and_rejected` | tamper 与 atomic-replace 单元测试 | `contracts` |
| `M-G03` | `tests/bdd/test_issue_40_scenarios.py::test_m_g03_public_and_generated_surfaces_are_guidance_only` | `scripts/smoke_distribution.py` 制品负向扫描 | `contracts` |
| `M-G04` | `tests/bdd/test_issue_40_scenarios.py::test_m_g04_legacy_inputs_are_rejected_before_any_write` | CLI v2 与旧 Artifact 集成测试 | `contracts` |
| `C-G01` | `tests/bdd/test_issue_40_scenarios.py::test_c_g01_rules_project_to_guidance_without_external_side_effects` | 投影字段单元测试 | `contracts` |
| `C-G02` | `tests/bdd/test_issue_40_scenarios.py::test_c_g02_cardinality_order_and_digest_rules_are_deterministic` | 规则 0/1/N 与摘要单元测试 | `contracts` |
| `C-G03` | `tests/bdd/test_issue_40_scenarios.py::test_c_g03_invalid_rules_have_precise_diagnostics_and_zero_writes` | 契约诊断单元测试 | `contracts` |
| `C-G04` | `tests/bdd/test_issue_40_scenarios.py::test_c_g04_execution_and_authorization_fields_never_call_providers` | CLI、导出、wheel/sdist 负向扫描 | `contracts` |
| `C-G05` | `tests/bdd/test_issue_40_scenarios.py::test_c_g05_minimal_input_is_explicit_and_never_default_completed` | 最小初始化集成测试 | `contracts` |

CI 的 `contracts` job 顺序执行全量 pytest、构建、wheel/sdist 干净环境 smoke 和
仓库自举校验。正式发布工作流在同一制品上重复这些检查。
