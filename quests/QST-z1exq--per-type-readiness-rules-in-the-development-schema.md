---
id: QST-z1exq
title: Per-type readiness rules in the development schema
description: Schema authoring, not code — when-guarded readiness rules per type, e.g. type=bug requires a Repro section before the brief reads READY.
project: questkit
type: task
status: done
priority: medium
tags:
  - questkit
  - schema
  - agentic
created: 2026-08-22
status_changed: 2026-08-24
modified: 2026-08-24
agentic:
aliases:
  - QST-z1exq
blocked_by: []
component:
effort: xs
milestone: 0.4.0
related_adrs:
---

## Spec

The `when:` mechanism shipped in v0.3 (`readiness:` rules reuse the
`--where` grammar). This quest is authoring, mostly in the Realm's
`99-system/questkit/schemas/development.yaml`:

- `when: "type=bug"` → `require: { sections: ["## Repro"] }` —
  "no repro steps — not implementation-ready"
- review whether other types earn one (e.g. `epic` requiring a Scope
  section) — add only what the corpus supports

Plus a documented example in docs/questkit.md §13 so the pattern is
discoverable for other schemas.

## Acceptance Criteria

- [ ] `development` schema declares at least the bug/Repro rule
- [ ] `quest brief` on a repro-less bug collapses with that message
- [ ] Docs show per-type rules as a worked example

## Log

- 2026-08-22: captured from R&D catalog SCH-4, accepted for 0.4.0
- 2026-08-24: Implemented for questkit v4 (milestone 0.4.0), TDD, full suite green.
