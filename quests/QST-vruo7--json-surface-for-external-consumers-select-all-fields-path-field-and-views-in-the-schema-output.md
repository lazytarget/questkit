---
id: QST-vruo7
title: "JSON surface for external consumers: select all fields, path field and views in the schema output"
description: Select all fields (including body), expose a path field per quest, and include views in 'quest schema --format json' — the three gaps questkit-pages hit in the 0.4.0 JSON output.
project: questkit
type: feature
status: todo
priority: medium
tags:
  - questkit
  - cli
  - json
  - pages
created: 2026-10-21
modified: 2026-10-21
agentic: hitl
aliases:
  - QST-vruo7
blocked_by: []
component: cli
effort: s
milestone: 0.5.0
related_adrs:
tier: brief
---

## Description

Three small gaps in questkit's JSON surface, found while planning
[[QST-97lsa--questkit-pages-publish-a-quest-log-as-a-static-website-via-a-github-action]].
Each is checked against the released `0.4.0`. Each is independently useful to any tool that
consumes `--format json`, so none is specific to questkit-pages.

| # | Gap | Today (0.4.0) | Wanted |
|---|-----|---------------|--------|
| U1 | No way to select every field | `quest list --select` needs every field named; `*` and `all` are rejected, and the valid field list only appears inside the error message | A way to select all fields including `body`, such as `--select all` or `--select +body` (extend the defaults) |
| U2 | No file location per quest | `path` is not a selectable field | A `path` field (relative to the log root, or absolute) usable in `--select` and `--format json` |
| U3 | Views are not discoverable | `quest schema quest --format json` has no `views` key | `views` in the schema JSON: names plus the resolved `where` / `sort` / `limit` prefills, with per-log overrides applied |

Why each matters to a consumer:

- **U1:** a consumer has to hardcode the field list, or parse it out of an error message,
  and a log's custom schema fields would be missed.
- **U2:** deriving a path from the log path and the id re-implements questkit's filename
  rules (id plus slug).
- **U3:** a consumer can only list the built-in views by name and cannot learn a log's
  overrides, because `views:` fully replaces the built-in map.

## Scope

- Pick the U1 spelling and document it in `quest list --help`, the README and `docs/questkit.md`.
  It must compose with `--where`, `--any` and `--view`, and must not change the default output.
- `path` is read-only like the other computed fields, and is valid in `--where` and `--sort`.
- `views` in the schema JSON reflects the *resolved* map for the log selected by `--in`.
- Out of scope: a JSON mode for `quest show` (`quest list --where id=... --select all`
  covers it), and any change to the table output.

## Acceptance Criteria

- [ ] `quest list --format json` can return every field including `body` and custom schema fields, without naming them
- [ ] The all-fields option is rejected, with a clear error, for formats that cannot carry `body` (matches the existing `--select body` rule)
- [ ] `path` is a selectable, filterable and sortable field; the value points at the quest file
- [ ] `quest schema quest --format json` includes `views`, with a log's `views:` override replacing the built-in map
- [ ] Tests for each, `docs/questkit.md` and the README updated, an entry in `CHANGELOG.md`

## Log

- 2026-10-21: captured while planning QST-97lsa. Checked against the `0.4.0` release from PyPI: none of the three exists, and no existing quest covers them.

