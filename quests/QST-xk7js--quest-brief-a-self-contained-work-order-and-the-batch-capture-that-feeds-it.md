---
id: QST-xk7js
title: "quest brief: a self-contained work order, and the batch capture that feeds it"
description: Emit a lean, agent-agnostic Markdown work order for one quest, and accept a body or a batch of quests on stdin as the inbound half.
created: 2026-08-19
status_changed: 2026-08-19
modified: 2026-08-20
type: feature
tier: brief
status: draft
priority: high
effort: m
milestone: 0.3.0
project: questkit
tags:
  - questkit
  - cli
  - agentic
blocked_by:
  - QST-b9lqo
aliases:
  - QST-xk7js
agentic:
---

## Description

`agentic: afk` is validated but **nothing consumes it**. `quest validate` enforces
that an AFK quest carries a `## Spec` and real acceptance criteria — readiness for
a handoff that has no receiver. One file in 129 uses the field. A
validated-but-unused axis is worse than no axis.

`quest brief <id>` gives it a receiver: a **self-contained, agent-agnostic
Markdown work order** on stdout. And `--body -` / `--batch -` are the missing
inbound half — today `quest new` takes a title and flags, so an agent that turned
a spec into eight tickets must shell out eight times and cannot write a body at
all.

Together these make questkit own **both edges** of the tickets step in a
grill → spec → tickets → implement → review flow: an ungroomed quest's brief seeds
a grilling session, a groomed quest's brief is the implementation prompt, and the
spec that comes back becomes N quests in one call.

## Spec

### Scope

**In:** `quest brief`, `quest new --body -`, `quest new --batch -`.
**Out:** `quest ready` (deferred), any claim/lock/report-back protocol (explicitly
out of scope for v3 — see [[QST-bmzl2--questkit-v3-loop-closure-multi-log-ux-and-agent-handoff]]).

### Approach — output

Short by default. Three compressions do the work: metadata collapses to one dense
line; **the schema block is printed only when the log actually overrides the
default vocabulary or declares custom fields** (precisely when the reader cannot
guess); prose becomes labeled blocks.

```
$ quest brief QST-8hjjk

QST-8hjjk — Allow for --select and --distinct when listing quests
feature · todo · medium · effort=s · tier=brief · agentic=afk · owner=peter · cli,dx

Add projection and de-duplication to `quest list` so it can answer "which
projects have open quests?" without post-processing in jq.

LOCATION
  quest  quests/QST-8hjjk--allow-for-select-and-distinct-when-listing-quests.md
  log    02-projects/lazytarget/questkit/quests   project=questkit  git=manual
  repo   02-projects/lazytarget/questkit          main, clean

SPEC
  1. `--select a,b,c` restricts output to the named fields, in order.
  ...

ACCEPTANCE
  [ ] `quest list -A --select project --distinct` prints one row per project
  ...

DEPENDENCIES
  blocked_by  (none)
  blocks      2 quests
              QST-xxxxx  todo  quests/QST-xxxxx--....md
  scope       7 logs under /home/gitops/realm

REPORT BACK
  quest set QST-8hjjk status=in-progress
  quest done QST-8hjjk
  Notable decisions → the quest's ## Log. Commit prefix: quest(questkit):

READY  ✅ spec · ✅ 4 acceptance criteria · ✅ agentic=afk
STATE  ✅ todo · ✅ unblocked · blocks 2
```

**Two lines, not one — they fail for different reasons and have different fixes.**

| Line | Question | Source | Fixed by |
|------|----------|--------|----------|
| `READY` | Is this document executable as written? | the schema's **`readiness:` rules** ([[QST-j68u5--schema-engine-field-order-defaults-macros-typed-fields-strict-writes]] rule 15) | grooming |
| `STATE` | Should anyone pick it up right now? | computed: `blocked=false`, status not terminal/parked/archived | unblocking, or a status change |

**`READY` is entirely schema-driven — `quest brief` hardcodes no rule.** It
evaluates the log's `readiness:` list and prints each rule's own `message` on
failure. That is what lets a `household` log declare that a chore needs a
description and nothing else, while `development` requires a spec and acceptance
criteria, without `brief` knowing either domain exists.

It also means `agentic` is not special to `brief`. The old AFK gate is now just a
conditional readiness rule that `development` happens to declare
(`when: "agentic=afk"`), and `brief` reads it the same way it reads every other.

**`STATE` stays computed and non-configurable.** The line is: `READY` is about
what a human wrote, so a schema owns it; `STATE` is about where the quest sits in
the graph, so the tool owns it. `status!=draft` is a *grooming* fact and belongs
to READY; `blocked`, terminal and archived are *graph* facts and belong to
STATE.

A `READY` failure means "not implementation-ready — this is grooming input". A
`STATE` failure is a warning, never a refusal: **`quest brief` must still emit a
full brief for a blocked quest**, because the most common reason to brief one is
to hand an agent the thing that unblocks it. It names the blocker so the reader
can retarget:

```
STATE  ⚠️  blocked by QST-3ehhu (todo) — that quest is the actionable work
```

`status=scrapped` and `status=completed` warn loudly (`already completed
2026-08-14 — briefing it is probably a mistake`) rather than erroring, since
re-briefing a finished quest to understand what was done is legitimate.

For an **ungroomed** quest the same command collapses to header, location and
warnings — short-by-default emerges exactly where a full brief would be
meaningless:

```
READY
  ⚠️  No `## Spec` or `## Design` section
  ⚠️  `## Acceptance Criteria` contains only the `- [ ] ...` placeholder
  ⚠️  `agentic:` unset — not triaged for handoff
  NOT implementation-ready. This is grooming input.
```

### What a brief has that `cat` does not

1. **Resolution** — `blocked_by` becomes title + status + path, so nobody hunts across seven logs.
2. **Location** — repo root, branch, dirty state, log path, git mode. Writing to the wrong log is the most common agent failure in a multi-log vault.
3. **Schema inline when it matters** — a brief pasted into a browser tab with no shell is still complete.
4. **A write-back contract** — exact commands, exact id, the log's commit convention. An agent that finishes work and leaves `status: todo` is how a backlog rots.
5. **Reverse dependencies** — `blocks` ([[QST-b9lqo--computed-fields-and-comparison-operators-for-where]]) as a priority signal the quest file itself does not carry.
6. **A stable format** — skills and scripts can be written against `quest brief`. Nothing can be written against `cat`.

### Agent-agnostic, concretely

Plain Markdown on stdout. No vendor keys, no JSON envelope, no tool definitions,
no system-prompt framing. It describes **the work**, never **the worker** —
`claude -p "$(quest brief X)"`, `codex exec "$(quest brief X)"`,
`quest brief X | pbcopy`, or `quest brief X | less` for a human.

**No `--for grill|implement` flag.** Skill names do not belong in questkit's CLI;
that would import one workflow's vocabulary into a tool that should not know it
exists. Emit one canonical brief with an honest readiness verdict and let the
caller decide.

### Approach — inbound

```bash
quest new "Add --select" --body - <<'EOF'
## Spec
...
EOF

quest new --batch - --in questkit <<'EOF'
- title: Add --select to quest list
  type: feature
  set: {effort: s}
  tags: [cli, dx]
  body: |
    ## Spec
    ...
EOF
```

`--batch` prints one id per line in input order, and makes the positional `title`
optional (`nargs="?"` plus a mutual-exclusion check).

### Alternatives

| Option | Verdict | Reason |
|--------|---------|--------|
| `quest brief` | ✅ Chosen | Noun and verb both; promises a document and delivers one |
| `quest handoff` | ❌ | Names a protocol deliberately not being built — every reader will ask where `quest claim` is |
| `quest prompt` | ❌ | LLM-specific; breaks agent-agnosticism |
| `quest spec` | ❌ | Collides with the `## Spec` body section |
| Fold into `quest show` | ❌ | `show` should stay dumb (`git show`); a brief is a derived document |

## Acceptance Criteria

- [ ] `quest brief <id>` emits the lean format above for a groomed quest
- [ ] The schema block is omitted for a log using the default vocabulary, present otherwise
- [ ] `DEPENDENCIES` resolves `blocked_by` to title, status and file path
- [ ] `DEPENDENCIES` lists reverse dependencies via `blocks`
- [ ] The brief sweeps all logs and prints its scope
- [ ] `REPORT BACK` names the exact commands and the log's commit prefix
- [ ] An ungroomed quest's brief collapses to header, location and warnings
- [ ] `READY` and `STATE` are separate lines with separate verdicts
- [ ] `READY` is computed from the log's `readiness:` rules, with no rule hardcoded in `brief`
- [ ] A rule's own `message` is what prints on failure
- [ ] A `household`-schema quest with only a description reports READY ✅
- [ ] `brief` never fails on `agentic` specifically — only via a declared rule
- [ ] A blocked quest still gets a full brief, with `STATE` naming the blocker
- [ ] A completed or scrapped quest warns but still briefs
- [ ] Only a `READY` failure produces the "not implementation-ready" verdict
- [ ] Output contains no vendor-specific or model-specific text
- [ ] `quest new --body -` reads the Markdown body from stdin
- [ ] `quest new --batch -` creates N quests and prints their ids in input order
- [ ] `--batch` with a positional title is a clear error

## Log

- 2026-08-19: READY rewired to the schema's `readiness:` list after `agentic` left the core; `brief` now hardcodes no readiness rule at all.
- 2026-08-19: readiness split into READY (document quality) and STATE (right-now eligibility) — they fail for different reasons and a blocked quest must still be briefable.
- 2026-08-19: captured. The default output was deliberately shrunk from an earlier verbose draft; the schema block's conditional presence is the principled half of that, not just the shorter one.
