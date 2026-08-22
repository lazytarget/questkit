---
id: QST-bmzl2
title: "questkit v3: loop closure, multi-log UX, and agent handoff"
description: "Umbrella epic for questkit v3: close the work loop, make multi-log targeting legible, and make an agent handoff format real. (v3)"
project: questkit
type: epic
status: done
priority: high
tags:
  - questkit
  - quests
  - framework
  - tooling
created: 2026-08-19
status_changed: 2026-08-22
modified: 2026-08-22
aliases:
  - QST-bmzl2
blocked_by: []
effort: xl
milestone: 0.3.0
owner: peter
tier: blueprint
---

## Description

v1 ([[QST-whm2e--questkit-design-blueprint-for-file-based-quest-tracking]]) established the file format, nearest-zone-wins discovery, and
the one-log-per-command rule. v2 ([[QST-v0hnq--questkit-v2-dynamic-schema-engine-and-multi-log-architecture]]) added the dynamic per-log schema
engine, cross-log query, and global-id mutation resolution.

**v3 is about what happens after capture.** Every field and command questkit has
today is about getting work *in* and describing it; nothing surfaces work that is
rotting and nothing helps choose what to do next. Trello — the system questkit
replaced — did not die of bad capture. It died of declining engagement with an
ever-growing board. Retrofitting hygiene onto a large corpus is far worse than
designing it in now.

Three themes, in priority order:

1. **Close the loop.** A staleness signal that file churn cannot launder
   (`status_changed`), derived state the schema does not store (`blocked`,
   `blocks`, `idle`, `age`), and the views that consume them (`next`, `stale`,
   `blocked`, `deps`).
2. **Make multi-log legible.** Selective Syncthing makes multiple logs
   mandatory, but today it is hard to know which log you are targeting and
   impossible to say "these two". Resolve logs by project name, allow several
   at once, group results per log, and always print the scope — a query whose
   answer depends on which device you ran it from must say so.
3. **Make the handoff real.** `agentic:` is validated but nothing consumes it.
   `quest brief` turns a groomed quest into a self-contained, agent-agnostic
   work order; `--body -` / `--batch -` are the inbound half, so a spec can
   become N tickets in one call.

The full design record — decisions, rejected alternatives, and the reasoning
behind each — is in [docs/planning/plan_questkit_v3.md](../docs/planning/plan_questkit_v3.md).

## Scope

Ordered by dependency. Each item is its own quest.

| # | Quest | Theme | Batch |
|---|-------|-------|-------|
| 1 | [[QST-mjuau--quest-save-writes-only-when-the-rendered-content-changes]] | correctness — blocks the committer | B0 |
| 2 | [[QST-lc3co--quest-migrate-frontmatter-aware-corpus-migrations]] | migration | B0 |
| 3 | [[QST-3h09k--status-changed-frontmatter-field-and-reusable-backfill]] | loop closure | B0 |
| 4 | [[QST-j68u5--schema-engine-field-order-defaults-macros-typed-fields-strict-writes]] | schema | B1-B3 |
| 5 | [[QST-fmk0p--resolving-questkit-log-in-specified-path-via]] | multi-log | B4 |
| 6 | [[QST-3ehhu--quest-logs-inventory-every-quest-log-under-a-root]] | multi-log | B4 |
| 7 | [[QST-iqwjm--multi-log-query-ux-all-logs-repeatable-in-and-root-per-log-grouping-summary-block]] | multi-log | B4 |
| 8 | [[QST-yiep7--qualified-cross-log-references-in-blocked-by]] | multi-log | B5 |
| 9 | [[QST-b9lqo--computed-fields-and-comparison-operators-for-where]] | loop closure | B1 + B5 |
| 10 | [[QST-8hjjk--allow-for-select-and-distinct-when-listing-quests]] | query | B4 |
| 11 | [[QST-xk7js--quest-brief-a-self-contained-work-order-and-the-batch-capture-that-feeds-it]] | agent handoff | B7 |
| 12 | [[QST-37n0t--built-in-views-next-stale-blocked-and-quest-deps]] | loop closure | B5 |
| 13 | [[QST-e6g6t--quest-commit-and-the-realm-01-designated-committer]] | automation | B7 |
| 14 | [[QST-5rjla--obsidian-capture-surface-generated-template-md-topology-rows-bases-triage-view]] | capture surface | B7 |
| 15 | [[QST-lcsza--archive-a-whole-quest-log-instead-of-individual-quests]] | multi-log | B6 |
| 16 | [[QST-zl5xc--group-root-commands-in-help-output-as-the-cli-passes-20-verbs]] | dx | B7 |

`quest migrate` moved from #15 to #2: it was scheduled behind every migration it
exists to perform, while #3's acceptance criteria named it outright. The
`--where` comparison operators split out of #9 into #4, where `readiness:`
consumes `!=`. Batch groupings and their rationale are in
[the plan's §12](../docs/planning/plan_questkit_v3.md).

Independent, no ordering constraint: [[QST-ombky--quest-validate-reports-informational-slug-drift-as-a-hard-error]], [[QST-lc3d7--check-for-duplicates-when-adding-with-same-title]], [[QST-onxad--new-frontmatter-attributes]].

## Release scope

This epic **is** the `0.3.0` release. `pyproject.toml` reads `version = "0.2.0"`
today; every quest in the Scope table above carries `milestone: 0.3.0`, and
shipping them all is what makes the version bump honest.

Two quests in this log are deliberately **not** in it —
[[QST-lc3d7--check-for-duplicates-when-adding-with-same-title]] and
[[QST-onxad--new-frontmatter-attributes]] are `milestone: 0.4.0`. Neither is
required for v3 to be coherent: duplicate detection is an independent nicety, and
`language` needs the `household` schema, which is the *second* schema to be
written.

**If 0.3 needs to shrink, items 13-15 are the cut line** — `quest commit` and the
realm-01 timer, the Obsidian capture surface, and archival. Each is genuinely
useful and none of the earlier items depend on them, so they move to `0.4.0` as a
block without leaving anything half-built. Items 1-12 are not separable: they are
the loop-closure story, and cutting any one of them leaves a command specified
against machinery that does not exist.

**In the end, the cut was partial rather than whole-item**: #13 and #14 each
shipped their in-repo software half in v0.3 (`quest commit`/`tracked:`/`quest
validate --report`, and `quest init --template`/the Bases view, respectively) and
split their infrastructure-outside-this-repo half —the realm-01 timer, `git: auto`
unification, and `topology.yaml` distribution — into
[[QST-kxo5m--realm-01-designated-committer-timer-and-git-auto-unification]] and
[[QST-9bsnv--obsidian-template-distribution-via-topology-yaml-and-home-assistant-capture]]
at `milestone: 0.5.0`. #15 (archival) shipped in full.

## Positioning decisions

| Question          | Decision                                                                                                     |
| ----------------- | ------------------------------------------------------------------------------------------------------------ |
| What is questkit? | A quest **tracker**. Recurrence and non-ticket collections never widen the quest schema.                     |
| Who is it for?    | **Personal-first**, structured so open-sourcing stays cheap (portfolio). Realm-agnostic discipline retained. |
| Who uses it?      | Solo + agents + **family via Obsidian**. `owner` stays free text. The CLI is not the family's surface.       |
| Capture or loop?  | **Loop.** Capture already works; that is the one thing questkit demonstrably nailed.                         |

## Out of scope

- **Recurrence** — the single most sophisticated part of the Trello setup
  questkit replaced. Deliberately untouched; see [[QST-whm2e--questkit-design-blueprint-for-file-based-quest-tracking]]'s Out-of-Scope.
- **Bulk multi-log writes** — every command still mutates one file per
  invocation.
- **A claim / lock / handoff protocol.** `quest brief` emits a document; it does
  not transfer ownership. Naming a command after a mechanism that does not exist
  invites the missing half.
- **`completed_at`** — derivable from git for `git: auto` logs, genuinely
  uncertain elsewhere, and no v3 command needs it.
- **A membership / parent-child concept.** `milestone:` is a planning bucket, not
  a link; an epic's Scope table stays prose. Grouping is a real gap and a real
  design round, and 20 quests is not enough pressure to justify it.
- **Nesting commands into noun-verb groups.** v3 groups `--help` output only; every command stays reachable as `quest <verb>`.
- **A readiness rule that can block a commit.** `quest validate` enforces the
  file contract; `readiness:` is advisory and belongs to `quest brief`.
- **WIP limits and auto-scrapping** — policy, and policy needs usage evidence
  that does not exist yet.
- **`quest ready`** — deferred until `quest brief` has been used by hand enough
  to know what the predicate should actually be.

## Acceptance Criteria

- [x] Every quest in the Scope table is completed or explicitly scrapped (items 13 and 14's infrastructure-outside-this-repo remainder split to [[QST-kxo5m--realm-01-designated-committer-timer-and-git-auto-unification]] / [[QST-9bsnv--obsidian-template-distribution-via-topology-yaml-and-home-assistant-capture]] at `milestone: 0.5.0` — see Release scope)
- [x] `quest next` answers "what should I do here" in one command, and never proposes a quest with an open dependency
- [x] `quest stale` survives a full-corpus `quest format --fill-defaults` run without being reset (`idle` is computed, never stored, so there is nothing for `format` to reset)
- [x] A cross-device query states its own scope, so a partial answer is never mistaken for a complete one
- [x] `quest brief <id>` output is sufficient to execute a groomed quest with no further discovery commands
- [x] The family log has a working creation path that is not the CLI (`quest init --template` shipped; distributing the generated file onto family devices via `topology.yaml`/Home Assistant is [[QST-9bsnv--obsidian-template-distribution-via-topology-yaml-and-home-assistant-capture]], `milestone: 0.5.0`)
- [x] `quest validate` on every Realm log reports clean, or reports something real (ran 2026-08-22 against all 7 logs: `family`/`grocy-ecosystem`/`realm-common`/`questkit` clean or note-only; `career-transition`/`pensieve`/`realm-system` report real, pre-existing corpus errors — undeclared fields from before their schemas adopted `strict:`, and a stale `status: completed` from before `terminal_statuses` renamed it to `done` — genuine findings, not validator noise. Migrating those 3 logs' corpora is out of this epic's scope, as already noted in prior sessions.)
- [x] A finished project's log can stop appearing in sweeps without any file moving
- [x] A `household` log's `quest brief` applies no software-shaped readiness rule
- [x] `--sort priority:asc` returns critical-first, and honors a second sort key
- [x] Every `milestone: 0.3.0` quest is done or scrapped before `pyproject.toml` reads `0.3.0`

## Log

- 2026-08-22: epic closed. All 16 Scope-table quests are done; #13 and #14 each split their infrastructure-outside-this-repo remainder into a new `milestone: 0.5.0` quest ([[QST-kxo5m--realm-01-designated-committer-timer-and-git-auto-unification]], [[QST-9bsnv--obsidian-template-distribution-via-topology-yaml-and-home-assistant-capture]]) rather than blocking the release on work this repo can't deploy or test. `quest validate` was run against all 7 real Realm logs; the errors it reports in `career-transition`/`pensieve`/`realm-system` are genuine pre-existing corpus drift (undeclared fields, a stale `completed` status value), not something this epic introduced or is scoped to fix. Every AC is satisfied; `pyproject.toml` can now read `0.3.0`.
- 2026-08-20: batch B7 shipped: [[QST-zl5xc--group-root-commands-in-help-output-as-the-cli-passes-20-verbs]] (grouped `--help`), [[QST-xk7js--quest-brief-a-self-contained-work-order-and-the-batch-capture-that-feeds-it]] (`quest brief`, `quest new --body -`/`--batch -`), [[QST-e6g6t--quest-commit-and-the-realm-01-designated-committer]] (`quest commit`, `tracked:`, `quest validate --report`, `quest init`'s `.gitignore` handling -- `git: auto` unification and the realm-01 timer itself deliberately left open), [[QST-5rjla--obsidian-capture-surface-generated-template-md-topology-rows-bases-triage-view]] (schema-generated `_template.md`, Bases "Needs attention" view -- `topology.yaml` distribution and Home Assistant integration deliberately left open, both being infrastructure outside this repository). B0-B7's in-repo scope is now complete; what remains against this epic's own acceptance criteria is genuinely operational (deploying the realm-01 timer, wiring `topology.yaml`, running `quest validate` across every real Realm log) rather than more code.
- 2026-08-20: batch B6 (archival) shipped: [[QST-lcsza--archive-a-whole-quest-log-instead-of-individual-quests]] — core `archived:` field's write surface (`archive`/`unarchive`/`archive-log`/`unarchive-log`) and query axis (`--archived exclude|include|only`). B0-B6 now complete (15 quests); remaining: B7 (brief/commit/capture-surface/help grouping).
- 2026-08-20: batch B5 (loop closure) shipped: [[QST-b9lqo--computed-fields-and-comparison-operators-for-where]] (blocked/blocks/idle/age), [[QST-yiep7--qualified-cross-log-references-in-blocked-by]] (qualified `blocked_by` refs), [[QST-37n0t--built-in-views-next-stale-blocked-and-quest-deps]] (`quest next`/`stale`/`blocked`/`deps`, schema `views:`). B0-B5 now complete (14 quests); remaining: B6 (archival, [[QST-lcsza--archive-a-whole-quest-log-instead-of-individual-quests]]) and B7 (brief/commit/capture-surface/help grouping).
- 2026-08-19: captured after a design grilling session covering positioning, multi-log friction, schema defaults, the agent handoff format, and the git/Syncthing boundary. Plan file written the same day.
