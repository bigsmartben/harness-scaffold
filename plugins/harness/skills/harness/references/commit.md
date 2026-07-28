# Commit checkpoint

Enter this route only when the user explicitly requests `git commit` or an
equivalent commit action.

1. Ask once whether to analyze every uncommitted workspace change.
2. If the user declines, confirm the commit paths and run only the minimum
   safety check.
3. If the user accepts, run the read-only workspace impact analysis over
   staged, unstaged, and untracked paths.
4. Keep Workspace Impact Scope separate from Commit Scope.
5. Present Workspace Impact Scope, Commit Scope, message, partial paths, and
   blocker codes from the exact commit plan.
6. Commit only confirmed paths through the Harness temporary-index adapter.
7. Preserve excluded paths and their original staged state.
8. Stop when a selected file is partially staged and whole-file semantics
   cannot preserve the user's hunks.

A commit decision authorizes only that commit. It does not authorize Push, PR,
Merge, Release, or Deploy.
