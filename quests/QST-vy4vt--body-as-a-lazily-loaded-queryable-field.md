---
id: QST-vy4vt
title: Body as a lazily-loaded queryable field
description: body becomes a lazily-loaded queryable field, so full-text search composes with --where, --any and every view — no separate search command.
project: questkit
type: feature
status: todo
priority: medium
tags:
  - questkit
  - query
  - cli
created: 2026-08-22
modified: 2026-08-22
agentic:
aliases:
  - QST-vy4vt
blocked_by: []
component:
effort: s
milestone: 0.4.0
related_adrs:
---

## Spec

`body` becomes an ordinary field in the row model, loaded lazily — the
file's body is read only when a query expression references it.
Grep-with-identity inside the existing engine, no new command:

    quest list --where "body~syncthing"
    quest list --any "body~## Repro;type=bug"    # composes with any-groups
    quest stale --where "body~TODO"               # views compose too

- `~` is case-insensitive substring; `body:exists` trivially true;
  other operators legal but documented as not useful.
- Excluded from `--select` for table/csv (unbounded cell); decide
  json/prompt behavior during implementation.
- Same lazy-parse mechanism as the criteria fields (QST-bo3xs).

## Acceptance Criteria

- [ ] `body~` works in --where and --any, across -A sweeps and views
- [ ] Body read only when referenced — no regression on plain list
- [ ] --select body decision documented and tested
- [ ] Tests + docs

## Log

- 2026-08-22: captured from R&D catalog QRY-2 (revised — folded into list, not a separate command), accepted for 0.4.0
