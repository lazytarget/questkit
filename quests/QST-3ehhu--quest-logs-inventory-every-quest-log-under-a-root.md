---
id: QST-3ehhu
title: "quest logs — inventory every quest log under a root"
description: "Add a 'quest logs' command that lists every quest log discoverable from the sweep root, with per-log project, counts and git mode, and aggregates config warnings."
created: 2026-08-19
modified: 2026-08-19
type: feature
tier: brief
status: todo
priority: high
effort: s
project: questkit
tags:
  - questkit
  - cli
  - dx
  - multi-log
blocked_by:
  - QST-fmk0p
aliases:
  - QST-3ehhu
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
   - `OPEN` — quests not in a terminal status.
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

8. Read-only. `quest logs` never writes, never creates, never migrates.

## Open Questions

- **Terminal statuses under a custom schema.** `OPEN` needs a definition of "not
  done", and hardcoding `completed`/`scrapped` breaks any log that overrides
  `statuses:`. Now tracked in [[QST-j68u5--schema-engine-field-order-defaults-macros-typed-fields-strict-writes]], since [[QST-b9lqo--computed-fields-and-comparison-operators-for-where]] needs the same
  decision — it is load-bearing in two places and should be decided once.
- `agentic:` deliberately left unset — AFK-readiness is a triage outcome to be
  earned, not declared at capture.

## Acceptance Criteria

- [ ] `quest logs` from the Realm root lists all seven logs with correct counts
- [ ] `quest logs --root <dir>` restricts the sweep to that subtree
- [ ] A log with no `project:` renders `-` rather than crashing
- [ ] `quest logs --format json` emits one object per log, valid for `jq`
- [ ] `--verbose` shows schema overrides, custom fields and strict mode
- [ ] A log with a broken `schema.extends` still appears as a row, with its warning printed once after the table
- [ ] The footer names the sweep root and totals, one row per root
- [ ] A duplicate `project:` across two logs is reported as an error naming both
- [ ] `.stversions/`, `.git/`, caches and per-log `ignore:` entries are pruned
- [ ] Tests cover: zero logs, one log, nested logs, a broken config, a duplicate project

## Log

- 2026-08-19: captured during a design grilling session on questkit's next feature set.
- 2026-08-19: folded into [[QST-bmzl2--questkit-v3-loop-closure-multi-log-ux-and-agent-handoff]]; the terminal-status question moved to [[QST-j68u5--schema-engine-field-order-defaults-macros-typed-fields-strict-writes]] and `project:` uniqueness enforcement added.
