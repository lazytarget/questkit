# questkit

File-based quest tracking: one Markdown file with YAML frontmatter per unit
of work, stored in plain `quests/` directories across as many Git/Syncthing
zones as you like. Built to be equally comfortable for humans (Obsidian,
VS Code, plain `ls`/`grep`) and AI agents (structured frontmatter, a small
CLI, no server, no database).

A **quest** is questkit's unit of work: `QST-<id>--<slug>.md`. Side quests
and epics are just quests with a `type`/`blocked_by` relationship — the
noun scales from "buy stamps" to "rebuild the deploy pipeline."

> This README is the pitch and the quickstart. For implementation detail,
> rationale, the full CLI/config/frontmatter reference, multi-zone setup,
> Git/Syncthing versioning, hooks, IDE integration, and agentic support in
> depth, see **[docs/questkit.md](docs/questkit.md)**.

## Install

```bash
pip install -e .          # from this repo, for development
# or, once published:
pip install questkit
```

This installs two identical entry points, `quest` and `qst` (pick whichever
you'd rather type), plus `quest-format`, `quest-validate`, and
`quest-bump-modified` for use as pre-commit hooks.

## Quickstart

```bash
cd some-project
quest init                     # creates quests/.questkit.yaml here
quest new "Fix the garage door sensor"
quest list                     # defaults to todo, in-progress, blocked
quest set QST-x7k2m priority=high
quest done QST-x7k2m
quest validate
```

## How it resolves which log to use

For every command, in order:

1. `--in DIR` — explicit override.
2. Walk up from the current directory looking for a `.questkit.yaml` marker
   — either directly in an ancestor, or in that ancestor's `quests/` child.
   This is "nearest zone wins": running `quest new` inside a project that
   has opted in always lands the file there, with no filing decision.
3. The `QUEST_LOG` environment variable, pointed at your central/catch-all
   log.
4. An actionable error telling you to run `quest init` or set `QUEST_LOG`.

A directory only becomes a quest log by containing `.questkit.yaml` — a
bare `quests/` folder with no marker is just a folder. `quest init [DIR]`
creates the marker (and the directory, if needed); it's idempotent and
never overwrites an existing config.

## Querying and mutating across logs

`quest list` is a small filter/export engine, not a fixed set of flags:

```bash
quest list --where "status=todo,in-progress"                # comma = OR within a field
quest list --where "tags~frontend" --where "tags~urgent"     # repeated --where = AND
quest list --all --format json | jq '.[].title'              # every log under QST_ROOT
quest list --format prompt                                   # compact, agent-friendly digest
quest schema quest status                                    # valid values, so nothing's guessed
```

`--all` aggregates from every log found downward from `QST_ROOT` (an env
var — the sweep-root analogue of `QUEST_LOG`), the git root, or the
current directory. Because ids are globally unique, targeted mutations
are location-independent too: `quest set`/`show`/`done <id>` check the
nearest log first, then sweep every other log under that same root if the
id isn't there — `--in` remains available to force a single log, but
isn't required to reach one elsewhere. See
**[docs/questkit.md](docs/questkit.md)** for the full `--where` grammar,
column/sort/format options, and resolution order.

## Frontmatter

```yaml
---
id: QST-x7k2m
title: Human-readable title
description: One-line purpose — omit while status is draft
created: 2026-08-13
modified: 2026-08-13
type: task                    # feature | task | bug | epic | chore
tier: spark                    # spark | brief | blueprint — optional
status: draft                  # draft | todo | in-progress | parked | done | scrapped
priority: medium               # critical | high | medium | low | deferred
effort: m                      # xs | s | m | l | xl — optional
owner: alex                    # free text — whose quest this is
project: some-project          # optional; stamped from the log's own config, if it declares one
tags: []
blocked_by: []                  # ids this quest is blocked by
aliases: [QST-x7k2m]             # surfaces the short id in Obsidian search/quick-switcher/autocomplete
---
```

`agentic: afk | hitl` is not shown above — it is not a core field. It is
declared by the `development` schema (`schema: development` in a log's
`.questkit.yaml`), because "can an agent run this unsupervised" is not a
universal vocabulary; household work has no such axis.

### Cross-referencing other quests in Obsidian

`aliases` does **not** make a bare `[[QST-x7k2m]]` link resolve on click —
Obsidian's wikilink resolver only reads filenames, not frontmatter aliases
(confirmed upstream gap, not a settings/plugin issue). Use the full filename
instead, with no pipe:

```markdown
[[QST-x7k2m--fix-garage-door]]
```

This resolves correctly (a real filename match) and reads better than a
piped short form — a descriptive slug is faster for a human to recognize
than a bare id, and it's fewer characters for an agent to read, not more.
Aliases still earn their keep elsewhere: type `[[QST-x7k2m`, Obsidian's
autocomplete matches on the alias and inserts the full link for you.

This is also vault-scoped: wikilinks cannot resolve across separate
Obsidian vaults at all, so a cross-reference between quests in different
zones/logs only resolves when a vault containing both is open (e.g. a
realm-root vault nesting every zone) — never when a narrower, per-zone
vault is open. For a genuinely cross-zone reference, prefer plain text
(`QST-x7k2m`, greppable and `quest show`-able) over a wikilink that will
silently fail to resolve in the common case.

### Frontmatter formatting

`Quest.save()` normalizes every quest file the same way, deliberately
matching Obsidian's own frontmatter writer instead of fighting it (a file
that alternates between the CLI's and Obsidian's preferred style every
time it changes hands is pure diff noise):

- Every list-valued field (`tags`, `blocked_by`, `aliases`, ...) renders
  flow style (`[]`) only when empty; any non-empty list — even a single
  item — expands to block style (one per line).
- `created`/`modified`/`due` become real `date` values, so they dump as a
  bare `2026-08-13` instead of being auto-quoted for type safety.
- Any single-quoted string converts to double-quoted.

This happens on every save, so a hand-edited or Obsidian-touched file that
doesn't follow it self-corrects the next time any `quest` command touches
it — no separate lint-and-fix step needed in the common case. To normalize
a whole log in one shot (after first adopting these rules, or a log with
no git at all), run `quest format [--in DIR]`; the `quest-format`
pre-commit hook does the same for staged files on every commit (see
[docs/questkit.md §11](docs/questkit.md#11-git-hooks-and-validation)).

`agentic: afk` is a claim, not a declaration — but `quest validate` no longer
checks it. That check now lives in a schema's `readiness:` block (advisory,
not commit-blocking): the `development` schema requires a `## Spec`/`##
Design` section and an `## Acceptance Criteria` checklist before treating an
AFK quest as handoff-ready. See [docs/questkit.md §13](docs/questkit.md#13-agentic-support).

### What else `quest validate` checks

Beyond required fields and enum membership: that the log's declared
`project` (if any) matches each quest's own `project:`; that the filename's
id matches frontmatter `id` and `aliases` includes it; that the filename's
slug is still consistent with a freshly-slugified `title` (informational —
filenames are immutable by design, so this reports drift rather than
implying a rename, e.g. after a `quest set ... title=...` edit); and that
every `blocked_by` id and every `[[QST-xxxxx...]]` wikilink in the body
actually resolves to a file in the current log (code spans and fenced code
blocks are skipped, since those are usually syntax examples, not real
references). All of it is scoped to the one log being validated — there's
no cross-log reference concept, matching the vault-boundary limitation
above.

`owner` is intentionally free text, not a closed enum — questkit doesn't
know who's on your team.

## Config (`.questkit.yaml`)

Lives inside the `quests/` directory it governs, so a log is a portable,
self-contained unit:

```yaml
version: 1
pattern: "QST-*.md"
prefix: "QST-"
id_length: 5
git: manual            # auto | manual — see below
project: some-project  # optional; omit for a catch-all/central log
defaults:
  type: task
  status: draft
  priority: medium
ignore:                # directory names/globs pruned during a cross-log sweep
  - dist
schema:                 # override vocabularies and/or add custom fields — optional
  statuses: [draft, todo, in-progress, in-review, shipped, cancelled]
  terminal_statuses: [shipped, cancelled]
  fields:
    sprint:
      type: string
      required: true
```

`git: manual` (the default) means questkit never touches git — committing
quest changes is on you (or your existing agent/commit conventions).
`git: auto` makes `new`/`set`/`done` commit their own change, pathspec-
limited to the touched file, skipping with a warning rather than failing
if the repo is in a state that blocks committing (mid-merge, mid-rebase,
etc). It's a reasonable default for a log whose *only* content is quest
files; riskier for a log living inside a code repo, where you usually want
one commit pairing the code change with the ticket update.

### Custom fields and per-log schema

`schema:` is entirely optional — a log with no block behaves exactly like
today's hardcoded vocabulary. When present, `types`/`statuses`/`tiers`/
`priorities`/`efforts` override the built-in enums (an `extends: <path>`
key can chain in a shared schema file first, with sibling keys fully
replacing whatever it inherits), and `fields:` declares custom frontmatter
fields with a `required` flag. `quest new` null-initializes every declared
field and warns on stderr; `quest validate` fails if a `required: true`
one is still null or missing. `ignore:` (optionally `#include <path>` to
reuse a shared ignore-pattern file) extends the default prune list for
cross-log sweeps, scoped to that log's own project.

Use `quest schema quest [field] [--format json|table]` to introspect the
active, merged schema for a log — the whole thing, or just one field's
valid values/spec — instead of guessing or reading the YAML chain by hand.

## `quest init` flags

- `--project NAME` — declare this log's project, stored in its config. Once
  set, `quest new` stamps it automatically and `quest validate` flags any
  quest whose own `project:` field disagrees with it.
- `--git auto|manual` — set this log's git mode at init time (defaults to
  `manual` if omitted; see "Config" above).
- `--base` — scaffold `quests.base`, an Obsidian Bases kanban/table view.
  Skipped (not overwritten) if one already exists. Obsidian Bases is a
  fairly new file format; treat the generated file as a starting point, not
  a guarantee — check it opens the way you expect.
- `--hooks` — wire questkit's own pre-commit hooks (`quest-format`,
  `quest-validate`, `quest-bump-modified`, in that order) into this repo's
  `.pre-commit-config.yaml`,
  creating the file if it doesn't exist, and run `pre-commit install`. A
  no-op (with a message) outside a git repo. Structural, not marker-based:
  re-running it never duplicates the entry. References questkit by local
  path until it has a real Git remote to pin a release tag against.

All of `quest init`'s effects are idempotent — re-running it any number of
times converges to the same state and never overwrites something you've
already customized.

## What's deliberately not here

- **No recurrence.** Recurring work (weekly chores, monthly reports)
  deserves its own design, not a bolt-on field; keep using cron/calendar/
  whatever you already have for that.
- **No status-history log, no server, no database.** The Markdown file is
  the record. `git log` is the audit trail if you want one.
- **No hardcoded taxonomy of people.** `owner` is free text.

## Development

```bash
uv venv
uv pip install -e ".[dev]"
pytest
ruff check .
```
