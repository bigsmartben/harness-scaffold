# Repository Document Facts

Use the following evidence order. Prefer the highest available source and
record conflicts instead of guessing.

| Fact | Preferred evidence | Example |
|---|---|---|
| Repository identity | package metadata, executable entrypoint, current README | `pyproject.toml` project name and description |
| Supported commands | package scripts, task registry, CI workflow | `package.json#scripts.test` |
| First success | executable smoke test or integration test | a CLI command with an asserted output |
| Contributor workflow | repository policy and registered local actions | validation command bound by the project |
| Release ownership | release workflow, maintainer policy, tags | a source-backed publish job |
| Agent boundary | AGENTS.md and repository Harness | controlled branch and action rules |
| Product behavior | accepted requirements and tests | one user flow asserted by an integration test |
| Technology choice | decision record and reproducible experiment | a candidate comparison with passing evidence |
| Architecture | code boundaries, deployment configuration, accepted decisions | module dependency and runtime topology |

## Conflict handling

1. Prefer current executable or machine-readable facts over stale prose.
2. Preserve disputed prose only when clearly labeled as historical.
3. Use `TODO(fact): <missing fact>` for a non-blocking gap.
4. Stop with `DOCUMENT_FACTS_MISSING` when a required command, owner, business
   rule, technology decision, or architecture conclusion has no authority.

## Repository type

- Library: emphasize API purpose, installation, supported runtimes, and a
  minimal usage example.
- Application: emphasize setup, first runnable state, configuration, and
  deployment boundaries.
- CLI: emphasize installation, one successful command, input/output, and exit
  behavior.
- Scaffold or template: write QUICKSTART for the template consumer. Keep
  scaffold maintenance in DEVELOPMENT and MAINTAINER.
- Monorepo: identify the root responsibility and link to component-local docs
  instead of flattening every workflow into the root README.
