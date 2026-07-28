# Local work

Keep work inside the local workspace and the requested scope.

1. Treat private branches, staged changes, unstaged changes, and untracked files
   as local workspace state.
2. Preserve unrelated user changes.
3. Use the repository Action binding for Test or Build; do not invent a command.
4. Select the lowest sufficient validation:
   - T0 Inspect: documentation, comments, or inert configuration.
   - T1 Nearest: one function, component, or narrow defect.
   - T2 Component: a public interface, shared module, Schema, or cross-file behavior.
   - T3 Full: core framework, dependency lock, migration, security, CI/CD, or controlled delivery.
5. Escalate only from impact facts. Do not run T3 merely because it is safer.
6. Report the changed scope and human-readable validation result.

Example: after editing one parser function, run its nearest unit test. After
changing a public JSON Schema, run the component contract tests.

