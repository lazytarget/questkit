---
id: QST-5rjla
title: "Obsidian capture surface: generated _template.md, topology rows, Bases triage view"
description: Give the family log a creation surface that is not the CLI, by generating the Obsidian template from the schema instead of hand-writing it.
project: questkit
type: feature
status: done
priority: medium
tags:
  - questkit
  - obsidian
  - dx
created: 2026-08-19
status_changed: 2026-08-22
modified: 2026-10-16
agentic: afk
aliases:
  - QST-5rjla
blocked_by:
  - QST-j68u5
effort: s
milestone: 0.3.0
tier: brief
---

## Description

`02-projects/family/quests` is initialized, syncs to family devices, and contains
**0 quests**. That is not youth; it is a missing surface. Family members can
already *read* (Bases) and *edit* (Obsidian's Properties panel). What does not
exist is a way to **create** a valid quest without the CLI — and the CLI is not
their surface.

## Spec

### Scope

**In:** the generated template, its distribution, a triage Bases view, and Home
Assistant as a second surface.
**Out:** `quest ingest` (only if the template goes unused — that is an
observation to make in a few weeks, not a guess now).

### Approach

**1. `quest init --template`** writes `<log>/_template.md` from the log's merged
schema, defaults and macros ([[QST-j68u5--schema-engine-field-order-defaults-macros-typed-fields-strict-writes]]).

- **`.md`, not `.tmpl`** — the file must be editable in Obsidian on a phone. A
  `.tmpl` is invisible to Obsidian: no rendering, no mobile editing, no Bases. A
  `.md` with `{{ }}` placeholders in real frontmatter also renders as what it
  produces, which is the best documentation it could have.
- **`_` prefix** — sorts first, reads as "not content", and is skipped by both
  `pattern: QST-*.md` and the Bases `file.name.startsWith("QST-")` filter.
- Packaged default at `src/templates/_template.md`; `quest new` prefers the log's
  own if present. This replaces the hardcoded `template.py`.

**Generating it from the schema is what makes this safe.** A hand-written Obsidian
template duplicates schema logic somewhere `quest validate` cannot protect, and it
drifts. A generated one is a build artifact like `quests.base` — regenerated on
schema change, not a parallel implementation.

**2. Distribution via `topology.yaml`**, the same proven route `quests.base`
already uses:

```yaml
- path: .templates/quest.md
  copy: 02-projects/lazytarget/questkit/src/templates/_template.md
  overwrite: true
```

Hardcode one row per vault that has an `.obsidian` directory: the **Realm root**
and **pensieve**. Not `02-projects/common/beans` — the dead system questkit
replaced. Both profiles' `templates.json` already declares `{"folder":
".templates/"}`, and **`.templates/` does not exist at the Realm root yet**, so
this row creates it. The Obsidian-profile route (`make pull-obsidian`) was
considered and rejected: it only handles `.obsidian/` config plus
`.obsidianignore`, and a template is vault content, not config.

**3. Bases triage view.** Add a "Needs attention" view to the generated
`quests.base`: `status == "draft" and description == null`. Grooming becomes a tap
on a surface that already exists. Note the existing view named "Kanban" is a
**table grouped by status** — Bases has no board type here — and that `family`,
`realm-system` and `career-transition` have **no `quests.base` at all**. Family is
the one that matters.

**4. Home Assistant** as capture and view. A local `todo` list → automation on
item-added → `shell_command` on realm-prod-01 → `quest new --in family "{{ item }}"`.
The family already uses HA to-do lists for groceries, so the interaction is one
they have learned, and it needs no new app.

This is also the **cleanest write path in the system**: HA writes *through the
CLI*, on the designated-committer machine, so HA-captured quests arrive with
normalized frontmatter and correct `project:` stamping and never need
`quest format` — unlike Obsidian-authored ones. A `command_line` sensor over
`quest list --in family --format json` feeds a dashboard card, and once
`quest stale` exists ([[QST-37n0t--built-in-views-next-stale-blocked-and-quest-deps]]) an HA notification reaches a person who will
never see a terminal.

**5. `_validation.md`** ([[QST-e6g6t--quest-commit-and-the-designated-committer]]) is the only error channel a phone user will
ever read.

## Acceptance Criteria

- [x] `quest init --template` writes `_template.md` from the log's merged schema
- [x] The template's frontmatter matches what `quest new` would produce for that log
- [x] Regenerating after a schema change updates it
- [x] `_template.md` is excluded by `pattern` and by the Bases filter
- [x] `quest new` uses the log's `_template.md` when present, the packaged one otherwise
- [x] `template.py` is removed
- [x] `quest init --base` emits a "Needs attention" view
- [x] A quest created from the template in Obsidian mobile passes `quest validate`
- [ ] ~~`topology.yaml` rows land it in the Realm root and pensieve vaults, creating `.templates/`~~ → split to [[QST-9bsnv--obsidian-template-distribution-via-topology-yaml-and-home-assistant-capture]], `milestone: 0.5.0`

## Log

- 2026-08-22: closed for v0.3. The remaining item (`topology.yaml` distribution, plus Home Assistant integration from the Spec) is split out to [[QST-9bsnv--obsidian-template-distribution-via-topology-yaml-and-home-assistant-capture]] at `milestone: 0.5.0` — infrastructure in a different part of the Realm, not deployable or testable from this repository.
- 2026-08-20: implemented the in-repo half. New `src/questkit/templates.py` replaces `template.py`: `render_body()` now reads a template file's body section (the log's own `_template.md` when present, else the packaged `src/templates/_template.md`) instead of a hardcoded Python string; `generate_template(config)` produces the frontmatter+body skeleton from the log's merged schema (declared custom fields, `project:`, and the three default-field values), regenerated in full on every `quest init --template` call. `quests.base`'s template gained a "Needs attention" view. **Left open**: the `topology.yaml` rows and Home Assistant integration are infrastructure in a different part of the Realm (or a different system entirely) — not files in this repository, and not deployable or testable from here. The exact rows and HA automation shape are already fully specified in this quest's Spec, ready for whoever has access to `topology.yaml` and the HA instance to apply them.
- 2026-08-19: captured. Generating the template from the schema reverses an earlier objection to Obsidian templates — the objection was drift, and generation removes it.

