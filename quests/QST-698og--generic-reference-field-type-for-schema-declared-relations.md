---
id: QST-698og
title: Generic reference field type for schema-declared relations
description: A ref/ref-list schema field type giving any custom field blocked_by-grade reference validation and deps traversal — relations become schema authoring.
project: questkit
type: feature
status: todo
priority: medium
tags:
  - questkit
  - schema
  - references
created: 2026-08-22
modified: 2026-10-16
agentic: hitl
aliases:
  - QST-698og
blocked_by: []
component:
effort: m
milestone: 0.5.0
related_adrs:
---

## Spec

A `type: ref` / `type: ref-list` field type in the schema engine, so
any custom field gets `blocked_by`-grade reference semantics with zero
new core fields:

- values are bare `QST-xxxxx` or qualified `project/QST-xxxxx` ids
- `quest validate` applies the blocked_by rules verbatim (local must
  resolve; qualified with the log absent is a note, never an error)
- `quest deps --via FIELD` traverses a declared ref field
- `blocked_by` stays the only core relation; `relates_to` and
  `discovered_from` (R&D AX-1) become one-line declarations in
  `development.yaml` when a real need appears — declaring them is
  deliberately NOT part of this quest
- heterogeneous references (URLs, files, quests) stay a `## References`
  body convention needing no code

## Acceptance Criteria

- [ ] ref/ref-list validated like blocked_by, incl. qualified refs
- [ ] deps --via walks a declared ref field
- [ ] quest schema surfaces the type
- [ ] Tests + docs (§8)
- [ ] Human review and explicit acceptance of the design before this
      quest may be marked done (required 2026-08-22)

## Log

- 2026-08-22: captured from R&D catalog SCH-1 + AX-1 (generic mechanism instead of hardcoded relation fields), accepted for 0.5.0, hitl

