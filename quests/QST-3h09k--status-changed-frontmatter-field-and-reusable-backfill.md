---
id: QST-3h09k
title: status_changed frontmatter field and reusable backfill
description: Add a status_changed date written only on real status transitions, so staleness measures work progress instead of file churn.
project: questkit
type: feature
status: done
priority: high
tags:
  - questkit
  - schema
  - cli
created: 2026-08-19
status_changed: 2026-08-20
modified: 2026-08-20
agentic: afk
aliases:
  - QST-3h09k
blocked_by:
  - QST-mjuau
  - QST-lc3co
effort: s
milestone: 0.3.0
tier: brief
---

## Description

`modified` cannot measure staleness. It is bumped by the `quest-bump-modified`
pre-commit hook on every commit touching a quest, and by `quest format` on every
run (see [[QST-mjuau--quest-save-writes-only-when-the-rendered-content-changes]]).

The concrete failure: the day `quest format --fill-defaults` ([[QST-j68u5--schema-engine-field-order-defaults-macros-typed-fields-strict-writes]]) runs across
the corpus to backfill newly-required fields, **every quest gets a fresh
`modified`** and any staleness view returns nothing for N days. The normalization
pass launders the entire backlog into looking freshly worked. That is not a
hypothetical — it is a scheduled step of v3.

`status_changed` measures work progress instead of file churn. This must land
**before** `--fill-defaults` or the signal is lost permanently.

## Spec

### Scope

**In:** the field, its write path, its position in frontmatter, and a reusable
backfill.
**Out:** `completed_at` (see Alternatives), and the `idle` computed field that
consumes it ([[QST-b9lqo--computed-fields-and-comparison-operators-for-where]]).

### Approach

- New **optional date** field, positioned between `created` and `modified`.
- Written by `quest set status=...` and `quest done`, **only when the new status
  differs from the old** — same comparison rule as [[QST-mjuau--quest-save-writes-only-when-the-rendered-content-changes]]. Otherwise an agent
  re-asserting state launders the signal exactly as `--fill-defaults` would.
- Null-safe: consumers fall back to `created`.
- Backfill seeds from `created`, not `modified` — `modified` is already polluted
  by the bump hook and every past `quest set`. This is wrong for the 15 completed
  quests (it will claim they have not moved since creation) and it does not
  matter, because staleness only ever looks at non-terminal statuses. Say so in
  the migration note rather than building git archaeology for a field nobody
  queries on finished work.
- The backfill itself now lives in [[QST-lc3co--quest-migrate-frontmatter-aware-corpus-migrations]] —
  v3 accumulated three corpus migrations rather than one (`status_changed`,
  `completed`→`done`, `agentic` demotion), so the tool is its own quest. This
  quest owns the **field and its write path**; that one owns **moving 129 files**.

### Alternatives

| Option | Verdict | Reason |
|--------|---------|--------|
| `status_changed` | ✅ Chosen | No git dependency, measures the thing staleness actually means |
| Derive from git history | ❌ | Three logs are `git: manual` inside code repos where quest and code commits interleave; makes a read-only command shell out per file |
| Reuse `modified` | ❌ | The bug being fixed |
| Also ship `completed_at` | ❌ Deferred | Derivable from git for `git: auto` logs, uncertain elsewhere, and no v3 command needs it |

## Acceptance Criteria

- [x] `quest set <id> status=in-progress` sets `status_changed` to today
- [x] Re-setting the same status changes neither `status_changed` nor `modified`
- [x] `quest done` sets `status_changed`
- [x] The backfill seeds every quest lacking the field from `created`, and is idempotent
- [x] The backfill runs via `quest migrate --backfill status_changed=created` ([[QST-lc3co--quest-migrate-frontmatter-aware-corpus-migrations]])
- [x] Field order places `status_changed` between `created` and `modified`
- [x] A quest with no `status_changed` is treated as `created` by every consumer
- [x] `quest schema quest status_changed` describes it

## Log

- 2026-08-21: implemented (batch B0). Two things the spec did not anticipate, both found by running the real corpus rather than by tests. First, the ordered-insertion rule was written in `set_cmd`, so `quest migrate` — the command that introduces this field to 122 files — appended it after `blocked_by` instead. Moved into `Quest.set()`, so every writer shares one rule. Second, backfilling from `created` assigned the source field's own object, which makes it appear twice in one document and ruamel then emits a YAML anchor/alias pair: the dry-run produced `status_changed: *id001`. That parses back correctly and is useless to Obsidian's Properties panel, to `grep`, and to a human — so the value is deep-copied. Also settled that `quest new` never writes the field: a new quest is *born* at its status rather than transitioning to it, so `created` is the honest answer and the fallback already returns it.
- 2026-08-21: added [[QST-lc3co--quest-migrate-frontmatter-aware-corpus-migrations]] to `blocked_by`. The backfill acceptance criterion names `quest migrate` outright, so the dependency was real but undeclared — and `migrate` sat at build-order #15 while this quest sat at #2. It now ships at #2 and this one at #3.
- 2026-08-19: captured. Sequenced deliberately ahead of `--fill-defaults`.
