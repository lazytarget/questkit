---
id: QST-bo3xs
title: Checklist-progress computed fields criteria_done and criteria_total
description: Computed criteria_done/criteria_total parsed from the Acceptance Criteria checklist, filterable and sortable like blocked/idle.
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
  - QST-bo3xs
blocked_by: []
component:
effort: s
milestone: 0.4.0
related_adrs:
---

## Spec

Two computed fields derived from the `## Acceptance Criteria` checklist:
`criteria_total` (all `- [ ]`/`- [x]` items) and `criteria_done` (checked
ones). Same machinery as `blocked`/`idle`: read-only, usable in
`--where`/`--select`/`--sort`, reserved-name rule extended to both names.

Bodies are parsed lazily — only when a criteria field is actually
referenced by the query (mirrors the planned `body~` handling, QRY-2).

A hygiene query this unlocks (from review feedback): quests marked done
with unchecked criteria —

    quest list --where "status=done" --where "criteria_done<criteria_total" --where "criteria_total>0"

## Acceptance Criteria

- [ ] `criteria_total`/`criteria_done` computed from `## Acceptance Criteria`
- [ ] Work in `--where`/`--select`/`--sort`; rejected by `quest set`
- [ ] Reserved-name rule covers both new names
- [ ] Body parsed only when a criteria field is referenced
- [ ] Tests + docs (README, docs/questkit.md §6)

## Log

- 2026-08-22: captured from R&D catalog SCH-2, accepted for 0.4.0
- 2026-08-24: Implemented for questkit v4 (milestone 0.4.0), TDD, full suite green.

