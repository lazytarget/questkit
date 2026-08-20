---
id: QST-j68u5
title: "Schema engine: field order, defaults, macros, typed fields, strict writes"
description: field_order normalization, schema.fields defaults with macros, --fill-defaults, enum-typed custom fields, generic --set, and strict CLI writes.
created: 2026-08-19
status_changed: 2026-08-19
modified: 2026-08-20
type: feature
tier: blueprint
status: todo
priority: high
effort: l
milestone: 0.3.0
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
A `--set` naming a field the schema does not declare is a hard error listing the
valid names, and — see rule 16 — an undeclared field found *in a file* is a
validation error too, with an allowlist for Obsidian's reserved property names.
With `strict: false` the same case still **warns on stderr**; silent is never correct
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

**10. Vocabularies become ordered sequences, not sets — and this is load-bearing.**

`statuses`, `priorities`, `efforts`, `tiers` and `types` are `frozenset`s today,
so `list_cmd._apply_sort` falls back to a lexicographic string sort:

| Sort | What it actually returns today |
|------|--------------------------------|
| `--sort priority:asc` | critical, **deferred**, high, low, medium |
| `--sort effort:asc` | l, m, s, xl, xs |
| `--sort tier:asc` | blueprint, brief, spark |

So the `next` view ([[QST-37n0t--built-in-views-next-stale-blocked-and-quest-deps]]), specified as
`sort: priority:asc,effort:asc`, would rank a `deferred` quest second. This is
not a polish item — **ordered vocabularies are a prerequisite for `next` to mean
anything.**

Declaration order becomes sort order; membership still uses a set internally;
`quest schema quest <field>` prints the declared order rather than a sorted one.

```yaml
statuses:   [draft, todo, in-progress, parked, done, scrapped]
priorities: [critical, high, medium, low, deferred]
efforts:    [xs, s, m, l, xl]
tiers:      [spark, brief, blueprint]
```

**A second, independent bug in the same function:** `sort_expr.partition(":")` on
`"priority:asc,effort:asc"` yields field=`priority`, direction=`"asc,effort:asc"`
— the second key is silently dropped and `desc` never matches. **Multi-key sort
does not exist.** `next` needs it. Fix both together: parse comma-separated
`field[:dir]` pairs into a tuple key.

**11. Terminal statuses become declarable — and required when you override the
vocabulary.** Four things need to know which statuses mean "finished":
`quest logs`' `OPEN` column, the `blocked` computation, `stale`'s exclusion set,
and what `quest done` writes. Hardcoding breaks the first log that overrides
`statuses:`.

```yaml
schema:
  statuses: [draft, todo, in-progress, in-review, shipped, cancelled]
  terminal_statuses: [shipped, cancelled]     # ordered — `quest done` writes the first
```

`terminal_statuses` defaults to `[done, scrapped]` intersected with the declared
statuses, and is **the tail of `statuses`** in the default vocabulary — the two
lists agree by construction rather than by discipline. If a log overrides
`statuses:` where **no** default survives and it declares no `terminal_statuses`,
that is a **hard schema error** at config load. Degrading (an `OPEN` column
silently equal to `total`, a `blocked` field always false) is a wrong answer
delivered confidently.

**Draft-ness needs no key.** Its jobs — exempting `description`, and the
not-draft readiness rule — key off `defaults.status`, the status a fresh quest is
born with. A log whose quests start at `todo` has no draft state and the
exemption correctly does not apply.

**The default listing is a view, not a config key.** `quest list`'s implicit
status filter moves into `views.default` ([[QST-37n0t--built-in-views-next-stale-blocked-and-quest-deps]]),
removing the third hardcoded status list rather than replacing it with a third
key.

**12. `completed` → `done`, and `blocked` leaves the enum.**

```
old core: draft | todo | in-progress | blocked | parked | completed | scrapped
new core: draft | todo | in-progress | parked | done | scrapped
```

**`completed` → `done`** makes `quest done` and `status: done` the same word.
The command/value mismatch was defensible; the alignment is worth more at v0.3
than it will ever be again, and the migration is 15 files.

The counterpart stays **`scrapped`**, with **`quest scrap <id>`** added as the
mirror of `quest done` — then the symmetry holds on both axes (`done`/`scrap` as
commands, `done`/`scrapped` as states). `cancelled` was the alternative, and is
what Linear and Jira use, but it imports the **cancelled/canceled spelling trap**
into a CLI enum where users will typo it forever.

**`blocked` leaves the enum** not because it is unused (0 of 129, same as
`parked`, which stays) but because **a status value and a computed field cannot
share a name in a query language**: `--where blocked=true` and
`--where status=blocked` would be two different questions one word apart, and a
quest could satisfy either without the other. `blocked` is derived; `parked` is
the declared state for "deliberately not being worked"; a blocker that is not
itself a quest should become one.

**13. A schema may not declare an enum value colliding with a computed field
name.** `statuses: [..., blocked]` is a schema validation error naming the
collision. Reserved names come from the computed-field registry (`blocked`,
`blocks`, `idle`, `age`, `archived`), so the rule extends itself as that registry
grows. This is what makes rule 12 permanent rather than a tidy-up someone
reverses next year.

**14. `agentic` leaves the core schema entirely.**

`AGENTIC_MODES`, the enum check at `schema.py:157`, and the AFK spec/criteria
rule at `schema.py:161` are all removed. `agentic` becomes a field declared by
the `development` schema:

```yaml
fields:
  agentic: { type: enum, values: [afk, hitl] }
```

The reasoning is the one the core-vs-schema test already gives: **`afk|hitl` is
not a universal vocabulary.** Household work has no unsupervised-agent axis, so
shipping one in the core is questkit having an opinion about what kind of work
its users do. Under `strict: true` a log that has not declared it will hard-error
on `--set agentic=afk` — and that is correct, not collateral damage.

The two hardcoded rules that guarded it (`afk` requires a non-draft status;
`agentic` is meaningless on a `type: epic`) are **not reintroduced elsewhere**.
The epic rule in particular was local taste dressed as a schema invariant: an OSS
user with a different epic convention would get a rule they never asked for and
could not turn off. Rule 15 is the general mechanism that replaces both.

**15. Readiness rules move into the schema.**

```yaml
readiness:
  - require: { where: "description:exists" }
    message: "no description"
  - require: { where: "status!=draft" }
    message: "still a draft — not groomed"
  - require: { sections: ["## Spec", "## Design"] }        # any-of
    message: "no spec or design section"
  - require: { checklist: "## Acceptance Criteria", min: 1 }
    message: "no acceptance criteria"
  - when: "agentic=afk"                                     # development only
    require: { where: "owner:exists" }
    message: "AFK work needs an accountable owner"
```

Three constructs, each earning its place:

- **`where:` reuses the `--where` grammar verbatim**, computed fields included —
  one expression language, not two. It needs `!=`, which is why the comparison
  operators are rule 19 of this quest rather than a forward dependency on
  [[QST-b9lqo--computed-fields-and-comparison-operators-for-where]].
- **`when:`** guards a rule so it applies conditionally. It exists for exactly one
  reason: it is how "AFK implies spec + criteria" becomes *configuration* instead
  of a hardcoded branch.
- **`sections:` / `checklist:`** are the only body-aware predicates, deliberately
  just two. A third construct and this is a template language.

**The core ships all four universal rules; `household` overrides the list down to
one.** The inverse (minimal core, rigor opted into via a schema) was considered
and rejected: a fresh `pip install questkit` would then print ✅ for a quest with
no spec and no criteria, making the flagship command look useless on day one.
Overriding a list off is one line in a config that already exists; opting into
rigor means authoring a whole schema file. "A spec and acceptance criteria make
work handoff-ready" is not an opinion about a domain — it is what handoff-ready
means.

**Readiness is advisory and never blocks a commit.** `quest validate` stops
enforcing it entirely (see Open Questions). That separation is what makes it safe
for configuration to define these rules at all.

**16. `strict` also governs `quest validate`, with an allowlist for Obsidian.**

Extended from the original CLI-write-path-only scope: under `strict: true`, an
undeclared field found *in a file* is a validation error, not just an error on
`--set`. That is what makes rule 14's migration real rather than cosmetic.

The hazard this creates is specific and worth naming: **Obsidian's Properties
panel adds fields.** In the family log, where nobody can read a terminal, a
stray `cssclasses` would produce a permanent validation error. So the core
schema carries a short **allowlist of Obsidian-reserved property names** —
`cssclasses`, `cssclass`, `permalink`, `publish`, `cover`, `image` — that are
permitted but unmanaged. Allowlisted, not silently ignored: `quest schema quest`
lists them so their status is discoverable.

**17. `archived` joins the core fields.** A boolean, defaulting to absent.
Retention is universal — every domain archives — so it passes the same
core-vs-schema test that kept `tier` and `effort`. It sorts into the alphabetical
tail of `field_order`, not the explicit head: rarely set, never scanned. See
[[QST-lcsza--archive-a-whole-quest-log-instead-of-individual-quests]] for why it is a stored field rather than a
status value or a log-config key.

**18. The `development` schema gains `milestone:`.** A free-text planning bucket
(`0.4.0`, `spring-2027`), enabling "what shipped when" queries and release-note
generation.

Named `milestone` rather than `planned_version` because it is a bucket that can
slip, not a fact, and rather than `version` because that would read as "which
questkit version" beside the config's own `version: 1`. **`milestone` therefore
leaves the core `types` enum** (0 uses in 129; `epic` already covers a grouping
quest), per rule 13.

It is **not** a membership link — questkit has no parent/child concept and v3
does not add one.

**Already in use, retroactively.** All 23 quests in questkit's own log carry a
`milestone:` as of 2026-08-21 — `0.1.0` on the founding blueprint, `0.2.0` on the
v2 work, `0.3.0` on this epic's build order, `0.4.0` on the two items that are
not required for v3 to be coherent. The repo has **no git tags and no
CHANGELOG**, so this field is currently the only machine-readable record of what
shipped when; retro-tagging three finished quests costs nothing and makes
`quest list --where milestone=0.2.0` answer a question that otherwise has no
source at all.

**That sharpens the ordering constraint from rule 14.** `agentic` leaving core
meant 16 files depended on `development` existing before `strict: true` lands.
`milestone` makes it **all 23** — every quest in this log. So the sequence is not
negotiable: the `development` schema must exist, and this log must adopt it,
**before** `strict` is enforced. Otherwise the release that introduces strict
validation fails validation on its own tracker.

**19. `--where` gains `!=`, `>`, `<`, `>=`, `<=`.**

Check order: `:exists`, `!=`, `>=`, `<=`, `~`, `>`, `<`, `=` — the compound
operators **must** be tested before `=`, or `>=` is shredded into `>` plus a
stray `=` and the value silently gains a leading `=`. ISO dates compare correctly
as plain strings, so `--where status_changed<2026-08-05` needs no date parsing.

These were originally scoped in [[QST-b9lqo--computed-fields-and-comparison-operators-for-where]], because the
motivating example of a comparison is `idle>14` and `idle` is a computed field.
But rule 15's `readiness:` grammar is written in `!=`, and `b9lqo` sits three
build-order items later — so the operators arrived after their first consumer.
`_parse_where` knows nothing about derivation, so the split is clean: the
operators land here, the fields they make interesting stay there.

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

None outstanding. Two questions were decided here rather than separately because
each was load-bearing in more than one place:

- **Terminal statuses** (rule 11) — needed by [[QST-3ehhu--quest-logs-inventory-every-quest-log-under-a-root]]'s `OPEN`
  column and [[QST-b9lqo--computed-fields-and-comparison-operators-for-where]]'s `blocked` computation.
- **Readiness vs. validation** (rule 15) — `quest validate` stops enforcing
  readiness entirely. The old AFK rule was a category error: it turned a
  *grooming judgment* into a *commit-blocking contract*. `validate` answers "is
  this file well-formed and are its references real"; `readiness` answers "is
  this good enough to hand to someone", which is advisory by nature and belongs
  to `quest brief`. Never both — and a config-defined rule that could block
  commits would be considerably more dangerous than a hardcoded one.

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
- [ ] `statuses`/`priorities`/`efforts`/`tiers`/`types` are ordered sequences, and `--sort <field>` uses declaration order
- [ ] `--sort "priority:asc,effort:desc"` sorts by both keys, in order
- [ ] `quest schema quest status` prints the declared order, not a sorted one
- [ ] `terminal_statuses` defaults to `[done, scrapped]` intersected with the declared statuses
- [ ] Overriding `statuses:` with no surviving default and no `terminal_statuses` is a hard schema error
- [ ] `quest done` writes `terminal_statuses[0]`; `quest scrap` writes `scrapped`
- [ ] `status: completed` is gone; `done` replaces it and `quest done` writes it
- [ ] `blocked` is gone from the core status enum and `quest list` defaults to `todo, in-progress`
- [ ] Declaring an enum value named `blocked`/`blocks`/`idle`/`age`/`archived` is a schema error naming the collision
- [ ] `agentic` is gone from `schema.py` — no enum, no AFK rule, no epic rule
- [ ] `--set agentic=afk` errors under strict in a log that has not declared it
- [ ] `readiness:` rules are read from the schema and drive `quest brief`'s READY verdict
- [ ] A `when:` guard makes a rule conditional on a `--where` expression
- [ ] `sections:` matches any-of; `checklist:` counts items under a heading
- [ ] The core ships all four universal readiness rules; a schema can override the list to fewer
- [ ] `quest validate` enforces no readiness rule and cannot fail on one
- [ ] Under `strict: true`, an undeclared field found in a file is a validation error
- [ ] Obsidian-reserved property names are allowlisted and listed by `quest schema quest`
- [ ] The `development` schema declares `component`, `related_adrs`, `agentic` and `milestone`
- [ ] `milestone` is gone from the core `types` enum
- [ ] questkit's own log adopts `schema: development` **before** `strict: true` is enforced
- [ ] `quest list --where milestone=0.3.0` returns this epic's build order
- [ ] `archived` is a core boolean field, sorting into the alphabetical tail of `field_order`
- [ ] `--where status!=draft` filters correctly and `!=` is not shredded by the `=` branch
- [ ] `>=` and `<=` parse correctly and are not shredded by the `=` branch
- [ ] `--where status_changed<2026-08-05` filters lexically on ISO dates
- [ ] `quest schema quest` reflects everything above

## Log

- 2026-08-21: took the `--where` comparison operators from [[QST-b9lqo--computed-fields-and-comparison-operators-for-where]] as rule 19 — rule 15's `readiness:` grammar consumes `!=`, so they were scheduled three build-order items behind their first consumer.
- 2026-08-21: `milestone:` stamped across all 23 quests in this log, including retroactive `0.1.0`/`0.2.0` on shipped work. Raises rule 14's `development`-before-`strict` constraint from 16 files to every file.
- 2026-08-19: `agentic` demoted out of core and both its hardcoded guard rules replaced by a configurable `readiness:` block; `completed` renamed to `done`; vocabularies made ordered after finding `--sort priority` returns `critical, deferred, high, ...` and multi-key sort silently drops all but the first key.
- 2026-08-19: rules 10-14 added after grilling terminal statuses, the `blocked` status/computed-field collision, and the milestone/planned-version question.
- 2026-08-19: captured. Bundled deliberately — a `required: true` field is unshippable against a 129-quest corpus without `--fill-defaults` in the same release.
