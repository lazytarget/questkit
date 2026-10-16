---
id: QST-lcsza
title: "Archival as an orthogonal `archived:` field, per quest and per log"
description: Add a core archived boolean that preserves a quest's status, with per-quest and whole-log commands, so a finished project stops appearing in sweeps without any file moving or any outcome being erased.
project: questkit
type: feature
status: done
priority: medium
tags:
  - questkit
  - cli
  - multi-log
created: 2026-08-19
status_changed: 2026-08-20
modified: 2026-08-20
aliases:
  - QST-lcsza
blocked_by:
  - QST-3ehhu
effort: s
milestone: 0.3.0
tier: brief
---

## Description

`02-projects/peter/2026-career-transition` is a **time-boxed** project. When it
ends, its 13 quests stay in every `-A` sweep forever — and the ones still `todo`
get nagged about by `quest stale` ([[QST-37n0t--built-in-views-next-stale-blocked-and-quest-deps]]) permanently, with
**no action that can ever silence them**. That is the concrete failure, and it is
why this ships in v3 rather than waiting for a third dead log: a dead log poisons
the loop-closure views, which are the point of v3.

## Spec

### Archival is orthogonal to status

**Scrapping and archiving are different decisions:**

| | Question it answers | Applies to |
|---|---|---|
| `status: scrapped` | What happened to this work? *(declined, cancelled)* | work that was abandoned on its merits |
| `archived: true` | Should this still be in front of me? *(retention/visibility)* | a quest at **any** status, `done` included |

A finished quest in a wound-up project is archived and emphatically not scrapped.
Career-transition holds **4 finished quests among its 13** — collapsing archival
into `status` would erase which ones shipped.

So `archived` is a **core boolean field**, not a status value and not a computed
one. Core because retention is universal — every domain archives. **Stored**
rather than derived from log config because a stored field is visible in
Obsidian's Properties panel, filterable in Bases, and greppable; a config key is
invisible to every non-CLI surface, including the family's.

It sorts into the alphabetical tail of `field_order`
([[QST-j68u5--schema-engine-field-order-defaults-macros-typed-fields-strict-writes]]), not the explicit head — it is
rarely set and never scanned.

### Commands

```bash
quest archive QST-9x2kf                              # one quest
quest archive QST-9x2kf --in career-transition       # bounded search set
quest unarchive QST-9x2kf

quest archive-log career-transition                  # every non-archived quest in that log
quest unarchive-log career-transition
```

`quest archive <id>` is sugar for `quest set <id> archived=true`, exactly as
`quest done` is sugar for `status=done`.

**`archive-log` sets no log state.** It is purely a bulk `quest archive` over the
log's quests, resolved by the same name-or-path logic as `--in`
([[QST-fmk0p--resolving-questkit-log-in-specified-path-via]]). Three consequences, all wanted:

- **One mechanism, one source of truth** — no config key that can disagree with
  the files it describes.
- **`quest new --in career-transition` needs no special rule.** The new quest is
  unarchived, so the log is no longer fully archived — correct, because the
  project came back to life. A stored log flag would have needed an error path
  here, and an answer to what happens when the two disagree.
- **`quest logs` reports `13/13 archived`**, derived, rather than a boolean that
  can drift ([[QST-3ehhu--quest-logs-inventory-every-quest-log-under-a-root]]).

The separate command name is deliberate and the clunkiness is the feature: a flag
typo cannot archive an entire log when the whole-log operation is a different
verb. They also sit in different `--help` groups ([[QST-zl5xc--group-root-commands-in-help-output-as-the-cli-passes-20-verbs]]).

### Query surface

**`--archived {exclude,include,only}`, default `exclude`.** One argparse
`choices=` option covers all three questions and makes "only the dead project"
expressible; `--include-archived` plus a separate `--archived-only` would be two
flags for one axis. Once archived quests are in scope, `--where archived=true`
and `--select archived` work like any other field.

### What archival does and does not affect

| Operation | Archived quest |
|-----------|----------------|
| `quest list` / views / `-A` sweeps | **excluded** unless `--archived include\|only` |
| `quest stale` / `next` / `blocked` | **excluded** — the point of the feature |
| `quest show` / `brief` / `deps` by id | **found**, with a note that it is archived |
| `blocked_by` reference resolution ([[QST-yiep7--qualified-cross-log-references-in-blocked-by]]) | **resolves** |
| `blocks` count ([[QST-b9lqo--computed-fields-and-comparison-operators-for-where]]) | **not counted** — nothing is really waiting |
| `quest set` / `done` by id | **found**, with a warning |
| `quest validate` | **validated normally** — archived is not exempt |

**Archival affects listing, never id resolution.** If it hid ids, every cross-log
reference into a finished project would start failing validation the day it was
archived and `quest deps` would lose half its graph — a worse problem than the
one being solved.

**Neither `status` nor `status_changed` changes.** Archiving is not a status
transition. `modified` does bump (it is a real CLI edit), which is exactly why the
two fields were split in [[QST-3h09k--status-changed-frontmatter-field-and-reusable-backfill]]: archiving 13
quests leaves `idle` untouched, so `stale` is unaffected by the archival itself.

### Alternatives

| Option | Verdict | Reason |
|--------|---------|--------|
| Core `archived: true` field + bulk log command | ✅ Chosen | Preserves the outcome, visible in Obsidian/Bases, one mechanism |
| `status: archived` | ❌ | **Erases the outcome** — 4 of the 13 are finished, and this forgets which |
| Treat `status: scrapped` as the per-quest archive | ❌ | Conflates a decision about the *work* with a decision about *retention*; a `done` quest can be archived and is not scrapped |
| `archived: true` in the log's `.questkit.yaml` only | ❌ | Invisible to Obsidian, Bases and grep — i.e. to every surface the family uses. Also needs a rule for what `quest new` does in an archived log. |
| Move files to `quests/archive/` | ❌ | Forbidden outright by [[QST-whm2e--questkit-design-blueprint-for-file-based-quest-tracking]] — breaks the Obsidian link graph this system exists to build |
| Move the log to `06-archive/` | ❌ | Immutable data vault, a different Syncthing folder, and the log lives inside a git repo |
| `--include-archived` + `--archived-only` | ❌ | Two flags for one axis |

## Acceptance Criteria

- [x] `archived` is a core boolean field, defaulting to absent/false
- [x] `quest archive <id>` sets it; `quest unarchive <id>` clears it
- [x] `quest archive <id> --in LOG` restricts the search to that log
- [x] `quest archive-log LOG` archives every non-archived quest in it, and is idempotent
- [x] `archive-log` writes no log config — archived-ness is derived
- [x] `quest new --in <fully archived log>` succeeds and the log is no longer fully archived
- [x] Archiving changes neither `status` nor `status_changed`
- [x] `--archived` defaults to `exclude`; `include` and `only` behave as named
- [x] `--where archived=true` and `--select archived` work once in scope
- [x] `quest show` / `deps` still resolve an archived id, with a note (`quest brief` ships in [[QST-xk7js--quest-brief-a-self-contained-work-order-and-the-batch-capture-that-feeds-it]], B7)
- [x] A `blocked_by` reference into an archived quest still resolves and does not error
- [x] `blocks` does not count archived quests
- [x] `quest logs` reports archived counts and excludes them from footer totals
- [x] `quest stale -A` returns nothing from a fully archived log

## Log

- 2026-08-20: implemented. `archived` was already a core field and honored by `computed.py`/`logs_cmd.py` from earlier batches ([[QST-b9lqo--computed-fields-and-comparison-operators-for-where]], [[QST-3ehhu--quest-logs-inventory-every-quest-log-under-a-root]]) — this quest added the write surface and the query axis. New `commands/archive_cmd.py`: `archive`/`unarchive` are sugar over `set_cmd.run` (like `done`); `archive-log`/`unarchive-log` bulk-iterate a resolved log's own quests directly, skipping any already at the target state (idempotent, and never bumps `modified` on a no-op). `set_cmd._coerce` gained bool coercion for `archived`; `set_cmd.run` now warns on stderr (not an error) when the target is already archived, which every command sugared over it (`done`, `scrap`, `archive`, `unarchive`) inherits for free. `list_cmd` gained `--archived exclude|include|only` (default `exclude`), filtered before view/where — so `next`/`stale`/`blocked` exclude archived quests automatically, with no code duplicated per view. `quest show` notes an archived id on stderr; `quest deps` labels an archived node `[archived]`. `logs_cmd`'s table gained an ARCHIVED column (JSON already had the count). 18 new tests in `tests/test_archival.py`.
- 2026-08-19: captured after grilling the archive question.
- 2026-08-19: reversed from log-config-only to a core per-quest field. Two corrections drove it: archiving and scrapping answer different questions (retention vs. the work's fate), and a stored field is the only form visible to Obsidian, Bases and grep — i.e. to the family. Retitled; the filename slug is deliberately left alone (filenames are immutable by design) — see [[QST-ombky--quest-validate-reports-informational-slug-drift-as-a-hard-error]].
