---
id: QST-79rt8
title: Quest ready a scriptable readiness predicate
project: questkit
type: feature
status: draft
priority: low
tags:
  - questkit
  - cli
  - agentic
created: 2026-08-22
modified: 2026-10-16
agentic:
aliases:
  - QST-79rt8
blocked_by: []
component:
milestone:
related_adrs:
---

## Notes (draft)

`quest ready <id>`: evaluate the log's `readiness:` rules plus computed
STATE (blocked/terminal/archived), exit 0/1, `--format json` listing
failing rules. The shell primitive for
`quest ready X && claude -p "$(quest brief X)"`.

Deliberately deferred (v3 §8 and review feedback 2026-08-22): wait until
`quest brief` has been used by hand enough to know what the predicate
should actually be — e.g. whether STATE failures should affect the exit
code, or only READY.

From R&D catalog AX-2. Draft by request, no milestone.

## Log

- 2026-08-22: captured from R&D catalog AX-2 (draft, deferred)

