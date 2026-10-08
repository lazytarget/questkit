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
modified: 2026-10-08
agentic: hitl
aliases:
  - QST-f0329
blocked_by: []
component:
effort: m
milestone: 0.4.0
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

### Also affects Obsidian Bases (`quests.base`)

Same root cause, third consumer, worse blast radius: the generated
`quests/quests.base` filters with `project == "questkit"` (confirmed by
diffing it against `src/templates/quests.base` — the template gains that
clause on generation). Bases has no folder-scoping filter
(`file.path.startsWith(...)`) — it's a vault-wide glob restricted only by
`file.name.startsWith("QST-")` and `project == "<name>"`. So once a
long-lived sibling worktree (`<repo>-worktrees/<branch>/`, the Realm's own
convention — see `.realm/README.md`) is synced into the same Obsidian
vault, its quests carry the same `project: questkit` value and get pulled
into every view by that filter alone, with no dedup. This is confirmed to
be what produced the "way too many rows" the user saw when testing Bases —
two logs' worth (roughly 58 + 57 quests) rendered as one inflated table.

Unlike the CLI paths above, this isn't fixable by changing `quest`'s
argument-resolution logic — Bases never calls into questkit at all. Whatever
uniqueness/disambiguation policy comes out of this quest needs a concrete
answer for what `project:` actually *means* project-wide (must be
vault-unique, since it's the only filter key Bases has), or `quests.base`
needs a different, still Bases-expressible key to filter on (e.g. a
generated `log:`/`log_path:` field unique per physical log) if `project:`
itself is allowed to collide.

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

### The wider duplicate family (2026-10-02)

Worktree logs are one of four ways the same quest or log shows up more than
once. They share a root cause (discovery assumes a key is unique and the
first match wins) and should share one policy, even though each is fixed in
its own quest:

| Source | Duplicated key | Tracked in |
|--------|----------------|------------|
| Git worktree checkouts | `project:` per log, and every quest id inside it | this quest |
| Syncthing conflict copies | quest id (`QST-x.sync-conflict-….md`) | [[QST-oe92z--exclude-syncthing-conflict-copies-from-quest-enumeration]] |
| Re-capturing the same idea | title (different ids) | [[QST-lc3d7--check-for-duplicates-when-adding-with-same-title]] |
| Ids colliding across logs | quest id | [[QST-whcdp--quest-doctor-diagnoses-environment-logs-and-installs]] check 1 |

Learnings since capture:

- **Not questkit-specific.** On 2026-10-01 `quest logs` at the Realm root
  hard-failed on `project 'home-lab'` (`home-lab/quests` vs
  `home-lab-worktrees/arr-stack/quests`). Any repo with a worktree breaks
  the Realm-wide sweep, not just questkit's own.
- **Worktrees are long-lived.** `questkit-worktrees/feature-questkit-v4` has
  existed since 2026-08-24, so a worktree is a normal state for weeks, not
  a moment. That rules out a hard error as the steady-state answer.
- **Obsidian Bases shows one row per checkout.** Every quest appears once per
  worktree that holds it, because the Base filters only on `project` and
  file name. Worth verifying whether Bases' `file.inFolder()` gives the
  folder scoping this quest assumed is missing; if so, generating the Base
  with a folder filter is cheaper than a new `log_path` field.
- **Content can't tell worktrees apart.** Two worktrees on the same commit
  hold byte-identical quests, so content hashes don't help. Only the log
  path tells them apart. This is why the MCP server (QST-nxxk8) takes a
  required `log` parameter accepting a path; the CLI's `--in` should accept
  a path for the same reason (option 3 above).
- **Discovery tools must label, not fail.** `quest logs` and the MCP
  `list_quest_logs` should list both checkouts with their paths and a
  collision warning, never error out of the whole listing.

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
- [ ] `quests.base` generation (`src/templates/quests.base` →
      `quests/quests.base`) resolved against the same policy: either
      `project:` is enforced/treated as globally unique so `project ==
      "<name>"` stays a safe filter, or the generated Base filters on a key
      that actually is unique per physical log
- [ ] One documented duplicate policy shared by the four sources in the
      table above (worktrees, conflict copies, same-title captures,
      cross-log ids)
- [ ] `--in` accepts a log path as well as a project name, matching the MCP
      server's `log` parameter

## Log

- 2026-09-03: captured from user report — hit via an active
  `questkit-worktrees/feature-questkit-v4` worktree duplicating the
  `questkit` project name; not yet in the R&D ideas catalog
- 2026-09-03: confirmed this is also what caused inflated row counts when
  testing `quests.base` in Obsidian — the generated Base's only filter is
  `project == "<name>"`, vault-wide, no folder scoping, so it silently
  pulls in the worktree's duplicate-project quests too
- 2026-10-02: widened to the duplicate-quest family (worktrees, Syncthing
  conflict copies QST-oe92z, same-title captures QST-lc3d7, cross-log ids).
  Reproduced again outside questkit (`home-lab` worktree breaks
  `quest logs` at the Realm root). Noted that content hashes can't tell
  worktrees apart, so the log path is the disambiguator.
