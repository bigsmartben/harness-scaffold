# Harness 4.0.0

Harness 4.0.0 is the initial repository-governance release.

- The fixed Audience × Responsibility × Governance Domain model still has
  exactly sixteen Cells.
- `generate` covers discovery, existing-governance reading, normalization,
  classification, calibration, and deterministic projection.
- `enforce` creates typed obligations and verifies external evidence.
- Rules have stable identity, revision, sources, enabled/disabled state, and
  operation history.
- Typed add, update, disable, enable, delete, and cancel operations use
  optimistic base revisions and atomic state replacement.
- `harness load` bootstraps new repositories without a pre-existing repository
  Skill.
- Load exposes typed request/result schemas, explicit governance-source
  priorities, deterministic duplicate merging, and fact-driven baseline
  recalibration when a current v4 state is reloaded.
- App and CLI adapters exchange the same typed operation/cancel contracts, and
  enforcement decisions are exactly recomputable from authoritative inputs.
- The public CLI is `load`, `operate`, `cancel`, and `inspect`.

Harness Skill remains a governance interface. It does not implement code, run
tests, perform Git operations, release, or deploy software.
