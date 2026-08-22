---
id: QST-46rdv
title: Log flag appends dated entries on set done and scrap
description: A --log message flag on set, done and scrap appends a dated bullet to the quest's Log section (created if missing) in the same save.
project: questkit
type: feature
status: todo
priority: medium
tags:
  - questkit
  - cli
  - dx
created: 2026-08-22
modified: 2026-08-22
agentic:
aliases:
  - QST-46rdv
blocked_by: []
component:
effort: s
milestone: 0.4.0
related_adrs:
---

## Spec

`--log "message"` on `quest set`, `quest done`, `quest scrap`: append
`- YYYY-MM-DD: message` to the quest's `## Log` section in the same
save. **If no `## Log` section exists, create it** (at the end of the
body). `quest set <id> --log "msg"` with zero field assignments is
legal — a pure journal entry; `modified` still bumps.

Deliberately NOT a `quest log` verb: "quest log" already names the
directory concept and `quest logs` the inventory command
(decided 2026-08-22). Transitions get their "why" atomically:

    quest scrap QST-x7k2m --log "superseded by QST-y"

## Acceptance Criteria

- [ ] --log on set/done/scrap, dated, appended in the same save
- [ ] ## Log section created when missing
- [ ] set with only --log is legal; modified bumped
- [ ] Tests + docs

## Log

- 2026-08-22: captured from R&D catalog CLI-3 (revised — flag, not a verb), accepted for 0.4.0
