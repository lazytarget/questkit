---
id: QST-vl9cq
title: Investigate viability of querying multiple quest logs at once
description: Decide whether a real cross-log query command is worth building, and if so, what it should look like.
created: 2026-08-13
status_changed: 2026-08-14
modified: 2026-08-20
type: feature
tier: brief
status: completed
priority: low
milestone: 0.2.0
project: questkit
tags:
  - cli
  - dx
blocked_by: []
aliases:
  - QST-vl9cq
---

## Description

Every `quest` command resolves to exactly **one** log (`--in` / walk-up /
`QUEST_LOG`) — deliberate for v1 (see QST-whm2e), but it means there is no
built-in way to ask "what's active across the whole Realm?" This quest
captures the workarounds already in use and the open question of whether a
real multi-log command is worth adding.

## Investigation notes (from prior session, 2026-08-13)

Two workarounds exist today, both verified working:

**Discovery loop** — find every `.questkit.yaml`, run `quest list` against
each:

```bash
for cfg in $(find . -name .questkit.yaml -not -path "*/.git/*"); do
  dir=$(dirname "$cfg")
  echo "--- $dir ---"
  quest list --in "$dir" --status in-progress,blocked
done
```

Verified output (four logs, at the time): correctly listed
`career-transition`'s and `pensieve`'s in-progress quests, empty for
`common`/`system`. Works, but O(logs) subprocess spawns and no unified
sort/filter across the results.

**Plain grep** — no CLI needed at all, since quests are just greppable
files by design:

```bash
grep -rl "^\s*- gdrive$" --include="QST-*.md" .
```

Works, but must explicitly exclude `.git`/`.stversions` or it picks up
noise (confirmed: a stale Syncthing-version copy of a quest file showed up
in one run — see QST-whm2e's Log on the unexplained `.stversions` finding,
still open).

## Spec

Open questions to resolve before building anything:

1. **Is a built-in command actually worth it**, given both workarounds
   already work and cost nothing to maintain (no new code, no new
   surface)? The case *for*: unified sort/filter across logs, one process
   instead of N, and it's the natural next thing someone reaches for after
   `quest list`. The case *against*: v1's single-log scoping was a
   deliberate design choice (nearest-zone-wins, no ambiguity about where a
   `quest new` lands) — a multi-log *query* doesn't threaten that, but it's
   worth checking it doesn't quietly invite multi-log *writes* too, which
   should stay out of scope.
2. **If built, what's the shape?**
   - `quest list --all` — discovers every `.questkit.yaml` under the
     current `QUEST_LOG`'s... what root? There's no existing concept of
     "the Realm root" in questkit (deliberately — it's supposed to work
     standalone, outside any Realm). Needs either a `--root DIR` flag, an
     env var, or walking up to the filesystem root and scanning down
     (expensive on a large tree).
   - `QUEST_LOGS` (plural) env var — an explicit, ordered list of log
     paths, sidestepping discovery entirely. Simpler, but one more thing to
     configure per device.
   - A lightweight generated index (like the Realm's own
     `frontmatter-index.json`) that a `quest reindex` command refreshes and
     `quest list --all` reads from, instead of re-scanning every log on
     every call. Faster at scale, but introduces a cache-freshness problem
     v1 explicitly avoided everywhere else.
3. **Output shape for a merged view** — needs a log/project column added
   (currently `quest list`'s table omits it, since within one log it's
   redundant); should probably sort by status or priority across logs
   rather than grouping by log.

## Acceptance Criteria

- [x] Decide: build it, or is grep/the discovery loop good enough
      permanently?
- [x] If building: pick one of the three shapes above (or a better one)
      and write a follow-on Blueprint-tier quest with the actual design
- [x] Either way, document the chosen answer (including "we decided not
      to") somewhere durable — this quest, or its follow-on

## Log

- 2026-08-13: captured, with investigation notes carried over from the
  session that first hit this gap while demoing the CLI
- 2026-08-13: decided — build it. Follow-on Blueprint quest is `QST-v0hnq`
  (questkit v2: dynamic schema engine and multi-log architecture, this
  same log), now implemented (tests + docs done; not yet committed). Shape
  chosen: a `QST_ROOT`
  env var (option 2 from the Spec above) rather than a generated index —
  no cache-freshness problem, and it's the one that needed the least new
  machinery. `quest list --all` covers the "unified sort/filter across
  logs" case; `set`/`show`/`done` additionally resolve an id across logs
  for targeted mutations (a deliberate, narrow extension beyond pure
  query, confirmed with the user first — still only ever touches one file
  per call, no bulk multi-log write). The `.stversions`/noise-in-`grep`
  problem this quest's investigation notes flagged is solved structurally
  by `discovery.find_all_logs()`'s default ignore list, not by convention.
