---
id: QST-5brm7
title: Unique custom-field constraint enforced by quest validate
description: A schema field may declare unique true; quest validate errors when two quests in the same log share its non-null value.
project: questkit
type: feature
status: done
priority: low
tags:
  - questkit
  - schema
  - validation
created: 2026-08-22
status_changed: 2026-08-24
modified: 2026-08-24
agentic:
aliases:
  - QST-5brm7
blocked_by: []
component:
effort: xs
milestone: 0.4.0
related_adrs:
---

## Spec

`schema.fields.<name>.unique: true` — `quest validate` collects the
field's values across the log and hard-errors on a duplicate, naming both
files. Null/absent values are exempt (nothing to collide). Log-scoped,
like every other validation rule — no cross-log uniqueness concept.

Belongs in the CLI validate loop (needs the whole log in view), NOT in
`schema.validate_quest()` — the per-file hook can't see siblings, same
split as cross-reference resolution.

## Acceptance Criteria

- [ ] `unique: true` parsed and surfaced by `quest schema`
- [ ] Duplicate non-null values are a validate error naming both files
- [ ] Null values exempt; hook behavior unchanged
- [ ] Tests + docs (§8 config reference)

## Log

- 2026-08-22: captured from R&D catalog SCH-5, accepted for 0.4.0
- 2026-08-24: Implemented for questkit v4 (milestone 0.4.0), TDD, full suite green.
