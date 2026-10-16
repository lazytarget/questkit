---
id: QST-nij1y
title: Due-derived computed fields overdue and due_in plus a due view
description: Computed overdue (bool) and due_in (days) from due, plus a views.due, so dated quests surface without hand-written date comparisons.
project: questkit
type: feature
status: done
priority: medium
tags:
  - questkit
  - query
  - computed-fields
created: 2026-08-22
status_changed: 2026-08-24
modified: 2026-10-16
agentic:
aliases:
  - QST-nij1y
blocked_by: []
component:
effort: xs
milestone: 0.4.0
related_adrs:
---

## Spec

Two computed fields from `due:`: `overdue` (bool — due date passed and
status non-terminal) and `due_in` (int, days until due; negative when
past). ISO strings already compare correctly, so this is cheap. Add a
`views.due` to the core views (`where: ["due:exists"], sort:
"due_in:asc"` or similar), reachable via `quest list --view due`.
Reserved-name rule extended to `overdue`/`due_in`.

Might be what makes `due:` actually get used. Also the data source for a
future due-notification surface (MOB-3, deferred).

## Acceptance Criteria

- [ ] `overdue`/`due_in` computed, honoring terminal statuses and archived
- [ ] `views.due` ships in the core views
- [ ] Reserved-name rule covers both new names
- [ ] Tests + docs

## Log

- 2026-08-22: captured from R&D catalog SCH-3, accepted for 0.4.0
- 2026-08-24: Implemented for questkit v4 (milestone 0.4.0), TDD, full suite green.

