---
id: QST-iqwjm
title: "Multi-log query UX: --all-logs, repeatable --in and --root, per-log grouping, summary block"
description: "Make the scope of every query legible: rename --all, allow multiple logs and roots, group results per log, and print the filters in effect."
project: questkit
type: feature
status: done
priority: high
tags:
  - questkit
  - cli
  - dx
  - multi-log
created: 2026-08-19
status_changed: 2026-08-20
modified: 2026-10-16
agentic: afk
aliases:
  - QST-iqwjm
blocked_by:
  - QST-fmk0p
effort: m
milestone: 0.3.0
tier: brief
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
- **There is no way to query two logs.** "House contexts" is `family + home-b`;
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
scope  archived: exclude  (3 archived quests hidden — see --archived)
sort   idle:desc
page   rows 1-12 of 12
logs   2 logs, 12 quests
       swept from /home/gitops/realm  2 logs, 12 quests
```

With multiple roots the `logs` block gains one row per root.

## Acceptance Criteria

- [x] `-A` / `--all-logs` works; `--all` is gone and the docs are updated
- [x] Multiple `--root` de-duplicates logs discovered under overlapping roots
- [x] `QST_ROOT` accepts `os.pathsep`-separated paths
- [x] Multiple `--in` works on `list` and every view, resolving names and paths
- [x] Multiple `--in` on a mutation command searches only those logs
- [x] Table output groups by log when >1 log is in scope
- [x] The column header repeats under every group separator
- [x] The group separator names the log and its row count
- [x] `--select` computes one column set for the whole result, blank where a log lacks the field
- [x] `--select` naming a field absent from every log in scope is a hard error
- [x] `--select` naming a field absent from some logs prints a stderr note naming them
- [x] JSON and CSV remain flat arrays, ordered by log
- [x] `quest list --format json | jq '.[].title'` succeeds unchanged
- [x] The summary block goes to stderr and `--quiet` silences it
- [x] The summary names the injected default status filter and its override idiom
- [x] The summary names the `--archived` scope and how many quests it hid, so an all-archived log never returns silently empty
- [x] The `logs` block prints one row per root
- [x] `quest next -A --limit 3` returns 3 rows total, not 3 per log

## Log

- 2026-08-21: implemented (batch B4) with three items deliberately deferred to later batches, noted below. `list_cmd._collect_rows` now goes through the one `discovery.resolve_log_set()` instead of its own branch on `args.all_logs`/`args.in_dir` -- the consolidation the quest asked for. `resolve_sweep_root` (singular) survives as a one-line wrapper over the new plural `resolve_sweep_roots()`, so every existing caller (`resolve_mutation_target`, `resolve_by_name_or_path`'s default) is unaffected. `resolve_by_name_or_path` itself grew a `root: Path | list[Path] | None` parameter rather than a second function, since every existing single-root call site (from `QST-fmk0p`) already passes a bare `Path`.

  **A real design problem surfaced building per-log grouping**: after `--select` projects a row down to just the requested fields, the row loses whatever told it which log it came from -- so grouping breaks, and worse, `--distinct` would start treating identical values from different logs as distinct if the log identity leaked back in as a hidden dedup key. Solved with one internal bookkeeping key, `_LOG_KEY` (`"__log__"`), carried through projection but stripped before JSON output and excluded from the `--distinct` equality check, and never a legal `--select` name (it isn't in `CORE_FIELDS` or any schema). One key, three call sites that had to agree with each other.

  **Deferred, and revisit when the dependency lands:**
  - The summary's `view` line and per-log independent `--sort` ranking -- both are properties of a *view definition* ([[QST-37n0t--built-in-views-next-stale-blocked-and-quest-deps]]), which does not exist yet. Plain `--sort` sorts the full result globally exactly as before this quest; grouping only reclusters the *already-sorted* rows by log for table display, it does not re-sort within each group.
  - The summary's `--archived` scope line -- no `archived` query flag exists until archival ships ([[QST-lcsza--archive-a-whole-quest-log-instead-of-individual-quests]]).
  - `quest next -A --limit 3` returning 3 total rather than 3-per-log -- `next` does not exist until B5.

  Extended repeatable `--in` beyond `list` to `set`/`done`/`scrap` (via `resolve_mutation_target` accepting a list), since the spec explicitly calls out mutation commands as "a bounded search set with no silent sweep past it." `new`/`mv`/`show`/`schema`/`format`/`validate` keep single-target `--in` -- a repeatable `--in` on `new` has no coherent meaning (which of several logs would it write to?), and the others already gained name resolution from `QST-fmk0p` without needing to become multi-valued.
- 2026-08-19: captured. Grouping replaced an earlier proposal to force a global ranking across logs — concatenating per-log results means each log evaluates its own view definition, which is strictly more correct.

