# Repository projection

Treat entrypoint publication and repository projection as two exact phases.

1. Confirm `inspect` reports `entrypoint-ready`, or reports an active but stale
   projection that the user asked to refresh.
2. Build a zero-write `projection-plan`.
3. Explain the repository model and its path-backed reasons, the five managed
   projection files, preserved paths, available actions, capability gaps,
   sixteen-cell coverage, and blockers.
4. Apply only the unchanged plan digest after the task decision is clear.
5. If any source changes after planning, stop on
   `INITIALIZATION_PLAN_STALE`; do not silently rescan and continue.
6. A blocked plan writes zero files. In particular,
   `TOOL_BINDING_AMBIGUOUS` must name every conflicting source.
7. Rebuild without source or policy changes must produce no writes and the same
   projection ID.

After apply, run `inspect` again. Report a human-readable conclusion, current
repository and branch, source-backed reasons, changed and preserved paths,
validation result, capability gaps, blockers, and next step. Do not use a
digest or exit code as the only conclusion.
