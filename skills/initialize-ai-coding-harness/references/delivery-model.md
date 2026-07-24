# Delivery model

Map existing scripts and workflows into `tasks.yaml`; do not rewrite their implementation by default.

- Use Local for registered project commands.
- Use GitHub Actions only for an existing referenced workflow or a separately selected Bootstrap backend.
- Map changed paths to the lowest sufficient validation level in `impact.yaml`.
- Classify CI/CD actions by semantics, not by Shell, CLI, MCP, or API channel.
- Require complete Task Evidence and a current confirmation before Merge.
- Keep Push, Merge, Publish, Release, and Deploy critical and separately confirmed.

The Registry indexes ordinary tools and does not authorize or proxy them. External `push`, `pull_request`, `schedule`, or webhook events must retain the configured automation gate. Report uncontrolled protected triggers; do not claim to control ordinary Shell, MCP, network, or file writes.

## Work and Verify

Compare the Change Manifest with actual changed paths. Resolve every path through `impact.yaml`; unmatched paths return `IMPACT_UNRESOLVED`. Agent recommendations never determine the final set.

Choose the maximum matched level in this order:

`inspect → affected → contract → integration → full`

Only a DM-004 fact can select `full`: Harness/CI execution semantics, broad build/Lockfile changes, public foundation/architecture, an explicit user request, or Merge Policy.

After selecting a validation level, apply the independent automation level:

- Run `routine` only when `auto_allowed: true`.
- For `expensive` Integration, E2E, Full CI, or large Build, create a request and wait for current confirmation.
- For `critical` Push, Merge, Publish, Release, or Deploy, require current confirmation and CI/CD platform gates.
- Treat missing or invalid automation metadata as confirmation-required; make zero backend calls.

Run an allowed registered command as an argument array with a timeout and declared working directory. Save the full log and return a summary containing the first useful error.

## Merge and Publish

Merge requires passed Evidence for every required stage, bound to both the Change Manifest and final selection. Then create a critical Merge Request. Work approval and passed checks do not replace the current Merge confirmation. Required Checks and Branch Protection provide the authoritative result.

Publish requires a separate confirmation matching the canonical digest of version, artifact, and target. Protected Environment approval and platform Run metadata are also required for formal Evidence. Without them, do not invoke the backend or report success.
