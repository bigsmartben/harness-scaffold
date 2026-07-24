# Tool Registry

Register capabilities or actions, not unrestricted executables.

| Entry | `invocation_mode` | Example |
|---|---|---|
| Ordinary capability | `direct` | `rg`, Python analysis, Shell helper, ordinary MCP tool |
| CI/CD semantic action | `managed` | test, build, push, merge, publish, release, deploy |

Every `managed` entry references a valid Task with automation metadata. Classify by action semantics, not by Runtime, Shell, CLI, MCP, or API channel. Register MCP servers and individual MCP tools separately. Record version and task facts by source reference rather than copying a value.

Never add Agent or Skill identity authorization fields such as `allowed_agents` or `denied_agents`. Registry is an index and usage guide, not an authorization matrix, per-call approver, or proxy.
