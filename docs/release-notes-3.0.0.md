# Harness 3.0.0

Harness 3.0.0 replaces the previous control plane with a fixed local
specification-governance model:

- Audience × Responsibility × Governance Domain always produces 16 Cells.
- Four explicit governance domains contain the only user-defined rule
  instances.
- One deterministic `model.lock.json` replaces the former multi-artifact
  projection.
- The CLI contains only `init`, `project`, `validate`, and `inspect`.
- Rules are always local `guidance`; they cannot execute actions, grant
  permission, or invoke a Provider.

## Breaking change

There is no v1/v2 migration tool, dual reader, compatibility wrapper,
deprecation period, alias, default completion, or fallback. Existing consumers
must back up anything they need, manually remove the old Harness control-plane
files, and run `sdd-harness init` again.
