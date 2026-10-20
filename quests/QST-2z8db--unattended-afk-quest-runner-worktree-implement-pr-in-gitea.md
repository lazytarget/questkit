---
id: QST-2z8db
title: "Unattended AFK quest runner: worktree, implement, PR in Gitea"
description: Design and build a runner that takes the next agentic=afk quest, implements it in a worktree via an AI harness, updates the quest and opens a Gitea PR with an Omnigent session link
project: questkit
type: feature
status: draft
priority: medium
tags:
  - questkit
  - agentic
  - automation
  - ci
created: 2026-10-13
modified: 2026-10-20
agentic: hitl
aliases:
  - QST-2z8db
blocked_by: []
component: cli
effort: l
milestone:
related_adrs:
tier: brief
---

## Description

`quest brief` produces a self-contained work order and `agentic: afk` marks a quest
as safe to hand off, but nothing closes the loop: a human still has to copy the
brief into an agent, make a worktree, run it, update the quest and open the PR.
This quest designs and builds the **unattended runner** that does all of that:

1. pick the next implementation-ready `agentic: afk` quest
   (`quest next --where agentic=afk`, or an explicit id),
2. render its work order (`quest brief <id>`),
3. create a Git worktree and branch for it,
4. hand the brief to an implementation agent,
5. update the quest (`status`, `## Log`, commit with the `quest(<zone>):` prefix),
6. push to `gitea` and open a PR for human review (never merge).

Draft, `hitl`: this is mostly an open design question. The decisions below must be
made (a grilling session is the natural way) before it can be groomed to `afk`.

Related: [[QST-xk7js--quest-brief-a-self-contained-work-order-and-the-batch-capture-that-feeds-it]],
[[QST-79rt8--quest-ready-a-scriptable-readiness-predicate]] (the `quest ready && ...` primitive this wants),
[[QST-nxxk8--expose-questkit-as-an-mcp-server-with-purpose-specific-tools]],
[[QST-tf4wc--github-actions-ci-for-the-questkit-repo]], [[QST-8hq61--reusable-ci-recipe-for-repos-hosting-a-quest-log]],
[[QST-22gdn--commit-trailers-transition-quests-from-code-repos]],
[[QST-u90gs--personalised-implement-quest-skill-for-epic-and-blueprint-quests]] (epic/blueprint harness skill),
[[QST-d5zdg--r-d-round-2-idea-catalog-for-0-5-0-and-later-beads-ticgit-tix-cli-markdown-ticket]]
(prior art from Beads/Gas Town and others: EXT-1 bears on decision 1, CLM-1 and STO-1 on decision 4).
Background: `99-system/docs/omnigent-realm-workflow.md` (worktrees, ship flow, tea + omnigent bot user).

## Decisions to make

Each has a leaning, not a verdict. Scope rules from the questkit philosophy apply:
lean core, mechanism in the CLI and scheduling outside, Realm specifics stay out of
CLI verbs, Gitea (not GitHub) is the target.

### 1. Shape: CLI command, CI workflow, or agent tool/MCP?

| Option | For | Against |
|--------|-----|---------|
| Standalone runner script (stdlib Python, one cross-platform file) that pipes `quest next` / `quest brief` into a harness | Testable locally, one implementation, CI and humans both call it, keeps questkit core lean | Another artifact to own and install |
| New `quest run`/`quest dispatch` verb | Discoverable | Violates "lean core / flags over verbs"; drags worktree, Gitea and harness logic into questkit |
| Gitea Actions workflow only | Free scheduling, runner already exists | Hard to debug, logic trapped in YAML, cannot be run by hand |
| MCP tool (`quest mcp`) | Lets an interactive agent say "run this quest" | MCP is for an agent to query/mutate quests; spawning other agents from a tool call is the wrong layer, and QST-nxxk8 is already scoped narrowly |

Leaning: **runner script outside the CLI core** (lives in the Realm scripts or a
sibling tool importing questkit as a library, like `ship.py`), with a Gitea Actions
workflow and a manual invocation as two thin callers of the same script. Questkit
itself only gains what the runner needs (likely `quest ready`, QST-79rt8, and maybe a
`--format json` field on `brief`); nothing agent-specific goes into the CLI.

### 2. Which AI harness?

Candidates: Claude Code headless (`claude -p`), an Omnigent-launched session,
Codex/Gemini CLI. Decide whether the runner has a **harness adapter interface**
(one small function: brief in, exit status + transcript pointer out) with a default,
or is hardwired. Leaning: thin adapter, default = Omnigent-launched Claude Code,
because that is what already gives sessions, transcripts and the Realm brief wiring.
Open: does the runner call Omnigent through its MCP/API, or shell out to a CLI?
Does the brief wiring (`CLAUDE.local.md`, `.realm/`) exist inside a fresh worktree
(known gap in omnigent-realm-workflow.md "Open items")? It must, or the agent works blind.

### 3. Which model?

Options: a runner-wide default; per-quest via a field (`model:` or derived from
`effort`/`tier`); per-quest-type table in config. Leaning: derive a default from
`effort`/`tier` in runner config (cheap model for `spark`/`xs`-`s`, stronger for
`brief`/`blueprint`), allow a per-quest override via `--set model=...` only if the
schema can declare it generically (a custom field, not a hardcoded core field).
Record the chosen model in the PR body and the quest `## Log`.

### 4. Guardrails

The runner executes quest text written by someone (possibly an agent) with write
access to a repo, so treat the quest body as untrusted-ish input. Candidate set:

- **Selection**: only `agentic=afk`, `status=todo`, READY and STATE both green
  (`quest ready`), unblocked, not archived; optional allowlist of logs/projects
  and a `--max-per-run`/`--max-per-day` cap. Default one quest per run.
- **Claim without a lock protocol**: set `status: in-progress` and push the branch
  before the agent starts; refuse a quest whose branch/PR already exists. (v3
  declared a claim/lock protocol out of scope, so this stays a runner convention.)
- **Isolation**: worktree under `<repo>-worktrees/<branch>/`, branch named from the
  quest id (`quest/QST-xxxxx-slug`), cwd-only access; remember worktrees are not an
  access fence, so also restrict permissions (tool allowlist, no network beyond Gitea,
  deny `git push` to anything but the quest branch).
- **Identity and blast radius**: the omnigent bot Gitea user and PAT, scoped to PR
  creation on allowed repos; branch protection on `main` so the bot cannot push
  there; never merge. The fleet break-glass key is never available to the runner.
- **Budget**: max turns, wall-clock timeout, max cost/tokens; on breach, stop, push
  what exists as a draft PR or leave the quest `parked` with a log entry.
- **Verification gate before PR**: repo test suite and `quest validate` pass, diff
  stays inside declared paths (if the spec lists any), no secrets/`.env` in the diff,
  no edits to CI/guardrail config unless the quest says so.
- **Failure path**: on any gate failure, no PR; the quest gets a `## Log` entry and
  returns to `todo` (or `parked` after N failures) so `quest next` does not spin on it.
- **Prompt injection**: the brief and any fetched content are data; the runner prompt
  states that, and the agent has no secrets in its environment.

### 5. Omnigent session link in the PR

Goal: a reviewer can open the actual prompts and reasoning. Needs a check of what
Omnigent exposes: is there a stable, shareable session URL, and is it reachable by
the reviewer (auth, network)? If not, fall back to a transcript attachment or an
exported summary committed outside the repo. Decide what goes in the PR body:
quest id/title link, harness + model, session link, gate results, cost/turns used.
Careful: session transcripts may contain secrets or private context; decide whether
the link is safe to put in a PR on a repo that is mirrored to GitHub.

### 6. Trigger

Options: manual (`runner run QST-xxxxx` / `runner next`), a schedule (Gitea Actions
cron or the realm-01 timer), an event (quest merged to `todo` + `agentic=afk` with a
label or `workflow_dispatch`), or a chat/Home Assistant command. Leaning: manual first,
`workflow_dispatch` second (explicit quest id input, runs on the Gitea runner), cron
only after the guardrails have proven themselves, with a hard daily cap.

### 7. Where does it run?

Gitea Actions runner (clean container, easy secrets scoping, but needs the harness
auth and Omnigent reachability there) versus dev-01 (already has tea, the bot PAT and
worktree conventions). Decide with the trigger answer; the single script runs in both.

### 8. Implementation layer: reuse Matt Pocock's skills v1.3

[mattpocock/skills](https://github.com/mattpocock/skills) v1.3 (2026-10, latest v1.3.1)
promoted three skills into its Engineering bucket that cover most of what this runner
would otherwise hand-roll. Facts below are from the upstream SKILL.md files and release
notes as read on 2026-10-14; re-read upstream before building, it moves fast.

**`/implement-spec`** (`skills/engineering/implement-spec/SKILL.md`, user-invoked,
`disable-model-invocation`). A coordinating agent that implements a whole spec plus its
tickets:

1. read the spec and tickets as a dependency graph (a **frontier** of unblocked tickets),
2. optional exploration subagent writes notes outside the repo for later subagents,
3. create **one integration branch**; open a draft PR after the first merge only if the
   tracker closes work through PRs or the user asks,
4. one **implementer subagent per ticket**, each in its own worktree and branch, using
   the `tdd` skill, rebased/merged onto the integration branch tip before reporting,
5. a **merger subagent** merges each finished ticket into the integration branch,
6. recompute the frontier after every merge and start newly unblocked tickets,
7. when all tickets are done, run the `code-review` skill on the integration branch and
   let one implementer fix everything it raises,
8. mark the draft PR ready, or resolve tickets the way the tracker closes work,
9. remove all implementer worktrees.

**`/pr`** (`skills/engineering/pr/SKILL.md`, derived from the `show-me` skill by Dex
Horthy at HumanLayer). Defines the PR body: **Summary** (smallest useful visual:
pseudocode, call tree, file tree, Mermaid, diff), **Evidence** (before/after: screenshots,
the exact test that failed then passed), **Merge Danger** (one-way vs two-way door, plus
blast radius). Writes for fast human review, uses glossary terms.

**`/retro`** (`skills/engineering/retro/SKILL.md`, user-invoked). Reads a session log
(default: current session) and proposes **ranked** improvements to the agent's
environment across navigation, automated checks, coding standards, global AGENTS.md,
tool economy, no-ops and information access. Biases toward deterministic checks (lint,
pre-commit, CI) over prose standards, and treats a repo with no guardrail as a finding.
It suggests; it does not apply.

How this changes the design, each point a decision to record:

- **Two tiers of runner target.** `spark`/`brief` quests are one agent in one worktree
  (the existing `implement` skill or a plain harness prompt). `type: epic` and
  `tier: blueprint` quests are the `/implement-spec` shape: the epic is the spec, its
  child quests are the tickets, and `blocked_by` is the graph. Decide whether the runner
  dispatches by `tier`/`type`, and check how epic-to-child is modelled in questkit
  (there is no parent field; the workflow README says epics are quests related by
  `blocked_by`) so the frontier can be computed with `quest next`/`quest deps`.
- **Quests as the tracker.** `/implement-spec` assumes a configured issue tracker
  (via `/setup-matt-pocock-skills`) and "resolves tickets the way the tracker closes
  work". Here that means `quest set status=in-progress` / `quest done`, the
  `quest(<zone>):` commit prefix, and quest-log edits staying on the integration branch.
  Upstream cannot know that; see the follow-up quest for a personalised
  `/implement-quest` instead of configuring the generic skill.
- **Branch versus PR.** Upstream targets an integration branch and opens a PR only when
  needed. This runner always ends in a Gitea PR (the bot cannot approve its own PR, which
  keeps a human in the loop). Decide: open the draft PR early (upstream's "tracker closes
  via PRs" path, gives the reviewer a live view) or only at the end.
- **PR body.** Use `/pr`'s Summary/Evidence/Merge Danger as the base, then append the
  runner-owned block: quest link, harness + model, Omnigent session link (decision 5),
  gate results, cost/turns. `/pr` writes the body; `/ship` (our existing judgment layer
  over `ship.py`) still opens it. Candidate guardrail: a **one-way door** verdict
  keeps the PR draft and adds a label, never "ready for review" automatically.
- **Blast radius of parallelism.** `/implement-spec` fans out many subagents and
  worktrees. Add runner guardrails for max concurrent subagents, max total subagents,
  total budget across all of them, and worktree cleanup in the failure path too. All
  subagent worktrees still follow the `<repo>-worktrees/<branch>/` convention, and
  worktrees are not an access fence (see decision 4).
- **Headless invocation.** Both `/implement-spec` and `/retro` are user-invoked, and as
  of v1.3 upstream user-invoked skills cannot be reached through the Skill tool. The
  runner must therefore put the slash command in the prompt itself. Verify whether
  `claude -p "/implement-spec ..."` and the Omnigent session API actually expand skills
  in non-interactive mode before relying on it; if not, the runner inlines the
  SKILL.md text into the prompt.
- **`/retro` closes the loop.** Run it after each unattended run (or weekly over the
  last N runs) against the Omnigent transcript. Its ranked findings become spark quests
  in the relevant log, never auto-applied edits. Its "prefer deterministic checks" stance
  is the same principle as the verification gate in decision 4. Decide cadence and who
  triages the resulting quests.
- **Upstream rename to track.** v1.3 renamed `CONTEXT.md`/`CONTEXT-MAP.md` to
  `GLOSSARY.md`/`GLOSSARY-MAP.md` (breaking; skills only look for the new names).
  `/pr` and `grill-with-docs` read `GLOSSARY.md`. questkit has no glossary file today;
  decide whether it should get one so PR bodies use consistent terms.

### 9. Context budget: two windows, not one

The runner should spend as little context as possible. Split it into two fresh windows:

- **Chooser.** A short-lived, fresh agent or sub-agent. It reads the quest list (`quest next`,
  `quest ready`) and returns one quest id with a one-line reason. It does not read the code, so
  its output is small and the caller's window stays small.
- **Implementer.** A fresh session started with only the chosen quest's brief. It loads files per
  step and clears old test logs by rule.

Compaction is the wrong tool for this split. A summary of the chooser's work would still carry the
candidate list the implementer does not need. A fresh window carries nothing it does not need.

Leaning: the runner script is the only thing that moves data between the two windows, and it passes
the quest id and the brief, not the chooser's transcript. Open: does the chooser need a model at all,
or is a deterministic `quest next --where agentic=afk` plus a stated reason enough for most runs?

## Spec

Not yet groomed. Once the decisions above are made, the first deliverable is a
**manual-trigger tracer bullet**: `runner run <id>` on dev-01 that creates the
worktree and branch, runs one harness with one model on one `spark` AFK quest, updates
the quest, runs the verification gate and opens a PR via `tea`. Scheduling, CI
wrapping, model selection tables and the Omnigent link follow as separate quests.

## Acceptance

- [ ] Each numbered decision above is resolved and recorded in this quest's `## Log`
- [ ] A follow-up tracer-bullet quest exists, groomed to `agentic: afk` with acceptance criteria
- [ ] Follow-up quests exist for any questkit core changes the design needs (e.g. `quest ready`)
- [ ] `implement-spec`, `pr` and `retro` are declared in `99-system/skills.yaml`
      (source `github.com/mattpocock/skills`, path `skills/engineering/<name>/SKILL.md`,
      personal scope enabled) and `make plan-skills` shows no drift for them
- [ ] The skills those three depend on are also declared: `tdd` (already present),
      `code-review` and `writing-for-agents` (retro loads it). Note the skills.yaml
      built-in blind spot: upstream `code-review` shares a name with a built-in skill,
      so decide whether to declare it or leave the built-in
- [ ] Decision 8 is resolved: runner dispatch by `tier`/`type`, how the headless prompt
      invokes user-invoked skills, PR body composition from `/pr`, and the `/retro` cadence
- [ ] The personalised `/implement-quest` skill is tracked in its own quest,
      [[QST-u90gs--personalised-implement-quest-skill-for-epic-and-blueprint-quests]]

## Log

- 2026-10-20: added decision 9 (context budget: a chooser window and a separate implementer window, with compaction ruled out for the split). Source: CCDV-F Lesson 0004 section 7; the design is not built

- 2026-10-14: added decision 8 and acceptance criteria after Matt Pocock's skills v1.3 (`/implement-spec`, `/pr`, `/retro`); personalised `/implement-quest` split out as QST-u90gs; no `blocked_by` between them because the tracer bullet runs on spark quests and does not need the skill

- 2026-10-13: captured from a request to automate AFK quest implementation end to end (worktree, branch, implement, update quest, Gitea PR); open decisions listed, nothing decided yet

