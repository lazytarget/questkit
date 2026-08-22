---
id: QST-4dwpu
title: Weekly digest note written by the committer timer
project: questkit
type: feature
status: draft
priority: low
tags:
  - questkit
  - reporting
created: 2026-08-22
modified: 2026-08-22
agentic:
aliases:
  - QST-4dwpu
blocked_by: []
component:
milestone: 0.5.0
related_adrs:
---

## Notes (draft)

A weekly `_digest.md` per log (or one aggregated at the catch-all):
new / done / stale counts for the week, most-idle open quests. Derived
state like `_validation.md` — transported by Syncthing, excluded from
`tracked:`, phone-readable in Obsidian. Zero new infrastructure: the
realm-01 timer just runs one more command.

Open question for grooming: is this a questkit command
(`quest digest --out _digest.md`) with the timer as one caller — keeping
the Realm-specific part out of core — or purely a Realm-side script over
`quest list --format json`? Leaning command-with-caller, same shape as
`quest adopt` (MOB-1).

From R&D catalog REP-3. Draft by request, milestone 0.5.0.

## Log

- 2026-08-22: captured from R&D catalog REP-3 (draft, milestone 0.5.0)
