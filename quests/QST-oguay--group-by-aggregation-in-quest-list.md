---
id: QST-oguay
title: Group-by aggregation in quest list
description: Group-by turns list into vocabulary-ordered aggregate counts across one or two fields; supersedes and removes the unused --distinct.
project: questkit
type: feature
status: done
priority: medium
tags:
  - questkit
  - query
  - cli
created: 2026-08-22
status_changed: 2026-08-24
modified: 2026-10-16
agentic:
aliases:
  - QST-oguay
blocked_by: []
component:
effort: s
milestone: 0.4.0
related_adrs:
---

## Spec

`--group-by FIELD[,FIELD2]` switches `list` into aggregation: output
rows are the field value(s) plus a count, sorted by each field's
declared vocabulary order.

- table/csv: value column(s) + `count`; json:
  `[{"status": "todo", "count": 86}]`; prompt: clean error (an
  aggregate is not a quest digest).
- Implies counting. `--select`/`--distinct` alongside it is an error.
  `--where`/`--any` filter before grouping. Honors `-A`/`--in`/
  `--archived`.
- Two-level grouping is what the milestone burnup consumes (REL-3).
- Supersedes `--distinct` (`--select f --distinct` = `--group-by f`
  minus the count): **remove `--distinct` in this quest** — unused in
  practice, removal approved 2026-08-22.

## Acceptance Criteria

- [ ] --group-by with one and two fields, vocabulary-ordered
- [ ] table/json/csv shapes; prompt errors cleanly
- [ ] --distinct removed, docs updated
- [ ] Interactions with --where/--any/-A/--archived tested

## Log

- 2026-08-22: captured from R&D catalog QRY-3, accepted for 0.4.0
- 2026-08-24: Implemented for questkit v4 (milestone 0.4.0), TDD, full suite green.

