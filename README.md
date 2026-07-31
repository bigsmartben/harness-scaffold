# SDD Harness

Harness 是基于固定 2-2-4 模型的仓库治理系统。它从仓库事实和已有治理来源生成
四域规则，由脚手架维护权威状态、确定性投影和内部执行保障；Harness Skill 是
用户的自然语言治理接口，不是实现、测试、Git、发布或部署入口。

当前重构的实施与验收状态以
[GitHub Epic #49](https://github.com/bigsmartben/harness-scaffold/issues/49)
为唯一事实源（SSOT, Single Source of Truth）。

当前合同版本是 `4.0.0`。首次 consumer bootstrap：

```text
uv tool install "sdd-harness @ git+https://github.com/bigsmartben/harness-scaffold.git@v4.0.0"
cd <consumer-repository>
harness load
```

## 固定模型

| 轴 | 固定值 |
|---|---|
| Audience（适用方） | `maintainer`、`consumer` |
| Responsibility（治理职责） | `generate`、`enforce` |
| Governance Domain（治理域） | `specification`、`implementation`、`verification`、`delivery` |

```text
2 × 2 × 4 = 16 个固定 Cell
```

`generate` 包含事实发现、已有治理读取、规整、分类、calibration（校准）和投影。
calibration 不是第三种 Responsibility。

`enforce` 表示脚手架建立治理义务、接收外部垂直执行者的类型化证据并核验结果。
它不再等同于 Schema、摘要或模型锁漂移校验。

## 三层协作

| 层 | 做什么 | 实例 |
|---|---|---|
| Harness Skill | 理解治理意图并提交类型化请求 | “停用 contract-tests”→ disable 请求 |
| Harness 脚手架 | 发现事实、保存权威状态、投影并执行保障 | 对测试证据返回 `satisfied` / `blocked` |
| 垂直业务执行者 | 实现、测试、Git、发布、部署 | 测试 Worker 实际运行契约测试 |

Skill 不会因为用户提到 verification 就运行测试，也不会因为用户提到 delivery
就发布软件。

## 权威关系

```text
仓库事实 + 已有治理来源
          │
          ▼
       generate
          │
          ▼
     权威规则状态
       │       │
       ▼       ▼
  规则投影   enforce 保障状态
```

规则投影和保障状态都是可重算派生物，不是第二份规则 SSOT。聊天、Agent 总结和
Memory 不构成权威治理状态或执行证据。

## Maintainer / Consumer 边界

本仓库开发并分发 Harness，不是 consumer 初始化目标。根目录通过 `AGENTS.md`、
规范源码和仓库测试闭环；consumer 的 load、规则变更和执行保障只能在外部或临时
仓库验收。

## 文档

- [规范说明](docs/specification.md)
- [2-2-4 治理模型白皮书](docs/harness-2x2x4-governance-model-whitepaper.md)
- [快速开始与实施状态](docs/quickstart.md)
- [仓库结构](docs/repository-structure.md)
- [历史 3.0.1 发布说明](docs/release-notes-3.0.1.md)

3.0.1 的 guidance-only 语义是历史发布合同。Harness 4 在 load 成功后将可识别
旧输入归档并建立唯一权威状态，不把旧配置保留为第二个现行 SSOT。
