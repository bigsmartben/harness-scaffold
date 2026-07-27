# GitHub platform gates

Use GitHub as the authority for formal CI/CD permissions and delivery Evidence.

- Keep default `GITHUB_TOKEN` permissions read-only.
- Do not expose Push, Merge, Publish, Release, or Deploy credentials to Agent / Skill.
- Use `workflow_dispatch` or a traceable `workflow_call` for Harness requests.
- Require Branch Protection and Required Checks before Merge.
- Require a Protected Environment with reviewers before Publish or Deploy.
- Prefer short-lived OIDC identity inside the protected Job; do not place cloud credentials in Registry entries.
- Treat local execution as diagnostic only.

Collect platform facts from GitHub settings or API responses. Configuration files alone do not prove that branch or environment protection is active.

Formal Evidence must include Workflow, Run ID, commit SHA, current confirmation, approval status, protected environment when applicable, and artifact digest for Publish, Release, or Deploy.

Use the Adapter Protocol in this order: `prepare → dispatch → poll → normalize`. Keep production credentials outside the Skill and Registry. Use a local Fake Adapter for repository acceptance; do not treat it as live GitHub authority.

Use `scripts/validate_platform.py FACTS --required-check CHECK --protected-environment ENVIRONMENT` to validate a captured fact set. A `ready` result proves only that the supplied facts satisfy the contract; the fact source must still be recorded as GitHub settings or API Evidence before P4 can be marked Available.
