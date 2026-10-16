---
id: QST-zl5xc
title: Group root commands in help output as the CLI passes 20 verbs
description: Render quest --help as labelled groups instead of one flat alphabetical list, so a 22-command CLI stays legible to humans and to agents reading it cold.
project: questkit
type: feature
status: done
priority: medium
tags:
  - questkit
  - cli
  - dx
created: 2026-08-19
status_changed: 2026-08-20
modified: 2026-10-16
aliases:
  - QST-zl5xc
blocked_by: []
effort: s
milestone: 0.3.0
tier: brief
---

## Description

v2 shipped 10 commands. v3 roughly doubles that:

```
today (10)  new list show set done mv init validate format schema
v3 adds     logs brief deps next stale blocked commit migrate
            archive unarchive archive-log unarchive-log scrap
reserved    ready upgrade
```

`argparse` renders subcommands as one flat, insertion-ordered list. At 10 that is
fine. At 22 it is a wall — and the reader who suffers most is **an agent seeing
`quest --help` cold**, which is precisely the reader questkit optimizes for
elsewhere (`--format prompt`, `quest schema`, `quest brief`).

The commands are not peers. `new`/`list`/`show`/`set`/`done` are typed daily;
`migrate`/`init`/`archive-log` are typed a handful of times ever. A flat list
gives them equal weight and no hint of which is which.

## Spec

### Scope

**In:** how `quest --help` renders. Group assignment for every command, and a
`group=` argument on the internal subparser helper.
**Out:** renaming, removing, or nesting any command; per-group `--help`; a
`quest help <topic>` concept command (worth its own quest if wanted).

### Approach

**Keep every command top-level. Group only the help output.**

```
usage: quest [-h] <command> ...

File-based quest tracking.

Capture
  new                 capture a new quest

Query
  list                list quests
  show                show a quest by id
  brief               emit a self-contained work order for a quest
  deps                render a quest's dependency graph
  next                the single most actionable quest here          (view)
  stale               quests nothing has moved in N days             (view)
  blocked             quests waiting on an open dependency           (view)

Modify
  set                 set one or more fields on a quest
  done                mark a quest done
  scrap               mark a quest scrapped
  archive             archive a quest, preserving its status
  unarchive           un-archive a quest
  mv                  move a quest to a different quest log

Logs
  init                opt a directory into a quest log
  logs                inventory every quest log under a root
  archive-log         archive every quest in a log
  unarchive-log       un-archive every quest in a log

Maintain
  validate            check quests against the schema
  format              normalize quest frontmatter
  migrate             frontmatter-aware corpus migrations
  commit              commit quest changes with a derived message

Introspect
  schema              introspect the active schema (for agents)
```

Implementation is a `HelpFormatter` subclass plus a `group=` keyword on the
internal `add_parser` wrapper. `argparse` has no native subcommand grouping, so
the formatter walks the subparser action and emits its own sections. Bounded —
roughly 40 lines and no change to argument parsing itself.

### Alternatives

| Option | Verdict | Reason |
|--------|---------|--------|
| Flat commands, grouped help | ✅ Chosen | Zero breaking change; costs nothing at the keyboard; fixes the only real problem (legibility) |
| Noun-verb nesting (`quest log ls`, `quest quest set`) | ❌ | Taxes the hot path forever. `list`/`set`/`show` are typed hundreds of times; two extra words each is a permanent bill for a one-time readability win. Also breaks every doc, script and habit. |
| Hybrid — flat hot path, nested cold path (`quest log archive`) | ❌ | Two grammars in one CLI. A reader cannot predict which commands nest without memorizing the split, which is worse than a long flat list. |
| Do nothing | ❌ | 22 undifferentiated lines, with daily commands and once-ever commands weighted identically |

**Precedent:** git has ~150 top-level commands and stays usable precisely because
`git help -a` groups them ("main porcelain", "ancillary", "plumbing") while every
command stays reachable as `git <verb>`. Same shape, same reason.

### Notes

- **`archive` vs `archive-log` land in different groups**, which is the argument
  for the hyphenated name rather than `quest archive --log NAME`: a flag typo
  cannot archive an entire log when the whole-log operation is a different verb
  in a different section. See [[QST-lcsza--archive-a-whole-quest-log-instead-of-individual-quests]].
- **Views are marked `(view)`** in the Query group, since they are prefilled
  `list` invocations ([[QST-37n0t--built-in-views-next-stale-blocked-and-quest-deps]]) and accept every `list`
  flag. The marker tells the reader that without a paragraph of explanation.
- Group order is by frequency of use, not alphabetical. Capture first because
  it is the one command a new user needs before any other.
- `ready` and `upgrade` are reserved and appear only when implemented.

## Acceptance Criteria

- [x] `quest --help` renders labelled groups in the order above
- [x] Every command appears in exactly one group
- [x] No command is renamed, removed, or nested — `quest <verb>` is unchanged for all of them
- [x] Views are marked `(view)` in the Query group
- [x] Adding a subparser without a group is a startup error, not a silent ungrouped command
- [x] `quest <command> --help` is unchanged
- [x] Output is plain ASCII and wraps sanely at 80 columns
- [x] A test asserts every registered subparser has a group

## Log

- 2026-08-20: implemented. New `src/questkit/help_groups.py`: `GroupedSubparsers` wraps the real subparsers action, requiring `group=` on every `.add(...)` call (used in place of `subparsers.add_parser(...)` throughout `cli.py`); `.validate()` — called once at the end of `build_parser()`, not lazily at `--help` time — raises `RuntimeError` naming any subcommand added by bypassing `.add(...)`, which is the actual "startup error" (a test constructs a raw subparser this way to prove it). `.formatter_class()` returns a `HelpFormatter` subclass that special-cases the one subparsers pseudo-action (identity-compared, not type-compared, so a nested subparsers action elsewhere would render normally) and renders it grouped by `GROUP_ORDER`, appending `(view)` for views. `commit`/`brief` will get group assignments when [[QST-e6g6t--quest-commit-and-the-designated-committer]]/[[QST-xk7js--quest-brief-a-self-contained-work-order-and-the-batch-capture-that-feeds-it]] ship. 7 new tests in `tests/test_help_groups.py`.
- 2026-08-19: captured. Trigger was counting the v3 command set: 10 today, 22 after v3, on an argparse default that renders them as one flat list.

