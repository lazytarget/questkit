---
id: QST-tok0k
title: Milestone view and burnup in the development schema
description: A views.milestone in the development schema; a specific milestone is selected via two-layer precedence, burnup counts via group-by milestone and status.
project: questkit
type: feature
status: todo
priority: medium
tags:
  - questkit
  - schema
  - query
  - release
created: 2026-08-22
modified: 2026-08-22
agentic:
aliases:
  - QST-tok0k
blocked_by:
  - QST-oguay
component:
effort: xs
milestone: 0.4.0
related_adrs:
---

## Spec

The `development` schema declares:

    views:
      milestone: { where: ["milestone:exists"], sort: "milestone:desc,status:asc" }

"Which milestone" needs no view parameter — two-layer precedence
already answers it: `quest list --view milestone --where
"milestone=0.4.0"` replaces the view's own milestone clause with the
caller's. Burnup counts ride on group-by (QST-oguay):

    quest list --view milestone --group-by milestone,status

## Acceptance Criteria

- [ ] views.milestone in development.yaml, reachable via --view
- [ ] Burnup one-liner documented (docs §6 views + schema comments)
- [ ] Works under -A across the four development logs

## Log

- 2026-08-22: captured from R&D catalog REL-3, accepted for 0.4.0
