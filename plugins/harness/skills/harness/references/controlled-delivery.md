# Controlled delivery

Treat Push, Pull Request, Merge, Publish, Release, and Deploy as separate
controlled actions.

1. Resolve one exact action and bind its target plus every applicable source
   ref, commit, artifact, and provider field.
2. Require a fresh task decision for that exact action.
3. Keep Commit authorization separate from every remote action.
4. Respect Codex, operating-system, provider, branch-protection, required-check,
   and environment-approval boundaries.
5. Execute only the registered adapter and validate platform evidence.
6. Stop on controlled or unclassified branches when the configured gate is
   missing.

Do not combine independent delivery actions into one open-ended authorization.
