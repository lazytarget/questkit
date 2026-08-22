---
id: QST-00myv
title: Any-groups and semicolon expression lists in the where grammar
description: Semicolon-separated expression lists where the flag names the combinator — any-groups are OR, where lists are AND sugar for repetition.
project: questkit
type: feature
status: todo
priority: medium
tags:
  - questkit
  - query
  - cli
created: 2026-08-22
modified: 2026-08-22
agentic:
aliases:
  - QST-00myv
blocked_by: []
component:
effort: s
milestone: 0.4.0
related_adrs:
---

## Spec

One rule: `;` separates a *list of expressions*; the **flag** names the
combinator. Comma stays OR within one field's values.

- `--any "expr;expr"` (repeatable): the group matches when ANY of its
  expressions does; each group is ANDed with everything else.
- `--where "expr;expr"`: ALL must hold — pure sugar for repeating
  `--where`, no new semantics.

Approved example — resolves as (type=bug OR feature) AND (effort=s OR m)
AND (status=parked OR blocked=true):

    quest list --any "status=parked;blocked=true" --any "effort=s,m" --where "type=bug,feature"

AND-in-one-flag example (the changelog query):

    quest list --where "milestone=0.3.0;status=done,scrapped"

No parentheses, no precedence, no nesting. Views' stored `where:` lists
gain an `any:` sibling so a view can hold the same expressiveness —
confirm shape during implementation.

## Acceptance Criteria

- [ ] `--any` repeatable; OR within a group, AND across groups and clauses
- [ ] `;` in `--where` equivalent to clause repetition
- [ ] Computed and custom fields work in both
- [ ] Summary block discloses any-groups like it discloses where clauses
- [ ] Tests + docs (§6 grammar)

## Log

- 2026-08-22: captured from R&D catalog QRY-1 plus the review side-thought (semicolon in --where), accepted for 0.4.0
