---
id: QST-f6otu
title: Markdown output format for quest list and views
description: A md output format rendering list and view rows as a Markdown bullet list — the changelog primitive the release helper consumes.
project: questkit
type: feature
status: done
priority: medium
tags:
  - questkit
  - cli
  - release
created: 2026-08-22
status_changed: 2026-08-24
modified: 2026-10-16
agentic: hitl
aliases:
  - QST-f6otu
blocked_by: []
component:
effort: s
milestone: 0.4.0
related_adrs:
---

## Spec

`--format md` on `quest list` — and therefore on every view: rows
render as a Markdown bullet list honoring `--select` (field order),
`--sort`, `--limit`, and multi-log grouping (`###` heading per log).
Line shape to converge in-session (hitl); starting candidate:

    - **QST-bo3xs** Checklist-progress computed fields *(feature, 0.4.0)*

This is the changelog primitive:

    quest list --where "milestone=0.4.0;status=done,scrapped" --sort type --format md

QST-cv23q's release helper consumes it for the CHANGELOG section;
grouping lines under Added/Fixed/Changed headings stays that script's
job (release-drafter-style category mapping from `type`).

## Acceptance Criteria

- [ ] --format md on list and every view
- [ ] Honors --select/--sort/--limit and per-log grouping
- [ ] Human sign-off on the line shape before done
- [ ] Tests + docs

## Log

- 2026-08-22: captured from R&D catalog REL-1 (option 2 of the review), accepted for 0.4.0, hitl
- 2026-08-24: Implemented for questkit v4 (milestone 0.4.0), TDD, full suite green.

