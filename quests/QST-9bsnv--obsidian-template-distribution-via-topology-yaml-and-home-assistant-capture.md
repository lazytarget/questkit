---
id: QST-9bsnv
title: Obsidian template distribution via topology.yaml, and Home Assistant capture
description: Obsidian template distribution via topology.yaml, and Home Assistant capture
project: questkit
type: feature
status: todo
priority: medium
tags:
  - questkit
  - obsidian
  - dx
created: 2026-08-22
modified: 2026-08-22
agentic: afk
aliases:
  - QST-9bsnv
blocked_by:
  - QST-5rjla
effort: s
milestone: 0.5.0
tier: brief
---

## Description

Split out of [[QST-5rjla--obsidian-capture-surface-generated-template-md-topology-rows-bases-triage-view]],
whose Log flagged this as deliberately left open: `topology.yaml` and the Home
Assistant instance are infrastructure in a different part of the Realm (or a
different system entirely), not files in this repository, and not deployable or
testable from here. The in-repo half — the schema-generated `_template.md` itself,
`quest init --template`, and the Bases "Needs attention" view — shipped in v0.3
(QST-5rjla). This quest is what actually gets the template onto family devices.

## Spec

### Scope

**In:** the `topology.yaml` rows distributing `_template.md`, and the Home
Assistant capture/view integration.
**Out:** `quest ingest` (only if the template goes unused — an observation to make
in a few weeks, not a guess now) — unchanged from QST-5rjla's own scope.

### `topology.yaml` distribution

The same proven route `quests.base` already uses:

```yaml
- path: .templates/quest.md
  copy: 02-projects/lazytarget/questkit/src/templates/_template.md
  overwrite: true
```

One row per vault with an `.obsidian` directory: the **Realm root** and
**pensieve**. Both profiles' `templates.json` already declares `{"folder":
".templates/"}`, and `.templates/` does not exist at the Realm root yet, so this
row creates it.

### Home Assistant capture and view

A local `todo` list → automation on item-added → `shell_command` on realm-prod-01 →
`quest new --in family "{{ item }}"`. The family already uses HA to-do lists for
groceries, so the interaction is one they've learned, with no new app. This is
also the cleanest write path in the system: HA writes *through the CLI*, on the
designated-committer machine ([[QST-kxo5m--designated-committer-timer-and-git-auto-unification]]),
so HA-captured quests arrive with normalized frontmatter and never need `quest
format`. A `command_line` sensor over `quest list --in family --format json` feeds
a dashboard card, and `quest stale` ([[QST-37n0t--built-in-views-next-stale-blocked-and-quest-deps]],
shipped) can drive an HA notification to someone who will never see a terminal.

## Acceptance Criteria

- [ ] `topology.yaml` rows land `_template.md` in the Realm root and pensieve
      vaults, creating `.templates/`
- [ ] A Home Assistant `todo` list automation calls `quest new --in family` via
      `shell_command` on realm-prod-01
- [ ] A `command_line` sensor over `quest list --in family --format json` feeds an
      HA dashboard card

## Log

- 2026-08-22: captured. Split out of [[QST-5rjla--obsidian-capture-surface-generated-template-md-topology-rows-bases-triage-view]] and retargeted to `milestone: 0.5.0`, so v0.3 isn't blocked on infrastructure outside this repository.
