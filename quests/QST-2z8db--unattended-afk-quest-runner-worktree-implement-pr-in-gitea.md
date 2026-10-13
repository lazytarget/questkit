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
modified: 2026-10-13
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
[[QST-tf4wc--gitea-actions-ci-for-the-questkit-repo]], [[QST-8hq61--reusable-ci-recipe-for-repos-hosting-a-quest-log]],
[[QST-22gdn--commit-trailers-transition-quests-from-code-repos]].
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

## Log

- 2026-10-13: captured from a request to automate AFK quest implementation end to end (worktree, branch, implement, update quest, Gitea PR); open decisions listed, nothing decided yet
