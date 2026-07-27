# Adopt an existing project

1. Discover Python, Node, workspace-declared monorepo units, `AGENTS.md`, `.harness/`, manifest commands, referenced scripts, and GitHub Actions without writing.
2. Record every fact source and identify protected workflow triggers.
3. Build a Plan that:
   - creates `AGENTS.md` only when absent;
   - updates it with a preservation merge when present;
   - creates or updates `.harness/`;
   - lists existing workflows under `preserve`.
4. Stop on `PROTECTED_TRIGGER_UNCONTROLLED`; do not report Adopt complete.
5. Record MCP, Make, Gradle, Maven, Fastlane, and unclassified scripts as source-backed gaps; do not invent registrations.
6. Apply only after the user confirms the digest and write scope.
7. Validate, then report preserved paths and Evidence.

Example: an existing `.github/workflows/ci.yml` stays unchanged while each discovered job becomes a GitHub Actions Task whose `source` names the Workflow and job.
