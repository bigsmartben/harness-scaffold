# Document Quality Checklist

## Contract

- [ ] The document answers its Contract question for its intended audience.
- [ ] Required sections are present or have an explicit fact gap.
- [ ] Forbidden topics are absent or replaced by a link to their owner.
- [ ] Product, technology, and architecture decisions come from repository
      authority rather than inference.

## Consistency

- [ ] Names, versions, commands, paths, and outputs match current repository
      facts.
- [ ] The document does not contradict another authoritative document.
- [ ] Repeated facts have one clear owner and other documents link to it.
- [ ] Existing valid custom content and stable anchors are preserved.

## Links and commands

- [ ] Every required relative link resolves with exact path casing.
- [ ] Every documented first-success or validation command is source-backed.
- [ ] Expected command results are observable and reproducible.
- [ ] Secrets, tokens, personal paths, and transient evidence are absent.

## Quickstart

- [ ] Prerequisites are minimal and ordered.
- [ ] A new user can reach one success without reading maintainer material.
- [ ] A scaffold Quickstart addresses the template consumer.
- [ ] The next step links to deeper documentation.

## Result

Return `DOCUMENT_BOUNDARY_VIOLATION`, `DOCUMENT_LINK_INVALID`, or
`DOCUMENT_FACTS_MISSING` when a required check cannot pass. Otherwise report
the checks performed and any optional fact gaps.
