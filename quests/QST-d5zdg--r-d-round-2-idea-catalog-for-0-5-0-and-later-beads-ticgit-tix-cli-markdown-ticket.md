---
id: QST-d5zdg
title: "R&D round 2: idea catalog for 0.5.0 and later (Beads, TicGit, tix-cli, markdown-ticket)"
description: Review pass over a numbered idea catalog drawn from four comparable tools and the unattended-runner work, turning accepted ideas into quests for 0.5.0 and later
project: questkit
type: task
status: todo
priority: medium
tags:
  - questkit
  - planning
  - agentic
created: 2026-10-14
modified: 2026-10-16
agentic: hitl
aliases:
  - QST-d5zdg
blocked_by: []
component: cli
effort: m
milestone: 0.5.0
related_adrs:
tier: brief
---

## Description

Second R&D round for questkit, aimed at **0.5.0 and later**, in the same style as the
August catalog ([[../docs/planning/rd_ideas_2026-08-21]]): numbered ideas with stable IDs, grounded in
what the repo does today, each with a suggested milestone and size, then a review pass
that records a disposition per ID and turns accepted ideas into quests.

This round is prompted by the unattended-runner work
([[QST-2z8db--unattended-afk-quest-runner-worktree-implement-pr-in-gitea]],
[[QST-u90gs--personalised-implement-quest-skill-for-epic-and-blueprint-quests]]) and by
four comparable tools:

- [Beads](https://github.com/gastownhall/beads) and its orchestrator
  [Gas Town](https://github.com/gastownhall/gastown): agent-first graph tracker,
  atomic claim, gates, formulas/molecules, multi-agent supervision;
- [TicGit](https://github.com/schacon/ticgit): the closest in spirit; agent output
  discipline, versioned JSON contract, `review` state;
- [tix-cli](https://github.com/nicolaou-dev/tix-cli): stale (last default-branch commit
  2025-09-03) and partly unimplemented, but git-style external subcommands are worth
  capturing;
- [markdown-ticket](https://github.com/andkirby/markdown-ticket): Markdown tickets in the
  repo, MCP with section-level tools, spec-driven pipeline; mostly a different problem.

## Spec

The research and first-pass catalog are done and live in
[[../docs/planning/rd_ideas_2026-10-14]] (`docs/planning/rd_ideas_2026-10-14.md`): 15 ideas across
`RUN`, `CLM`, `EPC`, `WFL`, `EXT`, `AGT` and `STO`, a findings section per tool, a
"considered and not proposed" table, the existing quests whose context changed, and a
suggested order. Remaining work on this quest is the **human review pass** (hitl):

1. Peter answers the five open questions at the end of the catalog.
2. A disposition per ID is appended to the catalog (same table format as round 1).
3. Accepted ideas become quests in this log, linked back by ID, milestone set per the
   disposition; rejected ones keep the evidence that would reopen them.
4. Context changes for existing quests (the table in the catalog) are applied or
   declined, one by one.

Headline findings to react to first:

- **EXT-1** external `quest-<name>` subcommands would settle where the runner lives
  without growing core.
- **CLM-1** re-examines the August AX-4 rejection: the runner partly meets its reopen
  trigger, but the recommendation is branch-as-claim in the runner, nothing in core yet.
- **EPC-1** epic membership through the generic ref field (QST-698og); touches a v3
  decision, so it needs an explicit yes or no.
- **STO-1** where quest edits land during a worktree run; the competing tools avoid the
  problem by storing tickets outside the code tree.
- **AGT-2** questkit has no documented JSON output contract, and the MCP server and runner
  are about to depend on one.

## Acceptance

- [ ] The five open questions in the catalog are answered
- [ ] Every idea ID in `rd_ideas_2026-10-14.md` has a recorded disposition
- [ ] Accepted ideas exist as quests with `milestone` 0.5.0 or later and a link to the idea ID
- [ ] The "existing quests whose context changed" table is resolved, each row applied or declined
- [ ] The catalog's `modified` date and status reflect the review

## Log

- 2026-10-14: catalog drafted from reading the four projects (README/docs plus GitHub API metadata); several repo-specific facts verified in this repo (batch refs, JSON contract, epic modelling); nothing reviewed yet

