# Core model

Treat `.harness/governance/rules.json` as the structured governance SSOT and `projection.lock.json` as its repository binding.

```text
Snapshot → Facts → Action Graph → 2 × 6 Projection → Validate → Publish
Action Request → Resolve → G0–G5 → Runner → Postconditions → G6–G7 → Evidence
```

Audit is only a read-only view of `generate` or `enforce`. A changed governance input invalidates the projection and Work Grant. Missing or untrusted custom Agents fail closed; do not use a generic fallback.

Standing Policy plus one Work Grant covers routine in-scope work. Aggregate Scope expansion once per change set and critical external actions once per delivery.
