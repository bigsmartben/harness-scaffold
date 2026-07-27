---
name: initialize-ai-coding-harness
description: Initialize, adopt, audit, update, or operate an AI Coding Harness for Python, Node, workspace-declared monorepos, and GitHub Actions. Use for 初始化、接管、审查、更新、实施 Work、选择验证、运行 Task、评估 Merge，或准备 Publish、Release、Deploy when the repository uses or needs `.harness/`.
---

# Initialize AI Coding Harness

## Route

Classify the request before loading details.

| Intent | Route | Reference |
|---|---|---|
| Existing repository or CI | Adopt / 接管 | [references/adopt-existing-project.md](references/adopt-existing-project.md) |
| New supported repository | Bootstrap / 初始化 | [references/bootstrap-new-project.md](references/bootstrap-new-project.md) |
| Inspect current Harness | Audit / 审查 | [references/core-model.md](references/core-model.md) |
| Repair current `0.3` Harness | Update / 更新 | [references/core-model.md](references/core-model.md) |
| Index a tool or action | Registry / 工具登记 | [references/tool-registry.md](references/tool-registry.md) |
| Work, Verify, Merge, Publish, Release, Deploy | Delivery / 交付 | [references/delivery-model.md](references/delivery-model.md) |
| Validate GitHub authority or Evidence | Platform / 平台门禁 | [references/github-platform-gates.md](references/github-platform-gates.md) |

Load only the listed Reference for the active route. Load each Reference directly from this file; do not follow a second Reference chain. Load `assets/schemas/` only when validating an artifact or configuration. Load a scaffold or backend asset only when an approved Plan names it.

## Execute

1. Run read-only discovery. Print to stdout by default; if a file is needed, place it outside the target repository.
2. Build the selected Plan and report its facts, exact actions, exact write scope, blockers, and `plan_digest`.
3. For Audit, validate and report without writing.
4. For Adopt, Bootstrap, or Update, stop until the user confirms the unchanged Plan digest and scope. Create a separate Approval outside the repository, then run `apply_scaffold.py PLAN --approval APPROVAL`.
5. For Work or Verify, validate every runtime Artifact, then bind Grant, Manifest, actual Diff, Selection, Request, commit, and Confirmation before invoking a Task.
6. For Push, require an exact remote, `refs/heads/*` target, commit, and current Confirmation. A `git-remote` Adapter may make one non-force `git push` call and proves only that exact Push.
7. For Merge or Publish, evaluate readiness first. Report `ready-for-dispatch` when no Adapter call was made. Finalize as `passed` only from complete, matching Platform Evidence.
8. Run `validate_scaffold.py` after configuration writes and preserve complete Task logs under `.harness/runs/`.

## Stop

Stop before writes or Adapter calls when any of these conditions holds:

- A Plan, Approval, Grant, Manifest, Selection, Request, Confirmation, Evidence, or Platform Evidence fails its runtime Schema or digest; or its bound facts changed.
- An action lacks `action_semantics`, a CI/CD action is direct, a Task reference is missing, or Task scope cannot cover the selected validation level.
- A path exceeds the approved scope or the Change Manifest differs from the actual Diff.
- A repository contains unsupported MCP, Make, Gradle, Maven, Fastlane, or unclassified script facts. Record the source-backed gap; do not invent a Tool, Task, or Adapter.
- Existing configuration is not `0.3.0`. Return `CONFIG_INVALID` and require a new Adopt or Bootstrap instead of migrating it.
- An expensive or critical Task lacks current matching Confirmation.
- A Local backend is asked to perform Push, Merge, Publish, Release, or Deploy. The narrow `git-remote` backend is not Local: it supports only an exact confirmed, non-force Push.
- Platform Evidence lacks a matching Workflow run, commit, approval, protected environment, required checks, or applicable artifact digest.

Return the stable blocker codes from `assets/schemas/common.schema.json` and include `HANDOFF_REQUIRED` when user or platform authority is needed.

## Report

Report:

- selected route and loaded Reference;
- facts and their sources;
- Plan or Request digest and exact scope;
- changed, unchanged, and preserved paths;
- selected and skipped Tasks with validation level;
- Adapter call count and state: `blocked`, `confirmation-required`, `ready-for-dispatch`, `dispatched`, or `passed`;
- Evidence bindings, first useful error, full-log path, and blocker codes.

Never claim that Registry entries authorize ordinary tools or that local/configuration-only evidence proves formal delivery authority.
