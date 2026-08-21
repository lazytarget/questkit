---
id: QST-8hjjk
title: Allow for --select and --distinct when listing quests
description: Add field projection, de-duplication and a row count to quest list, so aggregate questions are answerable without post-processing in jq.
project: questkit
type: feature
status: done
priority: medium
tags:
  - questkit
  - cli
  - dx
created: 2026-08-16
status_changed: 2026-08-20
modified: 2026-08-20
agentic: afk
aliases:
  - QST-8hjjk
blocked_by: []
effort: s
milestone: 0.3.0
tier: brief
---

## Description

`quest list` can filter and sort but cannot **project**. Answering "which projects
have open quests?" means dumping JSON and post-processing in `jq`, which is a
poor fit for the one consumer that matters most — an agent reading the output, for
which every unused column is wasted tokens.

`--columns` exists but applies to table/csv only, which is the wrong contract:
projection is a query concept, not a rendering one.

## Spec

### Scope

**In:** `--select`, `--distinct`, `--count`, and retiring `--columns`.
**Out:** computed fields ([[QST-b9lqo--computed-fields-and-comparison-operators-for-where]]), though `--select` must work with them once
they exist.

### Approach

1. **`--select a,b,c`** restricts output to the named fields, **in the given
   order**, and applies to **every** `--format` — table, csv, json and prompt. This
   is a widened contract, not a rename of `--columns`.
2. **`--distinct`** collapses rows identical across the selected fields.
3. **`--count`** prints a bare integer to stdout. It honors `--where`, `--select`
   and `--distinct` and **ignores `--limit`/`--offset`** — "how many are there" and
   "show me the first ten" are different questions, and a `--count` that respects
   `--limit` can only ever return `min(n, limit)`.
4. **`--columns` is removed**, not aliased. Its 12 doc references are updated in
   the same commit.

Errors are explicit rather than silently permissive:

- `--select` naming an unknown field errors, listing the valid fields for that
  log's schema
- `--distinct` without `--select` errors rather than silently doing nothing

### Snippets

```bash
quest list -A --select project --distinct              # which projects have open quests
quest list -A --select id,title --format prompt        # minimal agent digest
quest list -A --where status=todo --count              # 86
quest list -A --select project,status --distinct --format csv
```

## Acceptance Criteria

- [x] `quest list -A --select project --distinct` prints one row per project
- [x] `--select` applies to table, csv, json and prompt
- [x] `--select` preserves the order given
- [x] `--select` with an unknown field errors, naming the valid fields
- [x] `--distinct` without `--select` errors rather than no-opping
- [x] `--count` honors `--where`/`--select`/`--distinct` and ignores `--limit`/`--offset`
- [x] `--count` prints a bare integer suitable for `$( )`
- [x] `--columns` is gone and its doc references are updated
- [x] `--select` works with computed fields once [[QST-b9lqo--computed-fields-and-comparison-operators-for-where]] lands

## Log

- 2026-08-21: implemented (batch B4). Rows are projected to the selected fields exactly once, up front in `run()` -- `_project(row, fields)` -- so `json` and `prompt` inherit `--select` for free rather than needing per-renderer branches; the old `--columns` only ever reached `table`/`csv`. `--distinct` collapses on the already-projected row's values (tuple-ifying any list field first, since `tags` is unhashable), preserving first-seen order. `--count` short-circuits before sort/limit/offset, matching the spec's "these are different questions" framing exactly. One test caught a real gap early: repeatable multi-log `--in` doesn't exist yet on `quest list` (it is `QST-iqwjm`'s job) -- `--in` twice silently keeps only the last value, since the flag isn't `action="append"`. Adjusted the multi-log `--distinct` test to use `--all` instead of chasing that quest's scope.
- 2026-08-16: captured
- 2026-08-19: groomed as part of [[QST-bmzl2--questkit-v3-loop-closure-multi-log-ux-and-agent-handoff]]. Added `--count` and the `--columns` retirement.
