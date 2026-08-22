---
id: QST-jkru7
title: Obsidian plugin as the primary mobile capture path
description: A command in the existing self-built Obsidian plugin mints an id and creates a correctly-named quest from the generated template — Templater and quest adopt held as fallbacks.
project: questkit
type: feature
status: todo
priority: medium
tags:
  - questkit
  - obsidian
  - mobile
  - capture
created: 2026-08-22
modified: 2026-08-22
agentic: hitl
aliases:
  - QST-jkru7
blocked_by: []
component:
effort: m
milestone: 0.5.0
related_adrs:
---

## Spec (experiment first — agentic: hitl)

Primary: a minimal command in the existing self-built Obsidian plugin
(distributed via `make pull-obsidian` / `make apply-realm` — no
publishing needed): "New quest" -> prompt for title -> mint 5-char
base36 id -> create the correctly-named `QST-<id>--<slug>.md` from the
log's `_template.md` with macros filled -> open it. One tap, valid
filename at birth, family-usable on Android.

Fallbacks, held until the plugin experiment is evaluated:

- R&D MOB-2 — Templater (`tp.system.prompt` + `tp.file.rename`):
  no-code, works on mobile, but schema logic lives in template JS
  outside validate's reach
- R&D MOB-1 — `quest adopt`: a generic CLI verb (find `NEW--*.md`,
  mint, rename, normalize; the realm-01 timer merely schedules it) as
  the backstop for capture with no plugin at all

## Acceptance Criteria

- [ ] Plugin command creates a valid, correctly-named quest from _template.md
- [ ] Verified on Android Obsidian (the family surface)
- [ ] Decision recorded whether MOB-2/MOB-1 fallbacks are still needed
- [ ] Human evaluation of the experiment before done

## Log

- 2026-08-22: captured from R&D catalog MOB-5 + MOB-2 + MOB-1 (combined, plugin primary), milestone 0.5.0 chosen
