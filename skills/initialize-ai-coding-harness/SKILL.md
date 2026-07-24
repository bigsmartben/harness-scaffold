---
name: initialize-ai-coding-harness
description: Initialize, adopt, audit, update, or operate an AI Coding Harness in Python, Node, monorepo, or existing CI/CD repositories. Use when a user asks to bootstrap Harness configuration, index tools and tasks, preserve existing workflows, validate or repair `.harness/`, implement work inside a Grant, select or run verification, evaluate Merge readiness, or prepare a separately confirmed Publish, Release, or Deploy.
---

# Initialize AI Coding Harness

Build plans from repository facts, obtain approval before writes, apply only the approved paths, and validate the result.

## Route the request

| Intent | Route | Writes |
|---|---|---|
| Existing project or CI/CD | Adopt | After Plan approval |
| New project without CI/CD | Bootstrap | After Plan approval |
| Inspect existing `.harness/` | Audit | Never |
| Repair or refresh existing `.harness/` | Update | After Plan approval |
| Implement an approved change | Work | Inside the Work Grant |
| Select or run necessary checks | Verify | Auto only for explicitly allowed `routine`; confirm `expensive` |
| Evaluate or execute merge | Merge | Current confirmation plus platform gates |
| Publish, release, or deploy | Publish | Current confirmation plus platform gates |

Read [references/adopt-existing-project.md](references/adopt-existing-project.md) for Adopt. Read [references/bootstrap-new-project.md](references/bootstrap-new-project.md) for Bootstrap. Read [references/core-model.md](references/core-model.md) for Audit, Update, blockers, and Handoff. Read [references/tool-registry.md](references/tool-registry.md) when indexing tools. Read [references/delivery-model.md](references/delivery-model.md) when mapping Tasks or pipelines.

Read [references/github-platform-gates.md](references/github-platform-gates.md) when validating GitHub credentials, Required Checks, Branch Protection, Protected Environments, or formal delivery Evidence.

## Run Work, Verify, Merge, or Publish

1. For Work, verify that the Grant binds the goal, write scope, Merge target, validation policy, delivery target, and risk. Stop on any changed binding.
2. Compare the Change Manifest with the actual Diff. Run:

   `python scripts/select_validation.py <repository> <manifest.json> <diff.json> [--facts facts.json]`

3. If selection returns `IMPACT_UNRESOLVED`, report the missing facts; never silently run full CI.
4. Read each selected Task's automation metadata. Run only `routine` Tasks with `auto_allowed: true`. For `expensive` or unclassified Tasks, return a current Request and make zero backend calls.
5. Run an allowed Task through `scripts/run_task.py` or the registered GitHub Actions adapter. Return structured Evidence, not the complete log.
6. For Merge, use `scripts/evaluate_pipeline.py` with Evidence, a current Merge confirmation, and Required Checks state. Work approval never substitutes for Merge confirmation.
7. For Publish, show the version, artifact, target, request digest, and Protected Environment. Run no backend until a separate confirmation matches and the platform approval is present.

## Execute the workflow

1. Run read-only discovery:

   `python scripts/discover_repository.py <repository> --output <discovery.json>`

2. Build the selected plan:

   `python scripts/build_plan.py <discovery.json> --mode <adopt|bootstrap|audit|update> --output <plan.json>`

3. Show the plan digest, facts and sources, `create`/`update` actions, preserved paths, blockers, and proposed write scope.
4. For Audit, run validation and report without editing:

   `python scripts/validate_scaffold.py <repository>`

5. For Adopt, Bootstrap, or Update, stop until the user approves the plan digest and write scope. Set `approved` to `true` only from that confirmation.
6. Run `python scripts/apply_scaffold.py <approved-plan.json>`.
7. Run `python scripts/validate_scaffold.py <repository>`.
8. Report changed and unchanged paths, validation issues, preserved existing assets, and blockers.

## Enforce invariants

- Treat discovery and Audit as read-only.
- Never infer approval from the request to inspect or plan.
- Apply only actions and paths present in the approved plan.
- Preserve existing `AGENTS.md`; append the marked minimal entry only after showing the merge action.
- Preserve existing workflows unless the approved plan explicitly includes a workflow edit.
- Resolve CI/CD semantics to `task_ref` regardless of whether the action arrived through Shell, CLI, MCP, or API. Do not route ordinary tools through Harness approval.
- Return `PROTECTED_TRIGGER_UNCONTROLLED` when a protected workflow still has direct `push`, `pull_request`, or `schedule` triggers.
- Return `WRITE_SCOPE_EXPANDED` and `HANDOFF_REQUIRED` before adding a path outside the approved scope.
- Keep Schema, scaffold, and backend templates under `assets/` as their only source.
- Treat Agent validation suggestions as input only; the selector owns the final Task set.
- Select `full` only with a DM-004 fact.
- Treat Integration, E2E, Full CI, and large Build as `expensive`; do not dispatch them without current confirmation.
- Treat Push, Merge, Publish, Release, and Deploy as `critical`; require current confirmation every time.
- Accept formal delivery status only from CI/CD platform Evidence bound to the current request.
- Preserve complete logs under `.harness/runs/`, but expose only the first useful error by default.
- Never reuse Work, Merge, or historical approval for another critical action.
- Do not claim to enforce ordinary MCP, network, Shell, Runtime, CLI, or local file writes.
