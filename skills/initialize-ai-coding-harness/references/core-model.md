# Core model

Treat `.harness/governance/rules.json` as the structured governance SSOT and `projection.lock.json` as its repository binding.

```text
Snapshot → Facts → Action Graph → 2 × 2 × 4 Governance Projection → Validate → Publish
Action Request → Resolve → G0–G5 → Runner → Postconditions → G6–G7 → Evidence
```

Audit is only a read-only view of `generate` or `enforce`. A changed governance input invalidates the projection and Work Grant. Missing or untrusted custom Agents fail closed; do not use a generic fallback.

The projection covers two Audiences (`maintainer`, `consumer`), two Responsibilities (`generate`, `enforce`), and four SDD Governance Domains (`specification`, `implementation`, `verification`, `delivery`). Agent, runtime, tool, project profile, and Evidence concerns are horizontal controls rather than extra domains.

Standing Policy plus one Work Grant covers routine in-scope work. Aggregate Scope expansion once per change set and critical external actions once per delivery.
