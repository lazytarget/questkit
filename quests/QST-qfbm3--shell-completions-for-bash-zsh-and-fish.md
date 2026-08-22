---
id: QST-qfbm3
title: Shell completions for bash zsh and fish
description: quest completion <shell> generating completions, with dynamic completion of quest ids, project names, and schema fields where feasible.
project: questkit
type: feature
status: todo
priority: high
tags:
  - questkit
  - cli
  - dx
created: 2026-08-22
modified: 2026-08-22
agentic:
aliases:
  - QST-qfbm3
blocked_by: []
component:
effort: m
milestone: 0.4.0
related_adrs:
---

## Spec

`quest completion bash|zsh|fish` prints a completion script to stdout
(the `gh completion` convention — user eval's it from their shell rc).
Static completion of subcommands and flags; dynamic completion of:

- quest ids (from the resolved log / sweep — must stay fast; consider
  completing from the nearest log only)
- project names for `--in`
- field names for `--where`/`--select`/`--sort` (core + declared custom)

Investigate whether argparse introspection or a hand-maintained spec is
the more sustainable source; `qst` must get the same completions.

## Acceptance Criteria

- [ ] `quest completion <shell>` for bash, zsh, fish
- [ ] Dynamic id + project-name completion, sub-100ms
- [ ] Works for both `quest` and `qst`
- [ ] Install instructions in README

## Log

- 2026-08-22: captured from R&D catalog CLI-1, accepted for 0.4.0
