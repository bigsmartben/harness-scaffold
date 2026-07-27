# 正确入口与调用方式

当前 Harness 配置有效：对工作区运行只读校验

```powershell
.\.venv\Scripts\python.exe skills\initialize-ai-coding-harness\scripts\validate_scaffold.py .
```

退出码为 `0`，输出为 `[]`，即没有配置校验问题。

| 目的 | 注册入口 | 模式 | 怎样调用 |
|---|---|---|---|
| 搜索仓库 | `repository-search`（入口 `rg`） | `direct`（直接调用） | 在仓库根目录运行 `rg "<查询词>"`；例如 `rg "task_ref" .harness`。它是只读搜索，不用于运行验证。 |
| 读取 GitHub 文件 | `github-get-file`（`github.get_file_contents`） | `direct`（直接调用） | 直接调用 GitHub MCP 工具并传 `repository` 与 `path`；例如 `github.get_file_contents(repository: "owner/repo", path: "README.md")`。`github-server` 是服务器级索引，具体读文件应选工具级入口 `github-get-file`。 |
| 运行项目测试 | `contract-tests` | `managed`（Harness 管理） | 该入口解析到 Task `test:contracts`。完成验证选择后，通过 Harness runner 调用，例如 `python skills/initialize-ai-coding-harness/scripts/run_task.py . test:contracts --level affected --adapter .harness/adapters/local.yaml`，而不是把测试当普通 direct 工具执行。当前 Task 是 `routine` 且 `auto_allowed: true`。本次仅说明入口，没有运行测试。 |

`direct` 和 `managed` 是调用路由，不是身份授权：

- 普通只读能力（例如 `rg`、GitHub 读文件 MCP 工具）走 `direct`。
- Test、Build、Publish 等具有 CI/CD 语义的动作走 `managed`，并通过 `task_ref` 绑定 Task。
- 注册表（registry）只是能力索引和使用指南，不是授权矩阵、逐次审批器或代理；是否能实际调用仍取决于运行环境权限以及受管动作自身的确认/平台门禁。

本次没有运行项目测试，也没有触发 Publish。
