---
id: QST-v0hnq
title: "questkit v2: dynamic schema engine and multi-log architecture"
description: Design and implement a dynamic per-log schema engine, global-ID cross-log mutation resolution, an ambiguity guard for capture, an overhauled multi-log quest list query engine, and a new quest schema introspection command. (v2)
project: questkit
type: feature
status: done
priority: high
tags:
  - cli
  - dx
  - schema
created: 2026-08-13
status_changed: 2026-08-14
modified: 2026-10-16
aliases:
  - QST-v0hnq
blocked_by: []
milestone: 0.2.0
tier: blueprint
---

## Description

v1 (`QST-whm2e`) deliberately scoped every command to exactly one quest log
("nearest zone wins") and hardcoded the valid `type`/`status`/`priority`/etc.
vocabularies as Python frozensets in `schema.py`. This quest is the follow-on
Blueprint `QST-vl9cq` asked for: it answers "is a real cross-log query worth
building, and what shape" (yes — see Spec), while explicitly keeping bulk
multi-log *writes* out of scope (every command here still ever mutates exactly
one file; only *finding* that file may cross log boundaries).

## Spec

### 1. Dynamic schema engine (`schema.py`, `config.py`)

`.questkit.yaml` gains an optional `schema:` block: `types`/`statuses`/`tiers`/
`priorities`/`efforts` overrides, an `extends: <path>` directive (resolved
relative to the log's own directory; the target is itself a schema document, so
`extends` chains recursively; sibling keys fully replace — not merge — the
corresponding parent key), and a `fields:` map of custom field definitions
(`type`, `required`). `SchemaConfig.default()` (no `schema:` block) reproduces
today's hardcoded frozensets exactly, so this is 100% backward compatible —
none of the four live logs (`common`, `pensieve`, `system`,
`career-transition`) need any config change.

`quest new` null-initializes every custom field and prints a `[warning]` per
field to stderr. `quest validate` (and the `quest-validate` pre-commit hook)
fails when a `required: true` custom field is null/missing.

### 2. Ignore-list engine (`config.py`, `discovery.py`)

Directory pruning for cross-log sweeps does **not** hardcode a "starts with
`.`" rule. It mirrors two conventions already established elsewhere in the
Realm: `99-system/metadata/frontmatter.schema.yaml`'s `skip_dirs` (an explicit
named default list) and `syncthing.yaml`/`scaffold_syncthing.py`'s `#include
<path>` directive (pulls another file's patterns in, recursively, with
circular/missing-target guards). `.questkit.yaml` gains an optional `ignore:`
list supporting both literal patterns and `#include` entries; a log's own
ignore rules extend the active prune set for its own subtree only.

### 3. Global-ID mutation resolution (`discovery.py`)

`set`/`show`/`done` no longer require `--in`. Resolution: nearest log (today's
walk-up) checked first; if the id isn't there, sweep every log under
`QST_ROOT` (env var) or the git root or cwd, in that order, and mutate
whichever single file matches. An explicit `--in` still means exactly what it
means today — no silent sweep past it.

### 4. Ambiguous destination guard (`discovery.py`)

`quest new`, when no ancestor log is found via walk-up and 2+ quest logs exist
somewhere downward from cwd, fails fast: `"Ambiguous destination. Multiple
quest logs found in subdirectories. Specify target with --in <DIR>."` instead
of silently falling back to `QUEST_LOG`. (`quest init` already takes an
explicit target, so it doesn't need this guard.)

### 5. `quest list` overhaul (`list_cmd.py`)

Drops `--status`/`--type`/`--tag` for a dynamic `--where` filter (repeatable;
`field=value`, `field~value` substring/membership, `field:exists`), adds
`--all`/`--root` (cross-log aggregation via the sweep above), `--format
table|json|csv|prompt`, `--columns`, `--sort`, `--limit`/`--offset`, `--out`
(tee to a file). `--all` mode appends a `project` column. No new dependencies —
`json`/`csv` are stdlib.

### 6. `quest schema` introspection (new `schema_cmd.py`)

`quest schema quest [field] [--format json|table]` — dumps the active log's
merged schema, or one field's valid values / spec, for agents that shouldn't
have to guess or hallucinate valid enum values.

## Acceptance Criteria

- [x] `schema:` block with `extends` + custom `fields` works; validated by
      tests covering merge/override semantics and circular/missing `extends`.
- [x] `quest new` null-injects + warns on uninitialized custom fields; `quest
      validate` and the pre-commit hook fail on missing required custom fields.
- [x] `ignore:` (+ `#include`) correctly scopes directory pruning for cross-log
      sweeps, extending only its own subtree.
- [x] `set`/`show`/`done` resolve an id across logs when not in the nearest
      one; `--in` remains a precise, non-bypassable override.
- [x] `quest new` fails fast with the exact ambiguous-destination message when
      run from a directory with 2+ sub-logs and no ancestor log.
- [x] `quest list --where/--all/--root/--format/--columns/--sort/--limit
      /--offset/--out` all work per spec; default (no filters) output is
      unchanged from today's.
- [x] `quest schema quest [field] [--format]` returns correct values.
- [x] Full test suite + ruff pass; `docs/questkit.md` documents all of the
      above.
- [x] `QST-vl9cq` updated: Log entry linking here, acceptance criteria checked,
      status set to `completed`.

## Log

- 2026-08-13: captured, based on an external "handoff blueprint" the user
  supplied; two design decisions confirmed with the user before starting:
  implement cross-log mutation resolution exactly as specified (still only
  ever touches one file), and formalize this as a Blueprint quest closing out
  `QST-vl9cq`. The ignore-list engine (item 2) was added after the user
  corrected an initial "dot-prefix" pruning heuristic, redirecting to mirror
  the Realm's existing `skip_dirs`/`#include` conventions instead.
- 2026-08-13: implemented. Test suite grew 37 -> 99 tests, all passing;
  `ruff check` clean. Two real bugs found and fixed during manual smoke
  testing before they reached the test suite: (1) a broken config
  (bad schema `extends`) in one log during a `--all` sweep was aborting
  the whole aggregation instead of being skipped with a warning -- fixed
  in both `discovery._local_ignores` and `list_cmd._collect_rows`. (2) the
  ignore-scoping design as first implemented only pruned descendants of
  the log directory itself, missing the common real case of a sibling
  build dir (`project/dist` next to `project/quests`) -- fixed with a
  one-level lookahead in `discovery._find_logs` so a `quests`-shaped
  child's `ignore:` config is known before its siblings are visited.
  `docs/questkit.md` updated throughout (§1, §5, §6, §8, §9, §10, §13,
  §15); version bumped 0.1.0 -> 0.2.0. Not yet committed -- left for the
  user to review and commit.
- 2026-08-13: fast-follow. `--where field~value` (contains) now accepts a
  comma-list matched as OR, same convention `field=value` already had --
  `tags~frontend,backend` means "either tag qualifies," repeating `--where`
  on the same field means AND instead (`--where "tags~frontend" --where
  "tags~urgent"` requires both). Implemented as a shared
  `_split_candidates()` helper in `list_cmd.py`; `docs/questkit.md`'s
  `--where` grammar section updated with the OR-vs-AND distinction spelled
  out explicitly.

