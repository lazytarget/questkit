---
id: QST-mjuau
title: Quest.save() writes only when the rendered content changes
description: quest format and quest set rewrite files unconditionally, churning mtimes across Syncthing and destroying the quiescence signal a timed committer needs.
project: questkit
type: bug
status: done
priority: high
tags:
  - questkit
  - cli
  - sync
created: 2026-08-19
status_changed: 2026-08-19
modified: 2026-08-20
agentic: afk
aliases:
  - QST-mjuau
blocked_by: []
effort: s
milestone: 0.3.0
tier: spark
---

## Description

`commands/format_cmd.py` reads each file, calls `quest.save()` **unconditionally**,
then re-reads and diffs before/after only to decide what to *print*. `hooks.py`'s
`format_main` (the `quest-format` pre-commit entry point) has the identical
pattern. So a single `quest format` run rewrites every file in the log even when
nothing changes — 66 files in `grocy-ecosystem`, every time.

Two consequences, one of which blocks other work:

1. **Syncthing churn.** N mtime changes propagate to every device on every run.
2. **The debounce eats itself.** Any timed committer (see [[QST-e6g6t--quest-commit-and-the-designated-committer]]) gates on
   "has this log been quiet for N minutes", which means asking the filesystem
   for recent mtimes. After a no-op `quest format`, every file in the log is
   freshly touched — so the next run's quiescence check sees a hot log and skips,
   forever.

`commands/set_cmd.py` has the same class of bug from the other direction:
`modified` is stamped unconditionally before `save()`, so
`quest set QST-x status=todo` on a quest **already** `todo` bumps `modified`,
rewrites the file, and in a `git: auto` log produces an empty commit. Agents
re-asserting known state launder the corpus this way.

## Spec

### Scope

**In:** `Quest.save()`, `format_cmd`, `hooks.format_main`, `set_cmd`, and
`quest format`'s argument surface.
**Out:** frontmatter key ordering ([[QST-j68u5--schema-engine-field-order-defaults-macros-typed-fields-strict-writes]]) and `--fill-defaults` ([[QST-j68u5--schema-engine-field-order-defaults-macros-typed-fields-strict-writes]]).

### Approach

Fix it in `Quest.save()` — render to a string, compare against the file's current
content, write only on difference, return whether it wrote. Both existing call
sites and every future one then inherit the behavior. Fixing the two call sites
separately leaves the third to be written wrong later.

`set_cmd` compares each assignment against the current value and bumps `modified`
only if at least one field actually changed.

### Snippets

```python
def save(self) -> bool:
    """Normalize and write. Returns True only if the file's bytes changed."""
    ...
    content = f"---\n{buf.getvalue()}---\n\n{body}\n"
    if self.path.exists() and self.path.read_text(encoding="utf-8") == content:
        return False
    self.path.write_text(content, encoding="utf-8")
    return True
```

```
quest format                                  # the resolved log
quest format --in family                      # one named log
quest format quests/QST-3ehhu*.md             # explicit files, space-separated
quest format 02-projects/family/quests 99-system/quests   # dirs, each using its own pattern
quest format --check                          # report only, exit 1 if anything would change
```

A directory argument must resolve **that directory's** config and glob **its**
`pattern` — `pattern`/`prefix`/`id_length` are per-log config, so a hardcoded
`QST-*.md` would silently skip every quest in a log that renamed its prefix.
`hooks._schema_for` already has the "file whose parent isn't a log" fallback;
reuse it rather than writing a second one.

## Acceptance Criteria

- [x] `quest format` run twice reports 0 reformatted on the second run
- [x] File mtimes are unchanged by a no-op `quest format`
- [x] `quest set <id> status=<its current value>` writes nothing and does not bump `modified`
- [x] `quest set` with a real change bumps `modified` exactly once
- [x] A `git: auto` log produces no empty commits from a no-op `quest set`
- [x] `quest format` accepts multiple space-separated files
- [x] `quest format <dir>` expands to that log's own `pattern`, not a hardcoded glob
- [x] `quest format --check` writes nothing and exits 1 when a file would change, 0 otherwise
- [x] The `quest-format` pre-commit hook uses the same return value, not a re-read

## Log

- 2026-08-21: implemented (batch B0). `save()` now returns `bool`, with the rendering split out into `Quest.render()` so `--check` and `migrate --dry-run` can ask "what would change" through the same code that answers "what changed" — anything else drifts from `save()` and turns `--check` into a guess. `format` grew positional targets and `--check`; `set_cmd` compares each assignment against the *coerced* current value, which matters because `tags=a,b` becomes a list and dates round-trip as `date` objects, so a `str`-vs-typed comparison would call every date assignment a change. The hook's read-save-reread dance is gone. One test-design note worth keeping: the "does not bump `modified`" assertions had to backdate `modified` first — a fresh quest's `modified` is already today, so a same-day test cannot tell "did not bump" from "bumped to the value it already had", and would pass against the bug.
