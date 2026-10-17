---
id: QST-whcdp
title: Quest doctor diagnoses environment logs and installs
description: One read-only diagnosis pass over env, logs and installs — duplicate ids, conflict copies, orphaned quest files, broken configs, stale hook pins.
project: questkit
type: feature
status: done
priority: medium
tags:
  - questkit
  - cli
  - dx
  - maintenance
created: 2026-08-22
status_changed: 2026-08-24
modified: 2026-10-16
agentic:
aliases:
  - QST-whcdp
blocked_by: []
component:
effort: m
milestone: 0.4.0
related_adrs:
---

## Spec

`quest doctor [--root DIR ...]`: read-only, exit 1 when problems found.
The checks (accepted 2026-08-22):

1. duplicate ids across logs — nothing checks this today; the
   resolution sweep silently picks the first sorted path
2. Syncthing conflict copies present (companion to the enumeration
   exclusion fix)
3. orphaned `QST-*.md` outside any log — e.g. the unexplained
   90-playground/.stversions artifact (plan v3 §14)
4. broken log configs aggregated (extends/#include/version) instead of
   per-command scrolling warnings
5. hook-pin staleness: consuming repos' `rev:` vs questkit HEAD
6. install sanity: editable-install path exists; shared-venv vs
   uv-tool version agreement
7. env sanity: QUEST_LOG/QST_ROOT pointing at real logs
8. generated-artifact drift: _template.md/quests.base older than the
   schema chain that generates them

Text output; `--format json` follows the validate finding shape
(QST-njwu7).

## Acceptance Criteria

- [ ] All eight checks, each individually tested
- [ ] Read-only; exit 0/1; --format json
- [ ] Docs (§6, plus a troubleshooting pointer in §10)

## Log

- 2026-08-22: captured from R&D catalog CLI-5, accepted for 0.4.0
- 2026-08-24: Implemented for questkit v4 (milestone 0.4.0), TDD, full suite green.

