# Delivery Lifecycle

The scaffold owns one editable source tree for this Skill. Initialization
publishes it to `.agents/skills/repo-documentation-maker/` with a generated
`.scaffold-manifest.json`.

## Bootstrap and Adopt

- Publish every source file and the generated manifest.
- Refuse to take ownership of an existing same-name Skill when the manifest is
  absent or invalid.
- Keep unrelated repository files unchanged.

## Update

- Compare each current file with the digest recorded by the previous manifest.
- Update a file only when it still matches the previous managed digest.
- Preserve changed managed files and additional user files.
- List preserved paths in `preserved_customizations`.
- Repeating Update with identical source and repository state must write
  nothing.
- Reject a manifest with unsafe paths or a newer incompatible major version.

## Removal

Removal requires an explicit future scaffold release decision. The removal
plan may delete only files that still match their recorded managed digests.
Customized and additional files must be preserved and reported for human
handoff. Never remove the whole Skill directory recursively.
