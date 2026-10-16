---
id: QST-u90gs
title: Personalised /implement-quest skill for epic and blueprint quests
description: A Realm-native fork of Matt Pocock's /implement-spec that implements an epic or blueprint quest on an integration branch with parallel worktree subagents, quest lifecycle transitions and a Gitea PR
project: questkit
type: feature
status: draft
priority: medium
tags:
  - questkit
  - agentic
  - skills
created: 2026-10-14
modified: 2026-10-16
agentic: hitl
aliases:
  - QST-u90gs
blocked_by: []
component: cli
effort: m
milestone:
related_adrs:
tier: brief
---

## Description

Matt Pocock's skills v1.3 added `/implement-spec`, a coordinating-agent skill that
implements a whole spec (a dependency graph of tickets) on one integration branch with
parallel implementer subagents, one worktree each, then a code review. It is the right
shape for a `type: epic` or `tier: blueprint` quest, but it is generic: it assumes an
issue tracker configured through `/setup-matt-pocock-skills`, it prefers a branch over a
PR, and it knows nothing about quests, the `quest(<zone>):` commit prefix, the Realm
worktree convention, Gitea or `ship.py`.

This quest builds a **personalised `/implement-quest`** skill that does the same job
natively in the Realm: the epic or blueprint quest is the spec, its child quests are the
tickets, `blocked_by` is the graph, and quest status transitions are how work is
"closed". It is the interactive counterpart of, and the likely harness prompt for, the
unattended runner in [[QST-2z8db--unattended-afk-quest-runner-worktree-implement-pr-in-gitea]]
(decision 8 there).

Draft, `hitl`: the fork-versus-wrap and tracker-semantics decisions below need a
grilling session against the actual upstream SKILL.md before this can be groomed.

Upstream references (read 2026-10-14): `skills/engineering/implement-spec/SKILL.md`,
`skills/engineering/pr/SKILL.md`, `skills/engineering/code-review/SKILL.md` and
`skills/engineering/tdd/SKILL.md` in github.com/mattpocock/skills (v1.3.x).

## Decisions to make

### 1. Fork, wrap, or configure?

| Option | For | Against |
|--------|-----|---------|
| Configure upstream `/implement-spec` for a quest tracker | Zero authored code, tracks upstream | Needs a questkit tracker adapter in `/setup-matt-pocock-skills`; no place for Realm rules; cross-skill calls to user-invoked skills are blocked in v1.3 |
| Wrap: a thin `/implement-quest` that says "follow implement-spec, except..." | Small, survives upstream changes | Depends on the model reading and merging two instruction sets; the Skill tool cannot load a user-invoked skill, so it would have to read the file by path |
| Fork: own full `SKILL.md` in `lazytarget/skills/realm/implement-quest/` | Full control, deterministic, no cross-skill calls | Drifts from upstream; must re-diff on upstream releases |

Precedent: `teach` was forked this way (repointed to `local:02-projects/lazytarget/skills`
on 2026-09-25). Leaning: **fork**, new name `implement-quest` (so upstream
`implement-spec` stays installed and untouched), with a short "diverges from upstream
in..." section so re-diffing is cheap. Verify the upstream licence permits it first.

### 2. Quest lifecycle semantics

What "close the ticket" means, concretely, per child quest and for the epic:

- claim: `quest set <id> status=in-progress` on the integration branch before spawning
  the implementer (also gives the runner a claim signal);
- child done: `quest done <id>` when its work is merged into the integration branch and
  its acceptance criteria are verified, with notable decisions appended to its `## Log`;
- epic done: only when the PR is merged (commit trailers, QST-22gdn, may transition it);
  until then it stays `in-progress`;
- failure: back to `todo` (or `parked` after repeated failure) with a log entry, never
  left `in-progress` and orphaned.

Decide who writes quest-file changes: the coordinator only (avoids merge conflicts in
`quests/` between parallel implementers) is the leaning.

### 3. Graph and frontier from questkit

Compute the frontier with questkit rather than reading files: `quest deps <epic>`,
`quest next --where ...`, `quest brief <id>` for each ticket prompt (READY/STATE lines
decide whether to start it). Check how epic-to-child is modelled (no parent field;
the workflow README says epics relate to children through `blocked_by`) and whether a
`--format json` projection exists that is stable enough to parse. Anything missing
becomes a questkit follow-up quest, not logic in the skill.

### 4. Realm conventions the skill must enforce

- one integration branch per epic named from the quest id (`quest/QST-xxxxx-slug`);
  implementer worktrees under `<repo>-worktrees/<branch>/` (not `.claude/worktrees`
  unless Claude Code created them), removed at the end including on failure;
- push to the `gitea` remote after every commit; never push a mirror remote;
- Conventional Commits; `quest(<zone>):` prefix for quest-only changes; check the
  quest log's `.questkit.yaml` `git:` mode before double-committing;
- subagent prompts carry the Realm brief, because `CLAUDE.local.md` and `.realm/` are
  untracked and absent inside fresh worktrees (open item in omnigent-realm-workflow.md);
- scratch files and exploration notes under `.temp/` at the Realm root, cleaned up;
- worktrees are not an access fence, so implementer prompts forbid touching other
  checkouts and share state only through commits.

### 5. Finish: review, PR, never merge

End with `code-review` on the integration branch (spec-fidelity check against the
quest's acceptance criteria, not only coding standards), then compose the PR body with
`/pr`'s Summary / Evidence / Merge Danger structure plus a quest-linkage block, and open
it through `ship.py` (Gitea PR, the bot cannot approve its own PR). The skill never uses
`--merge`. Decide whether it opens a draft PR after the first merge (upstream's path)
or only at the end. A one-way-door verdict from the Merge Danger section keeps the PR
draft.

### 6. Invocation and scope

User-invoked only (`disable-model-invocation: true`, same as `ship`). Decide whether it
also handles a single `spark`/`brief` quest (one agent, one worktree, no subagents) or
leaves those to the existing `implement` skill; leaning: epic/blueprint only, and
refuse politely otherwise with a pointer to `implement`.

## Spec

Not yet groomed. First deliverable once decisions 1 to 6 are made:
`02-projects/lazytarget/skills/realm/implement-quest/{SKILL.md,README.md}`, listed in
`realm/README.md` and the package `README.md`, installed by `make apply-skills`, and
exercised once against a real small epic in this log.

## Acceptance

- [ ] Decisions 1 to 6 are resolved and recorded in this quest's `## Log`
- [ ] `realm/implement-quest/SKILL.md` and `README.md` exist in `lazytarget/skills`,
      with a "diverges from upstream" section and a link to the upstream SKILL.md version it forked
- [ ] `implement-quest` is declared in `99-system/skills.yaml` with
      `source: "local:02-projects/lazytarget/skills"`, `path: realm/implement-quest/SKILL.md`
      and `link: false` (same rationale as `ship`, `memorize` and `teach`), and
      `make plan-skills` shows no drift
- [ ] The upstream skills it relies on (`implement-spec` for reference, `pr`, `retro`,
      `tdd`, `code-review`, `writing-for-agents`) are declared in `99-system/skills.yaml`
- [ ] A dry run on a real epic produces an integration branch, worktrees for each ticket
      that are removed afterwards, quest transitions via the CLI, and one Gitea PR with a
      `/pr`-style body that is never auto-merged
- [ ] `/retro` is run on that dry-run session and its ranked findings are captured as quests
- [ ] QST-2z8db decision 8 references the finished skill as the epic/blueprint harness prompt

## Log

- 2026-10-14: captured from Matt Pocock's skills v1.3 review; no `quests/` log exists in `lazytarget/skills`, so the quest lives in the questkit log (the runner is the first consumer) and the skill itself will be authored in `lazytarget/skills`

