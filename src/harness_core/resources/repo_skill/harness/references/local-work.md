# Local work

Keep work inside the local workspace and the requested scope.

1. Treat private branches, staged changes, unstaged changes, and untracked files
   as local workspace state.
2. Preserve unrelated user changes.
   If the fix requires a path outside the requested scope, stop before editing
   it and explain the new path, why it is required, and any T0-T3 escalation.
3. Use the repository Action binding for Test or Build; do not invent a command.
   Execute a local binding by its exact `action_id` through `run-action`, at or
   above the Action Graph's validation floor.
4. Select the lowest sufficient validation:
   - T0 Inspect: documentation, comments, or inert configuration.
   - T1 Nearest: one function, component, or narrow defect.
   - T2 Component: a public interface, shared module, Schema, or cross-file behavior.
   - T3 Full: core framework, dependency lock, security, CI/CD, or controlled delivery.
5. Escalate only from impact facts. Do not run T3 merely because it is safer.
6. Report the changed scope and human-readable validation result.

Example: after editing one parser function, run its nearest unit test. After
changing a public JSON Schema, run the component contract tests.

For a lasting Project policy change, use `policy-plan` first. Apply only the
unchanged plan digest with `policy-apply`; the atomic publication must refresh
the Projection. End an exact Task Decision with `decision-end` when its task
or action is finished.
