---
id: QST-reakz
title: quest-bump-modified stages its own bump instead of failing the commit
description: Stage the modified-date bump and pass with one informational line, so a stale date no longer fails the commit and forces a second attempt.
project: questkit
type: feature
status: todo
priority: medium
tags:
  - questkit
  - hooks
  - dx
created: 2026-10-02
status_changed: 2026-10-02
modified: 2026-10-08
agentic: afk
aliases:
  - QST-reakz
blocked_by: []
component:
effort: s
milestone: 0.4.0
related_adrs:
---

## Description

Committing a hand-edited quest takes two attempts. `quest-bump-modified`
rewrites `modified` to today, and pre-commit marks any hook that leaves files
changed as **Failed**, whatever its exit code. The hook already returns 0
(`src/questkit/hooks.py`, `bump_modified_main`). Nothing about a stale
`modified` date is an error, yet every commit of a raw edit (Obsidian, another
agent, a Syncthing arrival) aborts and has to be re-staged and re-run. Hit
again on 2026-10-02 committing QST-f0329/QST-oe92z.

## Spec

pre-commit fails a hook when it leaves **unstaged** changes in the working
tree. There is no setting to disable that, so the hook avoids it:

- **Stage its own edit.** After saving a bumped file, run `git add <path>`.
  No unstaged diff remains, pre-commit reports Passed, and the bump goes into
  the same commit. `git add` writes to the index git is using, including the
  temporary one behind `git commit <paths>`.
- **Say what it did.** One line per changed file, e.g.
  `[quest-bump-modified] QST-nxxk8…md: modified 2026-10-01 → 2026-10-02`, and
  likewise for a `status_changed` backfill. Nothing when the date was already
  today.
- **Make the line visible.** pre-commit hides output from passing hooks, so set
  `verbose: true` in both `.pre-commit-hooks.yaml` and this repo's
  `.pre-commit-config.yaml`. Cost: a hook-id/duration header on every run.
- **Only bump files that actually changed.** Today the hook bumps every file
  it is given, so `pre-commit run --all-files` re-dates the whole corpus (and,
  with staging, would stage it). Bump and stage only files whose content
  differs from `HEAD`, reusing `_previous_quest`. A brand-new quest (no `HEAD`
  version) still counts as changed.

Out of scope: `quest-format` keeps failing when it reformats. A reformat is a
content change worth seeing, unlike a date bump.

### Edge cases

- Unstaged edits in the same file: pre-commit stashes them while hooks run.
  If the stash touches the `modified:` line itself, restoring it conflicts and
  pre-commit rolls back the working tree. The committed bump stays correct.
- Consumer repos run this through `.pre-commit-hooks.yaml`, so they get the
  change once their `rev:` pin is bumped.

## Acceptance Criteria

- [ ] Committing a quest with a stale `modified` succeeds in one attempt, with the bump included in the commit
- [ ] One informational line per bumped file, showing old → new date; silent when nothing changed
- [ ] `verbose: true` set in `.pre-commit-hooks.yaml` and `.pre-commit-config.yaml`
- [ ] Files whose content matches `HEAD` are neither bumped nor staged, so `pre-commit run --all-files` is a no-op on an unchanged corpus
- [ ] `status_changed` backfill still works and is staged the same way
- [ ] Works with `git commit`, `git commit -a` and `git commit <paths>`
- [ ] Tests in `tests/test_hooks.py` cover staging, the unchanged-file no-op and a new quest

## Log

- 2026-10-02: captured after the bump hook forced a second commit attempt on `b35421b`
