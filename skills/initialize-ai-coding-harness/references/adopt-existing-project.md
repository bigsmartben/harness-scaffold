# Adopt an existing project

1. Discover Runtime, package scripts, MCP configuration, `AGENTS.md`, `.harness/`, and workflows without writing.
2. Record every fact source and identify protected workflow triggers.
3. Build a Plan that:
   - creates `AGENTS.md` only when absent;
   - updates it with a preservation merge when present;
   - creates or updates `.harness/`;
   - lists existing workflows under `preserve`.
4. Stop on `PROTECTED_TRIGGER_UNCONTROLLED`; do not report Adopt complete.
5. Apply only after the user confirms the digest and write scope.
6. Validate, then report preserved paths and Evidence.

Example: an existing `.github/workflows/ci.yml` stays unchanged while `tasks.yaml` records its source.

