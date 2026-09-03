---
id: QST-f0329
title: "Duplicate project: names across logs resolve inconsistently"
project: questkit
type: bug
status: draft
priority: high
tags:
  - questkit
  - cli
  - discovery
  - correctness
created: 2026-09-03
modified: 2026-09-03
agentic:
aliases:
  - QST-f0329
blocked_by: []
component:
effort: m
milestone:
related_adrs:
---

## Spec

Reproduced with a git worktree checkout (e.g. `questkit-worktrees/feature-*`)
sitting alongside the primary `questkit` checkout: two physically distinct
logs both declare `project: questkit` in their `.questkit.yaml`. Every
command that discovers/resolves logs by project name handles the collision
differently, and none of them handle it *well*:

- `quest logs` — hard errors: `project 'questkit' is declared by both
  <path A> and <path B> -- project: must be unique per log`. Blocks the
  command entirely, even though nothing is actually broken yet.
- `quest list -A` — silently merges: both logs' quests get grouped under one
  `── questkit ───` header with no indication two physical sources were
  combined. Looks like one project with N quests; it's actually two logs'
  quests concatenated.
- `quest list --in questkit` (or any single-log `--in PROJECT` resolution) —
  silently picks one of the two and queries only that one, with no warning
  that the name was ambiguous. This is the dangerous case: `quest set`/`done`
  targeting `--in questkit` could silently act on the wrong physical log.

This is the project-name sibling of the duplicate-*id* problem already
flagged in QST-whcdp check 1 ("the resolution sweep silently picks the
first sorted path") — same underlying issue (log discovery assumes a key is
globally unique, nothing enforces it, first-match-wins masks the collision),
different key.

### Why this isn't a skip_dirs problem

Considered pruning worktree checkouts out of log discovery via the existing
skip_dirs/`#include` convention (frontmatter.schema.yaml's `skip_dirs`,
mirrored by questkit's own `find_all_logs`). Doesn't fit: a worktree log is
not junk like `.git`/`node_modules` — it holds genuinely different,
real quest state (whatever the feature branch has in flight). Pruning it by
path pattern would just hide data, not resolve the ambiguity.

### Options

1. **Enforce uniqueness, hard error everywhere** (extend today's `quest
   logs` behavior to `list -A`, `--in`, etc.). Correct-by-construction, but
   worktrees are a routine, expected occurrence in this repo (see the Realm's
   own agent-session workflow) — hard-erroring every cross-log command
   whenever a feature branch is checked out as a worktree is disruptive for
   something that isn't actually a mistake.
2. **Warn, don't block** — print a warning once (stderr, like the existing
   `[quest list] logs N logs swept` summary line) whenever project names
   collide, then continue with defined, documented behavior for what
   "continue" means.
3. Do nothing differently for discovery/listing, but make **`--in
   PROJECT` resolution itself refuse to guess** — error only when the
   ambiguity could cause a wrong-log write (single-log commands: `--in`,
   `set`, `done`, `scrap`, `mv`), while read-heavy aggregate views (`list
   -A`) keep working with a warning and a way to disambiguate (see below).

Leaning towards 2+3 combined: never hard-fail pure enumeration/listing
(annoying for a routine git state), but require an unambiguous target
before any single-log resolution or write — and always disambiguate
duplicate-project display by log path (or a `--root`-relative short id)
instead of silently concatenating under one header.

## Acceptance Criteria

- [ ] Decide and document the policy for warn-vs-error, and where each
      applies (enumeration/list vs single-log resolution/write)
- [ ] `quest list -A` never silently merges two physically distinct logs
      under one indistinguishable header — collisions are visible in the
      output (grouped-but-labeled by path, or similar)
- [ ] `--in PROJECT` (and anything that resolves a single log by name:
      `set`, `done`, `scrap`, `mv`, ...) never silently picks one of several
      matches — either errors with both candidate paths, or accepts a way
      to disambiguate (e.g. `--in <path>` as well as `--in <project-name>`)
- [ ] `quest logs`' existing hard error is reconciled with whatever the
      chosen policy is (today it's the strictest of all the commands, by
      accident rather than design)
- [ ] Covered by a test fixture with two logs sharing one `project:` name
- [ ] Docs note git worktrees as the common real-world trigger

## Log

- 2026-09-03: captured from user report — hit via an active
  `questkit-worktrees/feature-questkit-v4` worktree duplicating the
  `questkit` project name; not yet in the R&D ideas catalog
