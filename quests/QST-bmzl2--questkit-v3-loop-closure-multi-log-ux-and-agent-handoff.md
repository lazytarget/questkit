---
id: QST-bmzl2
title: "questkit v3: loop closure, multi-log UX, and agent handoff"
description: "Umbrella epic for questkit v3: close the work loop, make multi-log targeting legible, and make an agent handoff format real. (v3)"
created: 2026-08-19
modified: 2026-08-19
type: epic
tier: blueprint
status: todo
priority: high
effort: xl
owner: peter
project: questkit
tags:
  - questkit
  - quests
  - framework
  - tooling
blocked_by: []
aliases:
  - QST-bmzl2
agentic: afk
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

| # | Quest | Theme |
|---|-------|-------|
| 1 | [[QST-mjuau--quest-save-writes-only-when-the-rendered-content-changes]] | correctness — blocks the committer |
| 2 | [[QST-3h09k--status-changed-frontmatter-field-and-reusable-backfill]] | loop closure |
| 3 | [[QST-j68u5--schema-engine-field-order-defaults-macros-typed-fields-strict-writes]] | schema |
| 4 | [[QST-fmk0p--resolving-questkit-log-in-specified-path-via]] | multi-log |
| 5 | [[QST-3ehhu--quest-logs-inventory-every-quest-log-under-a-root]] | multi-log |
| 6 | [[QST-iqwjm--multi-log-query-ux-all-logs-repeatable-in-and-root-per-log-grouping-summary-block]] | multi-log |
| 7 | [[QST-yiep7--qualified-cross-log-references-in-blocked-by]] | multi-log |
| 8 | [[QST-b9lqo--computed-fields-and-comparison-operators-for-where]] | loop closure |
| 9 | [[QST-8hjjk--allow-for-select-and-distinct-when-listing-quests]] | query |
| 10 | [[QST-xk7js--quest-brief-a-self-contained-work-order-and-the-batch-capture-that-feeds-it]] | agent handoff |
| 11 | [[QST-37n0t--built-in-views-next-stale-blocked-and-quest-deps]] | loop closure |
| 12 | [[QST-e6g6t--quest-commit-and-the-realm-01-designated-committer]] | automation |
| 13 | [[QST-5rjla--obsidian-capture-surface-generated-template-md-topology-rows-bases-triage-view]] | capture surface |

Independent, no ordering constraint: [[QST-ombky--quest-validate-reports-informational-slug-drift-as-a-hard-error]], [[QST-lc3d7--check-for-duplicates-when-adding-with-same-title]], [[QST-onxad--new-frontmatter-attributes]].

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
- **WIP limits and auto-scrapping** — policy, and policy needs usage evidence
  that does not exist yet.
- **`quest ready`** — deferred until `quest brief` has been used by hand enough
  to know what the predicate should actually be.

## Acceptance Criteria

- [ ] Every quest in the Scope table is completed or explicitly scrapped
- [ ] `quest next` answers "what should I do here" in one command, and never proposes a quest with an open dependency
- [ ] `quest stale` survives a full-corpus `quest format --fill-defaults` run without being reset
- [ ] A cross-device query states its own scope, so a partial answer is never mistaken for a complete one
- [ ] `quest brief <id>` output is sufficient to execute a groomed quest with no further discovery commands
- [ ] The family log has a working creation path that is not the CLI
- [ ] `quest validate` on every Realm log reports clean, or reports something real

## Log

- 2026-08-19: captured after a design grilling session covering positioning, multi-log friction, schema defaults, the agent handoff format, and the git/Syncthing boundary. Plan file written the same day.
