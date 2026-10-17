---
id: QST-hzlny
title: quest set / new --set store blocked_by as a string; validate then checks it character by character
description: set_cmd._coerce only splits tags, so blocked_by=QST-x (or [QST-x]) is written as a YAML string; validate iterates the string and reports one 'not found' error per character.
project: questkit
type: bug
status: done
priority: high
tags:
  - questkit
  - cli
  - correctness
created: 2026-10-13
status_changed: 2026-10-16
modified: 2026-10-16
agentic: afk
aliases:
  - QST-hzlny
blocked_by: []
component:
effort: s
milestone: 0.4.0
related_adrs:
---

## Spec

### Repro (questkit 0.3.0, 2026-10-13, home-lab log)

```sh
quest new "Some task" --set blocked_by='[QST-eg94z]' --in quests
#   -> frontmatter: blocked_by: '[QST-eg94z]'
quest set --in quests QST-2aow5 blocked_by=QST-eg94z
#   -> frontmatter: blocked_by: "QST-eg94z"
quest validate
#   error: blocked_by references 'Q', not found in this log
#   error: blocked_by references 'S', not found in this log
#   ... one error per character
```

Workaround used: hand-edit the frontmatter to a YAML list.

### Root cause

- `commands/set_cmd.py::_coerce` special-cases only `tags` (comma split) and
  `archived` (bool); every other key, including list-typed `blocked_by`, is
  written as the raw string.
- `commands/new_cmd.py`: `--set k=v` values are always strings (the
  `_NewSpec.sets` comment says so); only `--batch` keeps native YAML types.
- `commands/validate_cmd.py` iterates `quest.frontmatter.get("blocked_by") or []`
  without checking the type, so a string is walked character by character.
  The same happens to any other list-typed field.

### Fix

1. Coerce by the **schema's declared type**, not by key name: list-typed
   fields (`blocked_by`, `tags`, `aliases`, any custom list field) split on
   commas and also accept a `[a, b]` YAML flow list. Share one coercion
   helper between `set` and `new --set` (fits the typed-fields work in
   QST-j68u5).
2. `validate`: a list-typed field holding a scalar is one clear error
   ("blocked_by must be a list, got string 'QST-eg94z'"), not N
   per-character errors. Optionally, `quest format` normalizes a scalar into a
   one-item list.
3. Tests: `set blocked_by=A`, `set blocked_by=A,B`, `set blocked_by=[A, B]`,
   `new --set blocked_by=A` all produce YAML lists; `blocked_by=` (empty) clears
   to `[]`; validate on a hand-written scalar gives the single error.

## Acceptance Criteria

- [x] `quest set <id> blocked_by=QST-x` and `quest new ... --set blocked_by=QST-x` write a YAML list
- [x] Comma-separated and `[a, b]` forms both work; empty value clears to `[]`
- [x] `quest validate` reports one type error for a scalar in a list field
- [x] Coercion is driven by the schema's field types, shared by `set` and `new --set`

## Log

- 2026-10-13: hit while creating home-lab QST-2aow5 (blocked by QST-eg94z); root cause read from `set_cmd._coerce` and `validate_cmd` on `main`
- 2026-10-16: Added to milestone 0.4.0.
- 2026-10-16: Implemented: schema-type-driven list coercion shared by set and new --set; validate reports one list-type error.

## Related

- [[QST-j68u5--schema-engine-field-order-defaults-macros-typed-fields-strict-writes]] - typed fields; coercion should use them
- [[QST-yiep7--qualified-cross-log-references-in-blocked-by]] - other `blocked_by` work

