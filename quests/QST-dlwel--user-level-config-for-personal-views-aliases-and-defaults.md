---
id: QST-dlwel
title: User-level config for personal views aliases and defaults
description: A user config file for personal views, aliases and defaults — ergonomics only, never schema or validity, with log config always winning.
project: questkit
type: feature
status: todo
priority: low
tags:
  - questkit
  - cli
  - dx
  - config
created: 2026-08-22
modified: 2026-08-22
agentic:
aliases:
  - QST-dlwel
blocked_by: []
component:
effort: s
milestone: 0.5.0
related_adrs:
---

## Spec

`~/.config/questkit/config.yaml` (XDG; `QUESTKIT_CONFIG` override).
Ergonomics only, never validity:

- precedence: CLI flag > log `.questkit.yaml` > user config > built-in
- MAY contribute: default `root:` (making QST_ROOT optional), personal
  `views:` (merged by name; log/schema wins on collision), command
  `aliases:`, default output preferences
- MAY NOT contribute: vocabularies, fields, readiness — anything
  validation depends on stays per-log / 99-system. A per-device config
  must never make the same file validate differently on two devices.

## Acceptance Criteria

- [ ] User config loaded with the stated precedence
- [ ] Personal views/aliases work; schema keys rejected with a clear error
- [ ] Summary block discloses when a user-defined view is active
- [ ] Tests + docs (§8 gains a user-config subsection)

## Log

- 2026-08-22: captured from R&D catalog CLI-6, accepted; milestone 0.5.0 chosen (0.4.0 is full, and ergonomics lands better after completions/doctor)
