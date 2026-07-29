# Reproducible Examples

## Create README

Repository facts:

```text
pyproject.toml
src/example/__init__.py
tests/test_smoke.py
```

The package metadata confirms the name, version, and supported Python version.
No license, audience, install command, or purpose is declared.

Expected operation:

1. Load `contracts/README.contract.md` and `templates/README.template.md`.
2. Create README with the confirmed identity and links that resolve.
3. Do not invent an install command.
4. Add `TODO(fact)` entries for purpose, audience, and license.

Expected checks:

- README Contract sections are present.
- Every relative link resolves.
- No command is documented without a source.
- Product, maintenance, and architecture details are absent.

## Update Quickstart

Initial facts:

```text
package.json#scripts.first-success = "tool run example"
QUICKSTART.md contains a local user note after the expected result.
```

Changed facts:

```text
package.json#scripts.first-success = "tool execute example"
The integration test asserts output "example complete".
```

Expected operation:

1. Load the existing QUICKSTART before its Contract and Template.
2. Replace only the first-success command and verified expected output.
3. Preserve the local user note, anchors, prerequisites, and unaffected links.
4. Run the Quickstart checklist.

Expected checks:

- The command matches the current package script.
- The expected output matches the integration test.
- The user note remains byte-for-byte unchanged.
- Repeating Update with the same facts produces no diff.
