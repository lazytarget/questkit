---
id: QST-b9lqo
title: Computed fields and comparison operators for --where
description: Derive blocked, blocks, idle and age alongside frontmatter and expose them to --where, --select and --sort, with numeric and date comparisons.
created: 2026-08-19
status_changed: 2026-08-19
modified: 2026-08-20
type: feature
tier: brief
status: todo
priority: high
effort: m
milestone: 0.3.0
project: questkit
tags:
  - questkit
  - cli
  - dx
blocked_by:
  - QST-3h09k
aliases:
  - QST-b9lqo
agentic: afk
---

## Description

Some of the most useful facts about a quest are not stored in it. They are
derivable from the corpus, and deriving them once — as **read-only fields
available to every query** — is what turns the loop-closing views into simple
prefills instead of bespoke commands.

It also fixes a live defect. `quest list` defaults to
`status=todo,in-progress,blocked`, and **8 non-terminal quests in `pensieve`
currently have at least one open dependency** while showing as actionable.
Meanwhile `status: blocked` is used **0 times in 129 quests**. The blocked state
is real; it is just derived, and nobody hand-maintains a redundant status field.
That is correct behavior from the human, and a gap in the tool.

## Spec

### Scope

**In:** the four computed fields, comparison operators, blocked marking in table
output.
**Out:** the views themselves ([[QST-37n0t--built-in-views-next-stale-blocked-and-quest-deps]]), `--select`/`--distinct` ([[QST-8hjjk--allow-for-select-and-distinct-when-listing-quests]]).

### Approach

| Field | Type | Meaning |
|-------|------|---------|
| `blocked` | bool | any `blocked_by` ref resolves to a **non-terminal** quest |
| `blocks` | int | how many **non-terminal, non-archived** quests list this one |
| `idle` | int | days since `status_changed` (falling back to `created`) |
| `age` | int | days since `created` |

They behave like any other field for `--where`, `--select` and `--sort`, and are
**read-only** — `quest set <id> blocked=true` is an error.

**`archived` is deliberately *not* one of these** — it is a stored core field
([[QST-lcsza--archive-a-whole-quest-log-instead-of-individual-quests]]), so it needs no derivation. It is named
here only because the computed fields must honor it.

**`blocks` counts only non-terminal, non-archived quests**, mirroring `blocked`,
which already only counts non-terminal dependencies. The symmetry is the
argument: both answer "what is actually in the way", so both must ignore work
that has already stopped moving. A raw reverse-edge count inflates permanently
and worst on the oldest quests — a quest whose three dependents are all `done`
would read as high-priority with nothing waiting on it. The raw historical graph
is `quest deps --blocks`, which is a view, not a ranking input.

**`--where` gains `!=`, `>`, `<`, `>=`, `<=`**, parsed **before** `=` so `>=` is
not shredded into `>` plus a stray `=`. Check order: `:exists`, `!=`, `>=`, `<=`,
`~`, `>`, `<`, `=`. ISO dates compare correctly as plain strings, so
`--where status_changed<2026-08-05` needs no date parsing at all. `!=` is also
what the schema's `readiness:` rules use
([[QST-j68u5--schema-engine-field-order-defaults-macros-typed-fields-strict-writes]] rule 15) — one expression
language, two consumers.

**`blocked` is now unambiguous.** [[QST-j68u5--schema-engine-field-order-defaults-macros-typed-fields-strict-writes]] removes `blocked`
from the core `status` enum and makes it a schema validation error for any log to
re-declare it, precisely so that `--where blocked=true` has exactly one meaning.
Without that, a quest could be `status: blocked` with no dependencies (computed
`false`) or the reverse, and `--where blocked=true` versus `--where status=blocked`
would be two different questions one word apart.

**Marking.** A blocked row renders its status cell as `todo [blocked]`. ASCII, so
it survives a PowerShell terminal; self-documenting, so no legend is needed; and
it costs width only on affected rows. A gutter column and a Unicode glyph were
both considered and rejected on those grounds.

**Scope.** `blocked` and `blocks` are computed over the **active log set**. In a
single-log listing, `blocks` counts same-log reverse edges only; with [[QST-yiep7--qualified-cross-log-references-in-blocked-by]],
qualified refs to logs present in the sweep are included. The summary block
([[QST-iqwjm--multi-log-query-ux-all-logs-repeatable-in-and-root-per-log-grouping-summary-block]]) states the scope, so a partial count is never mistaken for a total.

**Cost.** At 129 quests this is unmeasurable; at 1,000 it is a few hundred ms of
YAML parsing. Do not build a cache — a cache is a generated artifact, and
generated artifacts in this vault sync into conflict litter.

### Why this is the right layer

An earlier framing had each view carrying its own bespoke logic, justified by
"things `--where` cannot express". Pushing the derivation down one layer is
better: **one computation, many consumers.** The same `blocked` value marks the
default list, defines the `blocked` view, and filters `next`. And `blocks` is
what makes [[QST-xk7js--quest-brief-a-self-contained-work-order-and-the-batch-capture-that-feeds-it]]'s priority signal a number rather than a paragraph.

## Open Questions

None. The terminal-status question this depended on is resolved in
[[QST-j68u5--schema-engine-field-order-defaults-macros-typed-fields-strict-writes]] (rule 10): `terminal_statuses` is a declarable,
ordered schema key defaulting to `[completed, scrapped]`, and a log that
overrides `statuses:` without a surviving default must declare it or fail loudly
at config load.

## Acceptance Criteria

- [ ] `blocked`, `blocks`, `idle`, `age` are available to `--where`, `--select` and `--sort`
- [ ] `--where idle>14` filters numerically
- [ ] `--where status_changed<2026-08-05` filters lexically on ISO dates
- [ ] `>=` and `<=` parse correctly and are not shredded by the `=` branch
- [ ] Default `quest list` renders blocked rows as `todo [blocked]`
- [ ] `quest set <id> blocked=true` errors — computed fields are read-only
- [ ] `blocked` resolves against the log's `terminal_statuses`, not a hardcoded pair
- [ ] `blocks` excludes terminal and archived quests from its count
- [ ] `blocks` and `blocked` honor the stored `archived` field
- [ ] `--where status!=draft` filters correctly and `!=` is not shredded by the `=` branch
- [ ] `blocks` counts reverse edges across the active log set, and the summary states that scope
- [ ] A quest with no `status_changed` gets `idle` from `created`

## Log

- 2026-08-19: `blocked` removed from the core status enum so the computed field owns the name outright.
- 2026-08-19: captured. The corpus check that motivated it: 0 uses of `status: blocked`, 8 quests genuinely blocked by an open dependency.
