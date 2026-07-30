# Harness 3.0.1

Harness 3.0.1 is a maintenance release for the fixed local 2-2-4
specification governance scaffold.

## GitHub Actions platform boundary

- Migrates the external Action wrappers from Node.js 20 to audited Node.js 24
  releases.
- Pins `actions/checkout` and `astral-sh/setup-uv` to immutable full commit
  SHAs.
- Removes `actions/setup-python`; uv now installs and selects Python 3.12.
- Pins the uv bootstrap version and adds repository plus distribution checks
  that reject mutable Action references and Node.js project assets.

## Governance compatibility

- Audience, Responsibility, Governance Domain, the sixteen fixed Cells, and
  guidance-only rule semantics are unchanged.
- The exact Core, Contract, Compiler, Schema, CLI, and package version advances
  to `3.0.1`.
- Existing `3.0.0` repositories must update `schema_version` to `3.0.1` and
  regenerate `model.lock.json` with `sdd-harness project`; no automatic
  migration or fallback is performed.

This release does not publish to PyPI.
