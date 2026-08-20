---
id: QST-lcsza
title: Archive a whole quest log instead of individual quests
description: Let a finished project's log be marked archived in its own config, so its quests drop out of sweeps and stale nags without any file ever moving.
created: 2026-08-19
status_changed: 2026-08-19
modified: 2026-08-20
type: feature
tier: brief
status: todo
priority: medium
effort: s
project: questkit
tags:
  - questkit
  - cli
  - multi-log
blocked_by:
  - QST-3ehhu
aliases:
  - QST-lcsza
---

## Description

`02-projects/peter/2026-career-transition` is a **time-boxed** project. When it
ends, its 13 quests stay in every `-A` sweep forever — and the ones still `todo`
will be nagged about by `quest stale` ([[QST-37n0t--built-in-views-next-stale-blocked-and-quest-deps]]) permanently, with no
action that can ever silence them. Scrapping them would be a lie (they were not
abandoned on their merits), and completing them would be a bigger one.

That is the concrete failure, and it is the whole argument for shipping this now
rather than deferring: **a dead log poisons the loop-closure views**, which are
the point of v3.

The granularity is the key insight. The thing that ends is a **project**, not a
quest. Nobody archives 13 quests one at a time; they finish a job and want the
whole log to stop talking.

## Spec

### Scope

**In:** `archived: true` in a log's `.questkit.yaml`, its effect on discovery,
and `quest archive` / `quest unarchive` as the commands that set it.
**Out:** per-quest archival, moving files, and any `active/`/`archive/`
subdirectory — all three are forbidden by [[QST-whm2e--questkit-design-blueprint-for-file-based-quest-tracking]]'s "no
`active/`/`archive/` subdirectories, ever", and that decision still holds.

### Approach

```yaml
# 02-projects/peter/2026-career-transition/quests/.questkit.yaml
version: 1
project: career-transition
archived: true
```

**Archival affects listing, never id resolution.** That split is the whole
design:

| Operation | Archived log |
|-----------|--------------|
| `quest list` / views / `-A` sweeps | **excluded** unless `--include-archived` |
| `quest stale` / `next` / `blocked` | **excluded** — the point of the feature |
| `quest show` / `brief` / `deps` by id | **found**, with a note that its log is archived |
| `blocked_by` reference resolution ([[QST-yiep7--qualified-cross-log-references-in-blocked-by]]) | **resolves** |
| `quest set` / `done` by id | **found**, with a warning |
| `quest new --in <archived>` | **error** — reopen it first |

If archival hid ids, every cross-log reference into a finished project would
start failing validation the day it was archived, and `quest deps` would lose
half its graph. That is a worse problem than the one being solved.

`quest logs` ([[QST-3ehhu--quest-logs-inventory-every-quest-log-under-a-root]]) lists archived logs with an
`ARCHIVED` marker and excludes their counts from the footer totals, so the
inventory stays honest about what it is and is not counting.

`quest archive [--in LOG]` / `quest unarchive [--in LOG]` write the key. Nothing
about a quest file changes — no field, no move, no rename, no mtime.

### Alternatives

| Option | Verdict | Reason |
|--------|---------|--------|
| `archived: true` on the log config | ✅ Chosen | Matches the real granularity (a project ends), touches zero quest files, breaks zero links |
| `quest archive <id>` moving files to `quests/archive/` | ❌ | Explicitly forbidden by v1; a move breaks the Obsidian link graph this system exists to build |
| Per-quest `archived: true` field | ❌ | 13 file rewrites for one project ending, and a second axis that means almost the same thing as `status` |
| Move the log into `06-archive/` | ❌ | `06-archive/` is an immutable data vault, a different Syncthing folder, and the log lives inside a git repo |
| Do nothing — `--where status=completed` already hides them | ❌ | True for completed quests, false for the ones left `todo`, which are exactly the ones `stale` will nag about forever |

### Snippets

```bash
quest archive --in career-transition
quest logs                       # career-transition   13   9  manual  ARCHIVED
quest stale -A                   # career-transition no longer appears
quest show QST-xxxxx             # still works, prints: log 'career-transition' is archived
quest list -A --include-archived # everything, including it
```

## Acceptance Criteria

- [ ] `archived: true` in a log's config excludes it from `-A` sweeps and every view
- [ ] `--include-archived` brings it back
- [ ] `quest show` / `brief` / `deps` still resolve an id inside an archived log, with a note
- [ ] A `blocked_by` reference into an archived log still resolves and does not error
- [ ] `quest set` / `done` on an archived log's quest warns but succeeds
- [ ] `quest new --in <archived log>` errors, naming `quest unarchive`
- [ ] `quest logs` marks archived logs and excludes them from the footer totals
- [ ] `quest archive` / `quest unarchive` are idempotent
- [ ] No quest file is read, written, moved or renamed by either command

## Log

- 2026-08-19: captured after grilling the archive question. Log-level rather than quest-level, because the thing that ends is a project.
