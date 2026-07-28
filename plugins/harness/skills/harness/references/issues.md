# Issue planning and writes

Use one Issue Plan for local and remote providers.

1. Resolve the configured provider and exact destination.
2. Bind title, body, labels, assignee, repository, and provider into the
   plan digest.
3. For a local provider, write only under the configured issue directory.
4. For a remote provider, obtain a task decision bound to the exact target
   before calling the provider.
5. Validate the returned provider ID or URL.
6. Never interpret an available connector as consent.
7. Never fall back from a failed remote write to a local issue.

Example: a decision to create `owner/repo#new` does not authorize another
repository, a different title/body, or a second issue.
