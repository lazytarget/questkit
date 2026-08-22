---
id: QST-grmbv
title: Quest edit opens the resolved quest in the editor
description: quest edit <id> opens the resolved quest file in $EDITOR — parity with quest new --edit, same id resolution as show.
project: questkit
type: feature
status: todo
priority: medium
tags:
  - questkit
  - cli
  - dx
created: 2026-08-22
modified: 2026-08-22
agentic:
aliases:
  - QST-grmbv
blocked_by: []
component:
effort: xs
milestone: 0.4.0
related_adrs:
---

## Spec

`quest edit <id> [--in LOG ...]`: resolve exactly like `quest show`
(nearest-then-sweep, `--in` as bounded set), open the file in `$EDITOR`.
No `$EDITOR` set → the same skip-with-message behavior as `new --edit`.
After the editor exits: re-save through `Quest.save()` so hand edits are
normalized immediately (same guarantee as every other write path).

## Acceptance Criteria

- [ ] `quest edit <id>` with show-style resolution
- [ ] Post-edit normalization via `Quest.save()`
- [ ] Clean message when `$EDITOR` unset
- [ ] Tests + docs

## Log

- 2026-08-22: captured from R&D catalog CLI-2, accepted for 0.4.0
