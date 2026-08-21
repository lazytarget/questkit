---
id: QST-3ehhu
title: quest logs — inventory every quest log under a root
description: Add a 'quest logs' command that lists every quest log discoverable from the sweep root, with per-log project, counts and git mode, and aggregates config warnings.
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
modified: 2026-08-20
agentic: afk
aliases:
  - QST-3ehhu
blocked_by:
  - QST-fmk0p
effort: s
milestone: 0.3.0
tier: brief
---

## Description

`quest list -A` sweeps every log but reports only *quests* — there is no way to see
the **logs themselves**. In a seven-log vault (129 quests as of 2026-08-19) that
leaves no answer to "what logs exist here?", "which one is `--in` about to resolve
to?", or "which project name maps to which path?".

The paths are long and nested and are routinely misremembered, which is the actual
friction behind targeting the wrong log — see [[QST-fmk0p--resolving-questkit-log-in-specified-path-via]].

`discovery.find_all_logs()` already does the discovery and already prunes via
`DEFAULT_IGNORE_DIRS` plus each log's own `ignore:` list. This is a thin,
read-only command over machinery that shipped in v2.

It also gives a home to something `docs/questkit.md` §14 flags as missing:
broken-config warnings during a sweep are printed per-log, but *"nothing currently
aggregates or de-duplicates them across a large sweep."*

## Spec

1. `quest logs` prints one row per discovered log, sorted by project name:

   ```
   PROJECT              QUESTS  OPEN  GIT     PATH
   career-transition        13     9  manual  02-projects/peter/2026-career-transition/quests
   family                    0     0  auto    02-projects/family/quests
   grocy-ecosystem          66    54  auto    02-projects/grocy-ecosystem/quests
   ...

   7 logs, 129 quests, swept from /home/gitops/realm
   ```

   - `PROJECT` — the config's `project:`, or `-` for a catch-all log with none.
   - `QUESTS` — files matching that log's own `pattern`.
   - `OPEN` — quests not in a terminal status, per the log's own
     `terminal_statuses` ([[QST-j68u5--schema-engine-field-order-defaults-macros-typed-fields-strict-writes]] rule 10), never a
     hardcoded pair.
   - `GIT` — `auto` | `manual`.
   - `PATH` — relative to the sweep root.

2. The footer names the sweep root and the totals — **one row per root** once
   `--root` is repeatable ([[QST-iqwjm--multi-log-query-ux-all-logs-repeatable-in-and-root-per-log-grouping-summary-block]]). This is not decoration: selective
   Syncthing means a log present on one device is absent on another, so the scope
   of any sweep is device-dependent and must be stated rather than implied.

3. `--root DIR` (repeatable) uses the same resolution as `quest list -A`.

4. `--format table|json`. JSON emits one object per log with the full config
   surface — project, path, git, pattern, prefix, counts, declared custom fields,
   schema overrides — for programmatic consumers.

5. `--verbose` (table only) adds a second line per log naming that log's schema
   overrides and custom fields, including its `strict` mode ([[QST-j68u5--schema-engine-field-order-defaults-macros-typed-fields-strict-writes]]).

6. Config warnings are collected, **de-duplicated, and printed once after the
   table** under a `warnings:` heading naming the offending log, instead of
   interleaved with rows. A log whose config fails to load still appears as a row,
   with its error in place of counts.

7. **Enforces `project:` uniqueness** across the sweep — the identity guarantee
   [[QST-fmk0p--resolving-questkit-log-in-specified-path-via]] depends on. A collision is reported as an error naming both paths.

8. **Archived counts are derived, not stored.** A log whose quests all carry
   `archived: true` ([[QST-lcsza--archive-a-whole-quest-log-instead-of-individual-quests]]) renders
   `13/13 archived`; a partially archived one renders `4/13 archived`. There is
   no log-level archived flag to read, so the column can never disagree with the
   files. Fully archived logs are excluded from the footer totals.

9. Read-only. `quest logs` never writes, never creates, never migrates.

## Open Questions

None. The terminal-status question is decided in
[[QST-j68u5--schema-engine-field-order-defaults-macros-typed-fields-strict-writes]] (rule 10) — `OPEN` reads the log's declared
`terminal_statuses`.

## Acceptance Criteria

- [x] `quest logs` from the Realm root lists all seven logs with correct counts
- [x] `quest logs --root <dir>` restricts the sweep to that subtree
- [x] A log with no `project:` renders `-` rather than crashing
- [x] `quest logs --format json` emits one object per log, valid for `jq`
- [x] `--verbose` shows schema overrides, custom fields, strict mode and terminal statuses
- [x] `OPEN` uses the log's own `terminal_statuses`
- [x] Archived counts are derived from the quests; a fully archived log is excluded from footer totals
- [x] A log with a broken `schema.extends` still appears as a row, with its warning printed once after the table
- [x] The footer names the sweep root and totals, one row per root
- [x] A duplicate `project:` across two logs is reported as an error naming both
- [x] `.stversions/`, `.git/`, caches and per-log `ignore:` entries are pruned
- [x] Tests cover: zero logs, one log, nested logs, a broken config, a duplicate project

## Log

- 2026-08-21: implemented (batch B4), landing last within the batch since it reuses `discovery.resolve_log_set()` (built earlier in this batch) rather than rolling its own root-sweep-and-dedupe logic. Duplicate `project:` is a hard error printed immediately and the command exits 1 -- not collected as a warning -- because `--in`'s name resolution ([[QST-fmk0p--resolving-questkit-log-in-specified-path-via]]) is already load-bearing on that uniqueness, so a collision here means a real, pre-existing inconsistency in the corpus, not a soft heads-up. Ran against the real Realm as a sanity check: 7 logs, 145 quests, and `career-transition`/`grocy-ecosystem`/`pensieve` correctly report `OPEN == QUESTS` because their `status: completed` values predate the corpus-wide `completed`→`done` migration, which is still deliberately deferred (see the plan's §13) -- not a bug, exactly the behavior `terminal_statuses` should produce against an unmigrated log.
- 2026-08-19: captured during a design grilling session on questkit's next feature set.
- 2026-08-19: folded into [[QST-bmzl2--questkit-v3-loop-closure-multi-log-ux-and-agent-handoff]]; the terminal-status question moved to [[QST-j68u5--schema-engine-field-order-defaults-macros-typed-fields-strict-writes]] and `project:` uniqueness enforcement added.
