---
id: QST-3ehhu
title: quest logs — inventory every quest log under a root
description: Add a 'quest logs' command that lists every quest log discoverable from the sweep root, with per-log project/counts/git-mode, and aggregates config warnings that today scroll past unread.
created: 2026-08-19
modified: 2026-08-19
type: feature
tier: brief
status: todo
priority: high
project: questkit
tags:
  - cli
  - dx
  - multi-log
blocked_by: []
aliases:
  - QST-3ehhu
effort: s
---

## Description

`quest list --all` sweeps every log but reports only *quests* — there is no way
to see the **logs themselves**. In a seven-log vault (129 quests as of
2026-08-19) that leaves no answer to "what logs exist here?", "which one is
`--in` about to resolve to?", or "which project name maps to which path?".

The paths are long and nested (`02-projects/lazytarget/pensieve/quests`,
`02-projects/peter/2026-career-transition/quests`) and are routinely
misremembered — which is the actual friction behind targeting the wrong log.

`discovery.find_all_logs()` already does the discovery and already prunes via
`DEFAULT_IGNORE_DIRS` plus each log's own `ignore:` list. This is a thin,
read-only command over machinery that shipped in v2.

It also gives a home to something [docs/questkit.md](../docs/questkit.md) §14
flags as missing: broken-config warnings during a sweep are printed per-log,
but "nothing currently aggregates or de-duplicates them across a large sweep."

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
   - `OPEN` — quests not in a terminal status (see open question below).
   - `GIT` — `auto` | `manual`.
   - `PATH` — relative to the sweep root.

2. The footer names the sweep root and the totals. This is not decoration:
   selective Syncthing means a log present on one device is absent on another
   (`work-a` and `work-b` do not sync to the phone), so the scope of any
   sweep is device-dependent and must be stated rather than implied.

3. `--root DIR` uses the same resolution as `quest list --all` —
   `discovery.resolve_sweep_root()`: explicit, then `QST_ROOT`, then the git
   root, then cwd.

4. `--format table|json`. JSON emits one object per log with the full config
   surface (project, path, git, pattern, prefix, counts, declared custom
   fields, schema overrides) for programmatic consumers.

5. `--verbose` (table only) adds a second line per log naming that log's
   schema overrides and custom fields.

6. Config warnings are collected, de-duplicated, and printed **once, after the
   table**, under a `warnings:` heading naming the offending log — instead of
   interleaved with rows. A log whose config fails to load still appears as a
   row, with its error in place of counts.

7. Read-only. `quest logs` never writes, never creates, never migrates.

## Acceptance Criteria

- [ ] `quest logs` run from the Realm root lists all seven logs with correct counts
- [ ] `quest logs --root <dir>` restricts the sweep to that subtree
- [ ] A log with no `project:` renders `-` rather than crashing
- [ ] `quest logs --format json` emits one object per log, valid for `jq`
- [ ] A log with a broken `schema.extends` still appears as a row, and its warning prints once, after the table
- [ ] The footer names the sweep root and the log/quest totals
- [ ] `.stversions/`, `.git/`, caches, and per-log `ignore:` entries are pruned (inherited from `find_all_logs`)
- [ ] Tests cover: zero logs, one log, nested logs, and a log with a broken config

## Open Questions

- **Terminal statuses under a custom schema.** `OPEN` needs a definition of
  "not done". Hardcoding `completed`/`scrapped` breaks the moment a log
  overrides `statuses:` with a vocabulary that has neither. Decide before
  implementing: either the schema block declares which of its statuses are
  terminal, or `OPEN` falls back to `total` for logs whose vocabulary has no
  recognized terminal status. The former is more correct and pushes a small
  addition into `SchemaConfig`.
- **Relationship to `--in <project-name>`.** See
  [[QST-fmk0p--resolving-questkit-log-in-specified-path-via]]. Both depend on
  `project:` being a **unique identity** per log rather than a free label. If
  that is adopted, `quest logs` is the natural place to enforce uniqueness and
  report a collision.
- `agentic:` deliberately left unset — AFK-readiness is a triage outcome to be
  earned, not declared at capture time.

## Log

- 2026-08-19: captured during a design grilling session on questkit's next feature set.
