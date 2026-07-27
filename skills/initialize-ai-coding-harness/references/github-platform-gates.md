# GitHub platform gates

Local configuration and Agent summaries do not prove GitHub authority. For an external Action, bind Platform Evidence to the exact repository, Workflow or ref, commit, target, approval state, required checks and artifact digest where applicable.

Push, PR, Merge, Publish, Release and Deploy remain distinct Actions even when grouped in one confirmation package. Never infer a later Action from an earlier successful one. If current platform Evidence is unavailable or mismatched, return `GOVERNANCE_EVIDENCE_INCOMPLETE` and `HANDOFF_REQUIRED`.
