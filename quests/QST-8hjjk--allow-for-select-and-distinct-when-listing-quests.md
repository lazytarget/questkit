---
id: QST-8hjjk
title: "Allow for --select and --distinct when listing quests"
description: "Add field projection, de-duplication and a row count to quest list, so aggregate questions are answerable without post-processing in jq."
created: 2026-08-16
modified: 2026-08-19
type: feature
tier: brief
status: todo
priority: medium
effort: s
project: questkit
tags:
  - questkit
  - cli
  - dx
blocked_by: []
aliases:
  - QST-8hjjk
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

- [ ] `quest list -A --select project --distinct` prints one row per project
- [ ] `--select` applies to table, csv, json and prompt
- [ ] `--select` preserves the order given
- [ ] `--select` with an unknown field errors, naming the valid fields
- [ ] `--distinct` without `--select` errors rather than no-opping
- [ ] `--count` honors `--where`/`--select`/`--distinct` and ignores `--limit`/`--offset`
- [ ] `--count` prints a bare integer suitable for `$( )`
- [ ] `--columns` is gone and its doc references are updated
- [ ] `--select` works with computed fields once [[QST-b9lqo--computed-fields-and-comparison-operators-for-where]] lands

## Log

- 2026-08-16: captured
- 2026-08-19: groomed as part of [[QST-bmzl2--questkit-v3-loop-closure-multi-log-ux-and-agent-handoff]]. Added `--count` and the `--columns` retirement.
