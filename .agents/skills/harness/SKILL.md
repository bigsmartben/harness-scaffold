---
name: harness
description: Validate and project the fixed Harness 3.0 specification governance model and repository guidance rules.
---

# Harness 3.0

Contract version: `3.0.1`.

Harness is a local specification governance scaffold. Its fixed model has
three orthogonal axes:

- Audience: `maintainer`, `consumer`
- Responsibility: `generate`, `enforce`
- Governance Domain: `specification`, `implementation`, `verification`,
  `delivery`

The axes always produce exactly sixteen Cells. `2-2-4` is only a count
shorthand; it is not a hierarchy.

The only user extension point is `rule_instances` under the four explicit
governance domains in `.harness/harness.yaml`. Every projected rule has fixed
`kind: guidance`. Rules cannot grant permission, block an operation, select a
workflow, or invoke a remote Provider.

Use only these local commands:

- `sdd-harness init`
- `sdd-harness project`
- `sdd-harness validate`
- `sdd-harness inspect`

Invalid or legacy input must fail before any write. Harness 3.0 does not read,
migrate, complete, alias, or fall back to v1/v2 configuration or artifacts.
