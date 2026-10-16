---
id: QST-eszpe
title: Quest stats distributions flow and backlog age
project: questkit
type: feature
status: draft
priority: medium
tags:
  - questkit
  - reporting
  - cli
created: 2026-08-22
modified: 2026-08-22
agentic:
aliases:
  - QST-eszpe
blocked_by: []
component:
milestone: 0.5.0
related_adrs:
---

## Notes (draft)

`quest stats [--in|-A]`: a single stats overview per log or across logs —
think Claude Code's `/stats` screen, terminal-rendered:

- distributions: status / type / priority (vocabulary-ordered)
- flow: created vs closed per week, derived from `created` +
  `status_changed`
- median age of open quests; draft-backlog age
- text (aligned/sparkline-ish) + `--format json`

The "declining engagement" signal that killed Trello, made visible early.
Likely builds on the `--group-by` primitive (QRY-3, still in planning).

From R&D catalog REP-1. Draft by request, milestone 0.5.0.

## Log

- 2026-08-22: captured from R&D catalog REP-1 (draft, milestone 0.5.0)
