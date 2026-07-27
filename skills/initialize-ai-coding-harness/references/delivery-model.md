# Delivery model

Map only manifest-declared commands, explicitly referenced repository scripts, and existing Workflow jobs into `tasks.yaml`; do not rewrite their implementation.

- Use Local for registered project commands.
- Use GitHub Actions only for an existing referenced workflow or a separately selected Bootstrap backend.
- Use `git-remote` only for an exact confirmed non-force Push to `refs/heads/*`; it cannot Merge, Publish, Release, or Deploy.
- Map changed paths to the lowest sufficient validation level in `impact.yaml`.
- Classify CI/CD actions by semantics, not by Shell, CLI, MCP, or API channel.
- Require complete Task Evidence and a current confirmation before Merge.
- Keep Push, Merge, Publish, Release, and Deploy critical and separately confirmed. A Push confirmation binds the remote, full ref, and exact commit.

The Registry indexes ordinary tools and does not authorize or proxy them. External `push`, `pull_request`, `schedule`, or webhook events must retain the configured automation gate. Report uncontrolled protected triggers; do not claim to control ordinary Shell, MCP, network, or file writes.

## Work and Verify

Validate every received runtime Artifact against `runtime.schema.json` before using its digest or fields. A digest-correct but incomplete Artifact returns `EVIDENCE_BINDING_MISMATCH` and `HANDOFF_REQUIRED` with zero Adapter calls.

Compare the Change Manifest with actual changed paths. Resolve every path through `impact.yaml`; unmatched paths return `IMPACT_UNRESOLVED`. Agent recommendations never determine the final set.

Choose the maximum matched level in this order:

`inspect → affected → contract → integration → full`

After choosing the level, verify `supports_scope`. Contract needs a contract-capable Task; Integration and Full need a Task that covers that level. Return `IMPACT_UNRESOLVED` when coverage is insufficient. Never add Push, Merge, Publish, Release, or Deploy to Full.

Only a DM-004 fact can select `full`: Harness/CI execution semantics, broad build/Lockfile changes, public foundation/architecture, an explicit user request, or Merge Policy.

After selecting a validation level, apply the independent automation level:

- Run `routine` only when `auto_allowed: true`.
- For `expensive` Integration, E2E, Full CI, or large Build, create a request and wait for current confirmation.
- For `critical` Push, Merge, Publish, Release, or Deploy, require current confirmation and CI/CD platform gates.
- Treat missing or invalid automation metadata as confirmation-required; make zero backend calls.

Run an allowed registered command as an argument array with a timeout and declared working directory. Save the full log and return a summary containing the first useful error.

## Merge and Publish

Evaluate Merge or Publish in three states: readiness, dispatch, and finalize. Readiness makes no Adapter call and returns `ready-for-dispatch`; dispatch calls `prepare` then `dispatch`; finalization accepts `passed` only after `poll` and `normalize` yield complete Platform Evidence.

Merge requires passed Evidence for every required stage, bound to Grant, Change Manifest, actual Diff, final Selection, commit and Task Request. Work approval and passed checks do not replace current Merge confirmation. Required Checks and Branch Protection provide the authoritative result.

Publish requires a separate confirmation matching the canonical digest of version, artifact, target, commit and execution bindings. Protected Environment approval, platform Run metadata and the observed artifact digest are required for formal Evidence. A Local backend cannot complete a critical delivery Task.
