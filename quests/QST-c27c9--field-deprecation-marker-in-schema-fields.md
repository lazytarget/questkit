---
id: QST-c27c9
title: Field deprecation marker in schema fields
project: questkit
type: feature
status: draft
priority: low
tags:
  - questkit
  - schema
created: 2026-08-22
modified: 2026-10-16
agentic:
aliases:
  - QST-c27c9
blocked_by: []
component:
milestone:
related_adrs:
---

## Notes (draft)

`deprecated: true` on a schema field: `quest validate` reports usage as a
note (never an error), `quest schema` marks the field deprecated, and
`quest new` stops null-initializing it. A migration path gentler than
deleting the declaration and having `strict: true` hard-error the corpus.

From R&D catalog SCH-6. Draft by request — groom when a real deprecation
happens; until then this is speculative.

## Log

- 2026-08-22: captured from R&D catalog SCH-6 (draft, no milestone)

