---
id: QST-j68u5
title: "Schema engine: field order, defaults, macros, typed fields, strict writes"
description: field_order normalization, schema.fields defaults with macros, --fill-defaults, enum-typed custom fields, generic --set, and strict CLI writes.
created: 2026-08-19
modified: 2026-08-19
type: feature
tier: blueprint
status: todo
priority: high
effort: l
project: questkit
tags:
  - questkit
  - schema
  - cli
  - dx
blocked_by:
  - QST-mjuau
  - QST-3h09k
aliases:
  - QST-j68u5
agentic: afk
---

## Description

Seven changes to `schema.py` / `config.py` / the capture path that **ship together
because they are unshippable apart**: the moment any log declares a
`required: true` field, `quest validate` fails every quest that predates it and
the pre-commit hook blocks every commit — unless `--fill-defaults` lands in the
same release. Likewise `field_order` is meaningless until something writes
defaults worth ordering, and `--set` is unsafe until the schema can say which
field names are real.

v2 built the schema engine with **no consumer in the room**. The first real ones
(`development` for the four code logs, `household` for family/home) bend it in
three places at once, which is the argument for building against a real
vocabulary rather than writing reference docs for a shape that cannot survive
contact.

## Spec

### Scope

**In:** field ordering, defaults, macros, typed custom fields, strict CLI writes,
generic `--set`, `--fill-defaults`, named-schema resolution, and the `development`
schema as the first consumer.
**Out:** `--body -` / `--batch -` ([[QST-xk7js--quest-brief-a-self-contained-work-order-and-the-batch-capture-that-feeds-it]]), views in the schema file ([[QST-37n0t--built-in-views-next-stale-blocked-and-quest-deps]]),
the Obsidian template that consumes all of this ([[QST-5rjla--obsidian-capture-surface-generated-template-md-topology-rows-bases-triage-view]]).

### Approach

**1. `field_order` — one rule, not three.** An explicit ordered list, then
everything else alphabetically. No native-vs-custom distinction: that boundary is
itself schema-defined, so a rule that depends on it breaks the moment `tier` is
core in one log and custom in another.

```yaml
field_order: [id, title, description, project, type, status, priority, tags, created, status_changed, modified]
```

Unlisted fields — native or custom — sort alphabetically after. Overridable per
log/schema.

**Must drive `quest new` as well as `quest format`.** `commands/new_cmd.py`
currently hardcodes its own order (`id, title, description, created, modified,
type, tier, status, priority, project, <custom>, tags, blocked_by, aliases`), so
without this every freshly captured quest is immediately non-conformant and the
next `quest format` rewrites it.

**2. Defaults in one place.** `schema.fields.<name>.default` is canonical;
top-level `defaults:` becomes sugar writing into the same merged map. Precedence,
documented once: `--flag` > `fields.<n>.default` > `defaults.<n>` > built-in.

**3. Macros.** `{{ project }} {{ log }} {{ id }} {{ slug }} {{ title }}
{{ today }} {{ owner }} {{ env.USER }}`. Plain substitution, no control flow, no
new dependency. One evaluation point: **after id generation, before first save**,
so `{{ id }}` and `{{ slug }}` are always available and there are no ordering
surprises.

**4. `FieldSpec` gains `type: enum` + `values:`.** Today it carries only
`name`/`type`/`required` and `type` is validated against nothing. Three
independent features need this: grocy's `component`, the `development` schema's
`related_adrs`, and `--set` value checking.

**5. `strict`.** Schema-block key, inheritable via `extends:`, **default `true`**.
Governs the **CLI write path only** — a `--set` naming a field the schema does not
declare is a hard error listing the valid names. Hand-edited frontmatter stays
lenient forever, because Obsidian must remain free to add fields. With
`strict: false` the same case still **warns on stderr**; silent is never correct
here, because the failure mode is a field that appears in no filter, fails no
validation, and is only ever found by grep months later.

**6. Generic capture.** `quest new "title" --set component=x --set effort=s`,
keeping `--type` / `--status` / `--priority` / `--description` / `--tag` as
shorthands for fields every schema has. Retire `--tier` when `tier` demotes.
argparse cannot grow a flag per custom field — the parser is built before the log
is resolved.

`quest set` keeps positional assignments (`quest set <id> field=value ...`). The
asymmetry has a cause: `new` has a positional title, so `quest new "fix thing"
type=bug` is genuinely ambiguous, while `set`'s id + `nargs="+"` is not. A
`--set` passed to `quest set` produces a helpful error naming the right form, not
a second grammar.

**7. `quest format --fill-defaults`** backfills declared defaults into files
missing the field. Hard prerequisite for adopting any `required: true` field
against the live corpus.

**8. `required: true` + a *static* default emits a warning** — the combination is
validation theater (a mandatory field nobody ever thinks about). It stays legal,
because a *computed* default that genuinely varies (`{{ env.USER }}` on `owner`)
carries real information.

**9. Named schemas resolve from `99-system/questkit/schemas/<name>.yaml`** via a
configurable search path, falling back to path-relative `extends:` for a bare
path. **Not the Realm root** — `99-system/syncthing.yaml` has no folder for `.`,
so a file there reaches no other device; it would resolve on one machine and fail
silently everywhere else.

### Alternatives

| Option | Verdict | Reason |
|--------|---------|--------|
| `{{ name }}` substitution | ✅ Chosen | Strict subset of Jinja syntax, so adopting Jinja later costs nothing |
| Jinja2 | ❌ | Large dependency for substitution into a Markdown skeleton; `{% if %}` turns a body template into something you debug |
| `$PROJECT` | ❌ | Reads as shell/env interpolation in YAML; the first thing anyone tries is `$HOME` |
| Three-group field ordering (native ordered / native alpha / custom alpha) | ❌ | Requires questkit to know native-vs-custom, which is schema-defined; same quest would sort differently in two logs and `quest mv` would silently reorder |
| `strict: false` default | ❌ | Every existing log has no schema block, so the protection would be absent exactly where typos are most likely |
| Demote `tier`/`effort` to `development` | ❌ | `xs|s|m|l|xl` and `spark|brief|blueprint` describe any unit of work including a chore. Only `component`/`related_adrs` are software-specific. Demoting a universal vocabulary loses validation on the 20 files already carrying `effort`. |

## Open Questions

- **Terminal statuses under a custom schema.** `OPEN` in [[QST-3ehhu--quest-logs-inventory-every-quest-log-under-a-root]] and the
  `blocked`/`next` computations in [[QST-b9lqo--computed-fields-and-comparison-operators-for-where]] both need to know which of a log's
  statuses mean "done". Hardcoding `completed`/`scrapped` breaks any log that
  overrides `statuses:`. Either `SchemaConfig` declares its terminal set, or
  consumers degrade. **Load-bearing in two places — decide here, not there.**

## Acceptance Criteria

- [ ] `field_order` drives both `quest new` and `quest format`
- [ ] Fields absent from `field_order` sort alphabetically after those present
- [ ] A log or named schema can override `field_order`
- [ ] `{{ project }}`, `{{ today }}`, `{{ id }}`, `{{ env.USER }}` expand in defaults at creation
- [ ] `type: enum` + `values:` rejects an out-of-vocabulary value for a custom field
- [ ] `quest new --set <undeclared>=x` errors under strict, naming the valid fields
- [ ] `strict: false` warns on stderr for the same case
- [ ] `strict` is inherited through an `extends:` chain
- [ ] `quest set <id> --set f=v` errors with a message naming the positional form
- [ ] `quest format --fill-defaults` backfills declared defaults and is idempotent
- [ ] `required: true` with a static default emits a warning; with a macro default it does not
- [ ] `schema: development` resolves from `99-system/questkit/schemas/`
- [ ] The `development` schema exists and declares `component` and `related_adrs`
- [ ] `quest schema quest` reflects everything above

## Log

- 2026-08-19: captured. Bundled deliberately — a `required: true` field is unshippable against a 129-quest corpus without `--fill-defaults` in the same release.
