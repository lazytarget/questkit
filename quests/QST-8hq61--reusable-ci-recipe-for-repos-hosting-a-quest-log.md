---
id: QST-8hq61
title: Reusable CI recipe for repos hosting a quest log
project: questkit
type: chore
status: draft
priority: low
tags:
  - questkit
  - ci
created: 2026-08-22
modified: 2026-08-22
agentic:
aliases:
  - QST-8hq61
blocked_by: []
component:
milestone: 0.9.0
related_adrs:
---

## Notes (draft)

A two-step pipeline for any repo hosting a quest log:
`quest validate && quest format --check` (both exist, both exit
correctly). Catches what pre-commit structurally cannot: edits
arriving via Syncthing/Obsidian from devices with no hooks installed,
or pushes from machines that never ran `pre-commit install`.

In the current topology the realm-01 timer already validates every
log on a schedule, so this adds little today — it becomes real when a
log lives in a repo with a second contributor or push-based
collaboration on Gitea. Needs questkit installable in the runner
(Gitea registry — QST-x4zw2).

From R&D catalog CI-2.

## Log

- 2026-08-22: captured from R&D catalog CI-2 (draft, milestone 0.9.0)
