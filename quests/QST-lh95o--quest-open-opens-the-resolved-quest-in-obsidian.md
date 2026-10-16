---
id: QST-lh95o
title: Quest open opens the resolved quest in Obsidian
description: quest open <id> opens the resolved quest via an obsidian:// URI with $EDITOR fallback — the gh --web analog.
project: questkit
type: feature
status: done
priority: medium
tags:
  - questkit
  - cli
  - dx
  - obsidian
created: 2026-08-22
status_changed: 2026-08-24
modified: 2026-10-16
agentic:
aliases:
  - QST-lh95o
blocked_by: []
component:
effort: s
milestone: 0.4.0
related_adrs:
---

## Spec

`quest open <id>`: resolve like `show`, then launch
`obsidian://open?path=<absolute path>` via the platform opener
(`xdg-open`/`open`/`os.startfile`). Obsidian resolves the vault
containing the path itself — verify behavior when the file lies in a
nested vault (realm-root vault vs per-zone vault) and document which one
wins. Fallback order when no opener/Obsidian: `$EDITOR`, else print the
path. `--editor` flag to skip Obsidian explicitly.

## Acceptance Criteria

- [ ] `quest open <id>` launches the obsidian:// URI
- [ ] Graceful fallback to $EDITOR / path printing
- [ ] Nested-vault behavior verified and documented
- [ ] Tests (URI construction) + docs

## Log

- 2026-08-22: captured from R&D catalog CLI-4, accepted for 0.4.0
- 2026-08-24: Implemented for questkit v4 (milestone 0.4.0), TDD, full suite green.

