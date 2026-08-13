# questkit

File-based quest tracking: one Markdown file with YAML frontmatter per unit
of work, stored in plain `quests/` directories across as many Git/Syncthing
zones as you like. Built to be equally comfortable for humans (Obsidian,
VS Code, plain `ls`/`grep`) and AI agents (structured frontmatter, a small
CLI, no server, no database).

A **quest** is questkit's unit of work: `QST-<id>--<slug>.md`. Side quests
and epics are just quests with a `type`/`blocked_by` relationship — the
noun scales from "buy stamps" to "rebuild the deploy pipeline."

## Install

```bash
pip install -e .          # from this repo, for development
# or, once published:
pip install questkit
```

This installs two identical entry points, `quest` and `qst` (pick whichever
you'd rather type), plus `quest-validate` and `quest-bump-modified` for use
as pre-commit hooks.

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

## Frontmatter

```yaml
---
id: QST-x7k2m
title: Human-readable title
description: One-line purpose — omit while status is draft
created: 2026-08-13
modified: 2026-08-13
type: task                    # feature | task | bug | epic | milestone | chore
tier: spark                    # spark | brief | blueprint — optional
status: draft                  # draft | todo | in-progress | blocked | parked | completed | scrapped
priority: medium               # critical | high | medium | low | deferred
effort: m                      # xs | s | m | l | xl — optional
owner: alex                    # free text — whose quest this is
agentic: hitl                  # afk | hitl — optional; can an agent run this unsupervised?
project: some-project          # optional; stamped from the log's own config, if it declares one
tags: []
blocked_by: []                  # ids this quest is blocked by
aliases: [QST-x7k2m]             # so [[QST-x7k2m]] wikilinks resolve despite the slug
---
```

`agentic: afk` is a claim, not a declaration — `quest validate` checks that
an AFK quest actually carries a `## Spec`/`## Design` section and an
`## Acceptance Criteria` checklist before treating it as handoff-ready.

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
```

`git: manual` (the default) means questkit never touches git — committing
quest changes is on you (or your existing agent/commit conventions).
`git: auto` makes `new`/`set`/`done` commit their own change, pathspec-
limited to the touched file, skipping with a warning rather than failing
if the repo is in a state that blocks committing (mid-merge, mid-rebase,
etc). It's a reasonable default for a log whose *only* content is quest
files; riskier for a log living inside a code repo, where you usually want
one commit pairing the code change with the ticket update.

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
- `--hooks` — wire questkit's own pre-commit hooks (`quest-validate`,
  `quest-bump-modified`) into this repo's `.pre-commit-config.yaml`,
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
