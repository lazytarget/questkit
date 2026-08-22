# Changelog

All notable changes to questkit are documented here. Each release corresponds to
one epic quest in `quests/`; see the linked quest for full design rationale,
rejected alternatives, and acceptance criteria.

## [0.3.0] — 2026-08-22

[[QST-bmzl2--questkit-v3-loop-closure-multi-log-ux-and-agent-handoff]] — closing
the work loop, making multi-log targeting legible, and making the agent handoff
format real. Full design record: `docs/planning/plan_questkit_v3.md`.

### Loop closure

- **Computed fields** `blocked`, `blocks`, `idle`, `age` — derived once per query
  over the whole active row set, honoring each referenced quest's own log's
  `terminal_statuses` and the `archived` field. `--where`, `--select` and `--sort`
  all see them; they're read-only.
- **`--where` comparison operators**: `!=`, `>`, `<`, `>=`, `<=`, alongside the
  existing `=`, `~`, `:exists`.
- **Ordered vocabularies and multi-key `--sort`** — `--sort priority:asc` now
  means critical-first (declared order), not alphabetical, and a second sort key
  is honored.
- **`status_changed`** — a staleness signal written only on a real status
  transition, so it measures idleness where `modified` (bumped by every commit)
  cannot. Written by `quest set`/`quest done`/etc., and backfilled by the
  `quest-bump-modified` hook (diffed against `HEAD`) when a raw text edit —
  Obsidian, or anything bypassing the CLI — changed `status` without touching
  the field itself.
- **Qualified cross-log references** in `blocked_by`: `project/QST-xxxxx`, in
  addition to a bare id. Resolves against the named log when present in a sweep;
  downgrades to a note (never an error) when the log simply isn't synced to this
  device.
- **Built-in views** — `quest next` / `quest stale` / `quest blocked` (schema-
  defined `where`/`sort`/`limit` prefills over `quest list`, overridable per log),
  plus generic `quest list --view NAME`.
- **`quest deps <id> [--blocks]`** — walks the `blocked_by` dependency graph (a
  DAG, marking revisited nodes rather than looping or dropping edges), traversing
  qualified cross-log references.
- **Archival** — a core `archived` field, orthogonal to `status`. `quest
  archive`/`unarchive` (per quest), `quest archive-log`/`unarchive-log` (bulk,
  derived-not-stored), and `quest list --archived exclude|include|only` (default
  `exclude`), inherited by every view and `-A` sweep.

### Multi-log UX

- **`--in`/`-A` name resolution** — `--in <project-name>` resolves a log by its
  configured `project:`, in addition to a path.
- **`quest logs`** — inventories every quest log under a root: counts, `OPEN`,
  `ARCHIVED`, `git` mode, path.
- **Multi-log query UX** — repeatable `--in`/`--root`, per-log table grouping,
  and a stderr summary block stating exactly what a query meant (injected default
  filter, active view, sort, logs swept) — a query whose answer depends on cwd or
  an implicit default must say so.
- **`--select`/`--distinct`/`--count`** on `quest list`, replacing the old
  `--columns`.

### Schema engine

- **`field_order`, typed custom fields (`enum`/`string`), field defaults
  (including `{{ macro }}` expansion), named schemas (`schema: development`,
  `extends:`), and strict-mode writes** — `quest new --set`/`quest set` reject an
  undeclared field name outright when `strict: true` (the default).
- **`readiness:`** — a schema-configurable, advisory list of rules (`quest brief`
  reads these; `quest validate` does not enforce them) replacing a hardcoded
  AFK-readiness check.
- **`agentic: afk|hitl`** demoted out of the core schema into the `development`
  schema — not every kind of work has an unsupervised-agent axis.
- **The `household` schema** — for non-software logs (`family`): renames
  `todo`/`in-progress` to `waiting`/`doing`, and drops the readiness bar to just
  requiring a description.

### Agent handoff

- **`quest brief <id>`** — a self-contained, agent-agnostic Markdown work order:
  location, spec, acceptance criteria, resolved dependencies, and the exact
  report-back commands. Two separate verdicts — `READY` (schema readiness rules)
  and `STATE` (computed blocked/terminal/archived) — so a blocked or completed
  quest still gets a full brief rather than being refused.
- **`quest new --body -`** (read the Markdown body from stdin) and **`--batch -`**
  (create N quests from a YAML list in one call, printing their ids in input
  order) — the missing inbound half to `quest brief`.

### Maintenance and DX

- **`quest commit`** — stages and commits exactly a log's `tracked:` pathspec via
  `git commit -- <pathspec>` (ignores the index, so it can't sweep in unrelated
  staged changes), deriving a deterministic message from the frontmatter diff.
  Exits non-zero on a hook failure without `--no-verify`, instead of swallowing
  it.
- **`quest validate --report FILE`** — writes findings as a Markdown note,
  deleting it when the log is clean.
- **`quest init`** now ensures `<log>/.gitignore` contains `_validation.md`
  (derived state, transported by Syncthing rather than git), and **`--template`**
  writes/regenerates an Obsidian `_template.md` from the log's merged schema.
- **Grouped `--help` output** (Capture / Query / Modify / Logs / Maintain /
  Introspect) as the CLI passed 20 verbs — no command renamed or nested.
- **`quest version` / `quest --version`** — both print `questkit <version>`
  from the one source of truth (`questkit.__version__`, read from the
  installed package's own metadata). Fixed a real drift bug found while
  adding this: `__init__.py` had been hand-duplicating the version string
  and was already stale (`0.2.0`) against `pyproject.toml`'s `0.3.0`.
- **`quest migrate`** — frontmatter-aware corpus migrations (`--backfill`,
  `--rename-value`), with `--dry-run` and `--commit`.
- **`Quest.save()`** now writes only when the rendered content actually changes,
  which is what makes an unattended committer (and Syncthing) safe to run
  against a log nobody is actively editing.
- `quest validate` splits **errors** (block the exit code) from **notes**
  (informational — e.g. filename slug drift after a title edit, which is
  expected and not a defect).

### Deliberately deferred to 0.5.0

Two pieces of v0.3 scope are infrastructure this repository can't deploy or test
from inside itself, and were split into their own quests rather than blocking
the release:

- [[QST-kxo5m--realm-01-designated-committer-timer-and-git-auto-unification]] —
  reimplementing `git: auto` on top of `quest commit`, and deploying the
  realm-01 systemd timer that commits Obsidian-authored quest changes.
- [[QST-9bsnv--obsidian-template-distribution-via-topology-yaml-and-home-assistant-capture]]
  — distributing `_template.md` via `topology.yaml`, and a Home Assistant
  capture/view integration for the family log.

## [0.2.0]

[[QST-v0hnq--questkit-v2-dynamic-schema-engine-and-multi-log-architecture]] —
the dynamic per-log schema engine (custom vocabularies and fields declared in
`.questkit.yaml`), and the multi-log architecture: global-id resolution for
`show`/`set`/`done`/`mv` across every discoverable log, and `QST_ROOT`-rooted
cross-log discovery.

## [0.1.0]

[[QST-whm2e--questkit-design-blueprint-for-file-based-quest-tracking]] — the
founding design: one Markdown file with YAML frontmatter per quest, immutable
random ids, nearest-zone-wins log discovery, and the one-log-per-command rule.
