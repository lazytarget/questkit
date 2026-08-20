---
id: QST-iqwjm
title: "Multi-log query UX: --all-logs, repeatable --in and --root, per-log grouping, summary block"
description: "Make the scope of every query legible: rename --all, allow multiple logs and roots, group results per log, and print the filters in effect."
created: 2026-08-19
status_changed: 2026-08-19
modified: 2026-08-20
type: feature
tier: brief
status: todo
priority: high
effort: m
project: questkit
tags:
  - questkit
  - cli
  - dx
  - multi-log
blocked_by:
  - QST-fmk0p
aliases:
  - QST-iqwjm
agentic: afk
---

## Description

Selective Syncthing makes multiple logs mandatory — folder boundaries in this
vault are access-control lists, not a preference. But the current surface makes
the scope of a query hard to know and impossible to state:

- **`--all` reads as "all quests"** when it means "all logs". Nothing in the
  output distinguishes them.
- **Its scope is device-dependent.** `work-a` and `work-b` do not sync to the
  phone, so `quest list --all` reports a smaller world there than on the ProArt,
  and says nothing about it. A partial answer that does not announce itself is
  worse than a narrower one that does.
- **There is no way to query two logs.** "House contexts" is `family + home`;
  "code contexts" is `questkit + pensieve + realm-system`. Neither is one log and
  neither is every log.
- **The default status filter is invisible.** `quest list` silently injects
  `status=todo,in-progress,blocked` unless a `--where` mentions status, and the
  only override (`--where status:exists`) is undiscoverable.

## Spec

### Scope

**In:** flag renames, repeatable `--in`/`--root`, log-set resolution, per-log
grouping, the summary block.
**Out:** name-based `--in` resolution itself ([[QST-fmk0p--resolving-questkit-log-in-specified-path-via]]), `--select`/`--distinct`/
`--count` ([[QST-8hjjk--allow-for-select-and-distinct-when-listing-quests]]), the views that consume grouping ([[QST-37n0t--built-in-views-next-stale-blocked-and-quest-deps]]).

### Approach

**1. `--all` → `--all-logs` / `-A`.** No hidden alias; update the doc references
in the same commit. `--global` was considered and rejected: it overstates, since
logs outside the roots are still excluded, and `git config --global` means "the
user-level file", importing the wrong intuition.

**2. Repeatable `--root`**, de-duplicating **resolved log paths** — nested roots
would otherwise emit the same quest twice, and duplicate ids in a `--format json`
export are a silent data bug. `resolve_sweep_root()` becomes
`resolve_sweep_roots() -> list[Path]`. `QST_ROOT` accepts `os.pathsep`-separated
paths — `os.pathsep`, not `:`, since the Makefile targets Windows and `C:\` would
shred a colon split.

**3. Repeatable `--in`**, accepting names or paths. Allowed on mutation commands
too: it remains a **bounded search set with no silent sweep past it**, which is
the property `--in` has always guaranteed. A per-command rule about how many
`--in`s are legal is a rule nobody remembers.

**4. One `resolve_log_set()`** with three sources — explicit `--in`*,
`--all-logs` + `--root`*, or the default walk-up. This replaces two divergent
code paths (`resolve_log` vs `find_all_logs` + `resolve_sweep_root`); it is a
simplification, not an addition.

**5. Per-log grouping** whenever more than one log is in scope. Grouping is
**sort order plus a table-only separator header** — JSON and CSV stay flat arrays
ordered by log. Nesting JSON would break every `jq '.[].title'` consumer,
including the Home Assistant `command_line` sensor in [[QST-5rjla--obsidian-capture-surface-generated-template-md-topology-rows-bases-triage-view]].

**5b. The column set is computed once for the whole result, and the header
repeats under every group separator.**

*One column set, not one per log.* If `--select` names a field that exists in
some logs and not others, the column is present everywhere and renders **empty**
where absent — never silently dropped for the whole table, never ragged per
group. Three reasons: an empty column is informative (this log has no such data)
where a missing one hides the fact; CSV and JSON must be uniform anyway, and a
table that disagreed with them would be worse; and ragged groups cannot be
scanned side by side. A `--select` field that exists in **no** log in scope stays
a hard error naming the valid fields; one that exists in at least one gets a
stderr note in the summary block naming the logs that lack it.

*Header repeats.* The alternative — one header at the top — puts it 60 rows away
from the group you are reading and makes each group non-copy-pasteable on its
own. Repeating an identical header costs one line per group and is worth it. The
separator carries the log name and its count:

```
── family ─────────────────────────────────────  3 quests
ID         STATUS  PRIORITY  TITLE
QST-9x2kf  todo    high      Book the chimney sweep
```

**6. The summary block, always on stderr**, silenced by `--quiet` / `-q`. Rows go
to stdout, so `| jq` and `--out FILE` stay clean and a human at a terminal sees
both. Suppressing on non-TTY was rejected: it makes output device-dependent,
which is the exact class of problem this quest exists to remove.

**7. Two-layer limits.** A view's own `limit` is part of its per-log definition
and applies per log; a command-line `--limit` truncates the final concatenated
result. So `quest next -A` returns one row per log and `quest next -A --limit 3`
returns three of those rows. Stated once, learnable, and never silently discards
a whole log's ranking.

### Snippets

```
$ quest stale --in questkit --in realm-system

── questkit ────────────────────────────────────────────
QST-onxad  draft  medium  New frontmatter attributes
── realm-system ────────────────────────────────────────
QST-ut83f  todo   low     make help per target

view   stale (built-in; questkit override active)
where  status=todo,in-progress,draft  ·  idle>14
       (status filter is a default — override with --where status:exists)
sort   idle:desc
page   rows 1-12 of 12
logs   2 logs, 12 quests
       swept from /home/gitops/realm  2 logs, 12 quests
```

With multiple roots the `logs` block gains one row per root.

## Acceptance Criteria

- [ ] `-A` / `--all-logs` works; `--all` is gone and the docs are updated
- [ ] Multiple `--root` de-duplicates logs discovered under overlapping roots
- [ ] `QST_ROOT` accepts `os.pathsep`-separated paths
- [ ] Multiple `--in` works on `list` and every view, resolving names and paths
- [ ] Multiple `--in` on a mutation command searches only those logs
- [ ] Table output groups by log when >1 log is in scope
- [ ] The column header repeats under every group separator
- [ ] The group separator names the log and its row count
- [ ] `--select` computes one column set for the whole result, blank where a log lacks the field
- [ ] `--select` naming a field absent from every log in scope is a hard error
- [ ] `--select` naming a field absent from some logs prints a stderr note naming them
- [ ] JSON and CSV remain flat arrays, ordered by log
- [ ] `quest list --format json | jq '.[].title'` succeeds unchanged
- [ ] The summary block goes to stderr and `--quiet` silences it
- [ ] The summary names the injected default status filter and its override idiom
- [ ] The `logs` block prints one row per root
- [ ] `quest next -A --limit 3` returns 3 rows total, not 3 per log

## Log

- 2026-08-19: captured. Grouping replaced an earlier proposal to force a global ranking across logs — concatenating per-log results means each log evaluates its own view definition, which is strictly more correct.
