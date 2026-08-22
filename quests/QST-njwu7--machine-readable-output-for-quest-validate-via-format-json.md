---
id: QST-njwu7
title: Machine-readable output for quest validate via format json
description: quest validate --format json emitting structured findings (file, rule, kind, message) so agents and CI consume results without scraping stderr prose.
project: questkit
type: feature
status: todo
priority: medium
tags:
  - questkit
  - cli
  - agentic
  - validation
created: 2026-08-22
modified: 2026-08-22
agentic:
aliases:
  - QST-njwu7
blocked_by: []
component:
effort: s
milestone: 0.4.0
related_adrs:
---

## Spec

`quest validate --format json`: a JSON array of findings on stdout, one
object per finding — `{file, id, kind: "error"|"note", rule, message}` —
plus a summary object or trailing counts. Exit-code semantics unchanged
(errors fail, notes never). Human output stays the default.

Should compose with `--report FILE` (the JSON goes to stdout, the
Markdown note to FILE) and with `--no-notes`.

## Acceptance Criteria

- [ ] `--format json` emits stable, documented finding objects
- [ ] Exit codes identical to text mode
- [ ] Composes with `--report` and `--no-notes`
- [ ] Tests + docs

## Log

- 2026-08-22: captured from R&D catalog AX-3, accepted for 0.4.0
