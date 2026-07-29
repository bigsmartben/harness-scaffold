---
name: repo-documentation-maker
description: Create, update, refactor, or validate repository documentation from verified repository facts. Use when Codex needs to work on README.md, QUICKSTART.md, DEVELOPMENT.md, MAINTAINER.md, HARNESS.md, UC.md, TECH-SELECTION.md, or ARCHITECTURE.md while preserving document boundaries, existing valid content, links, and explicit fact gaps.
---

# Repository Documentation Maker

Create software-engineering documentation from repository evidence. Do not
invent product decisions, business rules, architecture decisions, commands, or
ownership facts.

## Route

1. Classify the requested operation as Create, Update, Refactor, or Validate.
2. Read [references/repository-document-facts.md](references/repository-document-facts.md)
   and collect the minimum facts needed for the target document.
3. Load the target Contract. For Create, also load its Template. For Update or
   Refactor, treat the Template as a structural reference and preserve valid
   existing content.
4. Load the matching workflow:
   - Create: [workflows/create.md](workflows/create.md)
   - Update: [workflows/update.md](workflows/update.md)
   - Refactor: [workflows/refactor.md](workflows/refactor.md)
5. Apply the change with normal repository editing tools.
6. Run [checklists/document-quality.md](checklists/document-quality.md).
7. Report changed documents, validated links or commands, and unresolved facts.

For reproducible Create and Update scenarios, read
[references/examples.md](references/examples.md). For Skill delivery, upgrade,
compatibility, and removal behavior, read
[references/delivery-lifecycle.md](references/delivery-lifecycle.md).

## Document map

| Document | Contract | Template |
|---|---|---|
| `README.md` | `contracts/README.contract.md` | `templates/README.template.md` |
| `QUICKSTART.md` | `contracts/QUICKSTART.contract.md` | `templates/QUICKSTART.template.md` |
| `DEVELOPMENT.md` | `contracts/DEVELOPMENT.contract.md` | `templates/DEVELOPMENT.template.md` |
| `MAINTAINER.md` | `contracts/MAINTAINER.contract.md` | `templates/MAINTAINER.template.md` |
| `HARNESS.md` | `contracts/HARNESS.contract.md` | `templates/HARNESS.template.md` |
| `UC.md` | `contracts/UC.contract.md` | `templates/UC.template.md` |
| `TECH-SELECTION.md` | `contracts/TECH-SELECTION.contract.md` | `templates/TECH-SELECTION.template.md` |
| `ARCHITECTURE.md` | `contracts/ARCHITECTURE.contract.md` | `templates/ARCHITECTURE.template.md` |

## Boundaries

- Read only local repository facts and this Skill's local resources.
- Keep each document within its Contract. Link to another document instead of
  duplicating that document's responsibility.
- Preserve useful prose, anchors, relative links, and user-specific sections
  unless the requested refactor explicitly replaces them.
- Use `TODO(fact): <missing fact>` for a non-blocking gap. Stop with
  `DOCUMENT_FACTS_MISSING` when the missing fact is required for a conclusion
  or executable instruction.
- Stop with `DOCUMENT_CONTRACT_MISSING` or `DOCUMENT_TEMPLATE_MISSING` when a
  required local Skill asset is unavailable.
- Stop with `DOCUMENT_BOUNDARY_VIOLATION` when the requested content belongs to
  another document and the user has not authorized that broader scope.
- Stop with `DOCUMENT_LINK_INVALID` when a required local link or documented
  command cannot be verified.

## Examples

- “Create a README for this library.” Route to Create, inspect package metadata,
  load the README Contract and Template, then verify every command shown.
- “Update QUICKSTART after the CLI changed.” Route to Update, preserve the
  existing first-success path, and replace only facts confirmed by code or tests.
- “Split our oversized README.” Route to Refactor; move contributor procedure
  to DEVELOPMENT and release ownership to MAINTAINER, leaving links in README.
- “Check our architecture document.” Route to Validate; do not make architecture
  decisions on the user's behalf.
