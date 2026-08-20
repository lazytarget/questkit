---
title: questkit v3 — loop closure, multi-log UX, and agent handoff
description: "Design record for questkit v3: the decisions, the evidence behind them, and the alternatives rejected along the way."
created: 2026-08-19
modified: 2026-08-21
type: plan
status: active
tags:
  - questkit
  - quests
  - framework
  - tooling
  - cli
quest: QST-bmzl2
---

## 1. Context

- **v1** ([[QST-whm2e--questkit-design-blueprint-for-file-based-quest-tracking]]) established the file format, nearest-zone-wins discovery, and the deliberate one-log-per-command rule.
- **v2** ([[QST-v0hnq--questkit-v2-dynamic-schema-engine-and-multi-log-architecture]]) added the per-log schema engine, cross-log query (`quest list --all`), and global-id mutation resolution.
- **v3** is about **what happens after capture.**

Every field and command questkit has today is about getting work *in* and describing it. Nothing surfaces work that is rotting, and nothing helps choose what to do next. Trello — the system questkit replaced — did not die of bad capture; it died of declining engagement with an ever-growing board. Retrofitting hygiene onto a large corpus is far worse than designing it in now.

This document is the design record for the epic [[QST-bmzl2--questkit-v3-loop-closure-multi-log-ux-and-agent-handoff]]. It records **why**, including the roads not taken; the individual quests record **what** and **how**.

## 2. Evidence

Measured across the Realm on 2026-08-19. These numbers drove specific decisions and are recorded so a future reader can tell which conclusions were data-driven and which were taste.

| Signal | Value | Drove |
|--------|-------|-------|
| Corpus | 129 quests, 7 logs | everything |
| Status spread | 86 `todo`, 24 `draft`, 15 `completed`, 3 `in-progress`, 2 `scrapped` | loop-closure focus |
| `status: blocked` | **0** | `blocked` as a *computed* field |
| `status: parked` | **0** | — |
| Quests with ≥1 open dependency | **8** (all `pensieve`) | `quest blocked`, and marking blocked rows in the default list |
| `blocked_by` edges | 21 local, **0 cross-log**, 0 dangling | qualified refs ship with no migration |
| `agentic:` | 1 file of 129 | `quest brief` — wire it or delete it |
| `quests.base` present | 4 of 7 logs (**not** `family`) | the capture-surface quest |
| `.sync-conflict` files | 46, across 15 `.git` directories | one-writer-per-repo |
| Syncthing folder for the Realm root | **none** — folders are `00-inbox`, `01-daily`, `02-projects/<project>`, `03-knowledge`, `04-workbench`, `05-assets`, `06-archive`, `90-playground`, `99-system` | shared schemas live under `99-system/`, never the root |
| `.stignore-gitmeta` | exists, referenced by nothing | the `.git/` exclusion option is already built |
| `status: parked` | **0** | kept — it is the *declared* counterpart to computed `blocked` |
| `type: milestone` | **0** of 129 | removed from core types; `milestone:` becomes a field |
| Review pass, 2026-08-19 | 15 → `agentic: afk`, 1 → `hitl`, 1 → `status: draft` | `status` and `agentic` are separate axes, used differently in one sitting |
| `agentic:` in questkit's own log | 16 of 22 after review | `development` must declare it before it leaves core |
| `--sort priority:asc` | returns `critical, deferred, high, low, medium` | ordered vocabularies are a prerequisite, not polish |
| `--sort "a:asc,b:asc"` | second key silently dropped | multi-key sort does not exist |
| career-transition | 13 quests, **4 finished** | `status: archived` would erase which ones shipped |

**Measured, not assumed** — a pathspec-limited commit does *not* avoid rewriting `.git/index`:

```
baseline index                                     719c9497e7d3
edit files in the worktree (no git command)        719c9497e7d3   unchanged
git commit -m x -- a.md   (no `git add` at all)    dbaffbef9728   REWRITTEN
```

Git's partial-commit path stages the named paths into the **real** index and writes it, then builds a temporary index to create the commit from. The `gitutil.auto_commit` sequence (`git add --` then `git commit --`) rewrites it twice. See §7.

## 3. Positioning

| Question | Decision | Reasoning |
|----------|----------|-----------|
| What is questkit? | A quest **tracker** | Recurrence and the non-ticket collections (Matschema, Städschema, People CRM, watchlists) stay out. Letting them in would widen the noun and the schema at once. |
| Who is it for? | **Personal-first**, structured so open-sourcing stays cheap | The Realm-agnostic discipline is retained because it is cheap and keeps the code clean — but the generality budget is frozen: no new configurability without a real second consumer. |
| Who uses it? | Solo + agents + **family via Obsidian** | `owner` stays free text. The CLI is explicitly **not** the family's surface. |
| Capture or loop? | **Loop** | Capture is the one thing questkit demonstrably nailed. |

## 4. Data model

### `status_changed`

`modified` cannot measure staleness — it is bumped by the `quest-bump-modified` hook on every commit and by `quest format` on every run. The concrete failure: running `quest format --fill-defaults` across the corpus to backfill newly-required fields gives **every** quest a fresh `modified`, laundering the entire backlog into looking freshly worked. That is a scheduled step of v3, not a hypothetical.

`status_changed` sits between `created` and `modified`, is written only when the status actually changes, and falls back to `created` when absent. Backfill seeds from `created` (not `modified`, which is already polluted) and the migration script is parameterized by field so a future timestamp is a re-run, not a rewrite.

Rejected: deriving from git (three logs are `git: manual` inside code repos with interleaved history, and it makes a read-only command shell out per file); `completed_at` (deferred — derivable for `git: auto` logs, uncertain elsewhere, and no v3 command needs it).

→ [[QST-3h09k--status-changed-frontmatter-field-and-reusable-backfill]]

### Field ordering

**One rule:** an explicit ordered list, then everything else alphabetically.

```yaml
field_order: [id, title, description, project, type, status, priority, tags, created, status_changed, modified]
```

A three-group rule (ordered natives → alphabetical natives → alphabetical custom) was rejected because it requires questkit to know which fields are "native" — a boundary that is itself schema-defined. The same quest would sort differently in two logs and `quest mv` would silently reorder frontmatter.

`field_order` must drive `quest new` as well as `quest format`; `new_cmd.py` currently hardcodes its own order, so without this every freshly captured quest is immediately non-conformant.

### Ordered vocabularies — a prerequisite, not polish

`statuses`, `priorities`, `efforts`, `tiers` and `types` stop being `frozenset`s
and become **ordered sequences**. Declaration order is sort order; membership
still uses a set internally; `quest schema quest <field>` prints the declared
order.

This is load-bearing because `list_cmd._apply_sort` sorts lexicographically:

| Sort | What it returns today |
|------|-----------------------|
| `--sort priority:asc` | critical, **deferred**, high, low, medium |
| `--sort effort:asc` | l, m, s, xl, xs |
| `--sort tier:asc` | blueprint, brief, spark |

So `views.next` (`sort: priority:asc,effort:asc`) would rank a `deferred` quest
second. A second bug in the same function compounds it: `sort_expr.partition(":")`
drops every key after the first, so `effort` is never consulted and `desc` never
matches. **Multi-key sort does not exist and `next` needs it.** Both are fixed
together.

### The status enum

Core becomes `draft | todo | in-progress | parked | done | scrapped` — **`blocked`
is removed and `completed` is renamed to `done`.**

**`completed` → `done`** makes `quest done` and `status: done` the same word. The
mismatch was defensible, but the alignment is worth more at v0.3 than it will
ever be again, and the migration is 15 files. The counterpart stays **`scrapped`**,
with **`quest scrap <id>`** added as the mirror of `quest done`.

The counterpart was re-judged from scratch, ignoring incumbency:

| Pair | Verdict |
|------|---------|
| `done` / `scrapped` | ✅ Chosen |
| `done` / `dropped` | ❌ **`drop` means delete in CLI-land** — `git stash drop` removes the stash, SQL `DROP` destroys the table. A user who hesitates before `quest drop QST-x7k2m` is reasoning correctly from convention, and that hesitation never goes away. Also shares an initial letter with `done`, foreclosing any prefix ergonomics. And it is vaguer: "dropped" can mean deprioritized, which is `parked`. |
| `done` / `cancelled` | ❌ The industry standard (Linear, Jira) and `quest cancel` is a fine verb, but it imports the **cancelled/canceled spelling trap** into a CLI enum where half the world types the other spelling |
| `done` / `abandoned` | ❌ Long and judgmental |

`scrapped` is also the more precise word: it means *cancelled after being
planned*, which is exactly the state, and it does not overlap `parked`.

**`blocked` leaves the enum** for a reason that is not disuse (0 of 129, same as
`parked`, which stays). It is that a status value and a computed field **cannot
share a name in a query language**:
with `blocked` computed, `--where blocked=true` and `--where status=blocked`
would be two different questions one word apart, and a quest could satisfy either
without the other. `blocked` is derived; `parked` is the declared state for
"deliberately not being worked"; a blocker that is not itself a quest should
become one.

This generalises into a rule: **a schema may not declare an enum value colliding
with a computed field name** (`blocked`, `blocks`, `idle`, `age`), enforced at
config load. That is what makes the removal permanent rather than a tidy-up
someone reverses in six months.

### Terminal statuses

Four consumers need to know which statuses mean "done": `quest logs`' `OPEN`
column, the `blocked` computation, `stale`'s exclusion set, and what `quest done`
writes. `terminal_statuses` is an **ordered** schema key defaulting to `[done, scrapped]`
intersected with the declared statuses; `quest done` writes the first entry. In
the default vocabulary it is literally **the tail of `statuses`**, so the two
lists agree by construction rather than by discipline — which is why `done` sits
second-to-last in the status order rather than last.

A log that overrides `statuses:` where **no** default survives, and declares no
`terminal_statuses`, is a **hard schema error**. Degrading (an `OPEN` column that
silently equals `total`) is a wrong answer delivered confidently, which is worse
than failing at config load.

Two related concepts get no key of their own. **Draft-ness** derives from
`defaults.status` — the status a fresh quest is born with — so a log whose quests
start at `todo` simply has no draft state and the `description` exemption
correctly does not apply. The **default listing** becomes `views.default`, which
removes the third hardcoded status list rather than replacing it with a third
config key.

### Core vs. schema

`tier` and `effort` **stay core**. The test is not "is this field used everywhere" but "is this vocabulary universal": `xs|s|m|l|xl` and `spark|brief|blueprint` describe any unit of work including a household chore. `component` and `related_adrs` are meaningless outside software and belong in the `development` schema. Demoting a universal vocabulary to shrink the core would also lose validation on the 20 files already carrying `effort`.

`language` follows the same rule and is therefore **not** a core field — see [[QST-onxad--new-frontmatter-attributes]].

`agentic` **leaves core entirely** and becomes a `development` field. The
core-vs-schema test decides it: **`afk|hitl` is not a universal vocabulary.**
Household work has no unsupervised-agent axis, so shipping one in the core is
questkit having an opinion about what kind of work its users do. The objection
that `strict: true` would then hard-error on `--set agentic=afk` in an
un-opted-in log is correct and is *the intended behavior*, not collateral damage.

Both hardcoded rules that guarded it are removed and **not reintroduced
elsewhere**: `afk` requires a non-draft status, and `agentic` is meaningless on a
`type: epic`. The second in particular was local taste dressed as a schema
invariant — an OSS user with a different epic convention would get a rule they
never asked for and could not turn off.

### Readiness becomes configuration

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

Three constructs. **`where:` reuses the `--where` grammar verbatim**, computed
fields included — one expression language, not two (it needs `!=` added).
**`when:`** guards a rule conditionally, and exists for exactly one reason: it is
how "AFK implies spec + criteria" becomes configuration instead of a hardcoded
branch. **`sections:` / `checklist:`** are the only body-aware predicates,
deliberately just two; a third and this is a template language.

**The core ships all four universal rules; `household` overrides the list down to
one.** The inverse — minimal core, rigor opted into — was rejected because a
fresh `pip install questkit` would then print ✅ for a quest with no spec and no
criteria, making the flagship command look useless on day one. Overriding a list
off is one line; opting into rigor is a whole schema file. "A spec and acceptance
criteria make work handoff-ready" is not an opinion about a domain; it is what
handoff-ready means. "Epics can't be AFK" was.

**Readiness is advisory and never blocks a commit** — see §13.

### `strict` also governs validation

Extended from CLI-write-path-only: under `strict: true`, an undeclared field
found *in a file* is a validation error. That is what makes the `agentic`
migration real rather than cosmetic.

The hazard is specific: **Obsidian's Properties panel adds fields**, and in the
family log nobody can read a terminal. So the core carries a short **allowlist of
Obsidian-reserved property names** — `cssclasses`, `cssclass`, `permalink`,
`publish`, `cover`, `image` — permitted but unmanaged, and listed by
`quest schema quest` so their status is discoverable.

**`archived` joins the core fields** — a boolean, defaulting to absent, sorting
into the alphabetical tail of `field_order`. Retention is universal, so it passes
the same core-vs-schema test that kept `tier` and `effort`. See §10 for why it is
a stored field rather than a status value or a log-config key.

`milestone:` joins the `development` schema — a free-text planning bucket
(`0.4.0`, `spring-2027`) for "what shipped when" queries and release notes. Named
`milestone` rather than `planned_version` because it is a bucket that can slip,
not a fact, and rather than `version` because that would read as "which questkit
version" beside the config's own `version: 1`. `milestone` therefore leaves the
core `types` enum (0 uses; `epic` already covers a grouping quest), per the
collision rule above. It is **not** a membership link — questkit still has no
parent/child concept, and v3 does not add one.

### Defaults, macros, typed fields, strict

Shipped as one unit because they are unshippable apart: the moment any log declares `required: true`, `quest validate` fails every quest that predates it and the pre-commit hook blocks every commit, unless `--fill-defaults` lands in the same release.

- **Defaults in one place** — `schema.fields.<n>.default` canonical, top-level `defaults:` as sugar. Precedence: `--flag` > `fields.<n>.default` > `defaults.<n>` > built-in.
- **Macros** — `{{ project }} {{ log }} {{ id }} {{ slug }} {{ title }} {{ today }} {{ owner }} {{ env.USER }}`, expanded after id generation and before first save. Plain substitution, no control flow. Jinja2 was rejected as a large dependency for string substitution into a Markdown skeleton, and because `{% if %}` turns a body template into something you debug; `{{ }}` is a strict subset, so adopting Jinja later costs nothing. `$PROJECT` was rejected because it reads as shell interpolation in YAML and the first thing anyone tries is `$HOME`.
- **`FieldSpec` gains `type: enum` + `values:`** — three separate features need it, and today `type` is validated against nothing.
- **`strict`, default `true`** — governs the CLI write path *and* validation (see above). `strict: false` still warns on stderr: the failure mode is a field that appears in no filter, fails no validation, and is only ever found by grep months later. A lenient default was rejected because every existing log has no schema block, so the protection would be absent exactly where typos are most likely.
- **`required: true` + a *static* default emits a warning** — the combination is validation theater. It stays legal, because a computed default that genuinely varies carries real information.

→ [[QST-j68u5--schema-engine-field-order-defaults-macros-typed-fields-strict-writes]]

### Named schemas

Shared schemas live at **`99-system/questkit/schemas/<name>.yaml`**, resolved via a configurable search path.

**Not the Realm root.** `99-system/syncthing.yaml` has no folder for `.` — the Realm root is a *local composition* of independently-synced folders, not a synced entity. A schema file there would resolve on one machine and fail silently on every other, which is the worst possible failure shape. Generalizes: any questkit artifact that must reach every device belongs under `99-system/`.

Two schemas planned. **`development`** first (`questkit`, `pensieve`, `realm-system`, `grocy-ecosystem`) — it is where the demand signal already lives, since 35 of grocy's 66 titles carry a hand-typed component prefix. **`household`** second (`family`, `home`) — it exercises *vocabulary override* rather than custom fields, and doubles as the partner test. `consulting` is held: three logs that do not exist yet is a schema written for hypothetical users.

## 5. Query engine

### Computed fields

Some of the most useful facts about a quest are not stored in it.

| Field | Type | Meaning |
|-------|------|---------|
| `blocked` | bool | any `blocked_by` ref resolves to a non-terminal quest |
| `blocks` | int | how many quests list this one |
| `idle` | int | days since `status_changed` (falling back to `created`) |
| `age` | int | days since `created` |
**`archived` is deliberately not computed** — it is a stored core field (§10), so
there is nothing to derive. The computed fields must honor it, which is the only
reason it appears here.

**`blocks` counts only non-terminal, non-archived quests**, mirroring `blocked`.
Both answer "what is actually in the way", so both must ignore work that has
stopped moving; a raw reverse-edge count inflates permanently and worst on the
oldest quests. The raw historical graph is `quest deps --blocks` — a view, not a
ranking input.

They behave like any other field for `--where`, `--select` and `--sort`, and are read-only.

**This is the right layer.** An earlier framing gave each view its own bespoke logic, justified by "things `--where` cannot express". Pushing the derivation down one level is better: one computation, many consumers. The same `blocked` value marks the default list, defines the `blocked` view, filters `next`, and gives `quest brief` a priority signal.

`--where` gains `!=`, `>`, `<`, `>=`, `<=`, parsed before `=` so `>=` is not shredded. ISO dates compare correctly as strings, so no date parsing is needed. `!=` is also what `readiness:` rules use — one grammar, two consumers.

→ [[QST-b9lqo--computed-fields-and-comparison-operators-for-where]]

### Views

Views are **pure prefills** defined in the schema file, overridable per log, exposed as bare subcommands:

```yaml
views:
  default: { where: ["status=todo,in-progress"] }
  next:    { where: ["blocked=false"], sort: "priority:asc,effort:asc,idle:desc", limit: 1 }
  stale:   { where: ["idle>14"], sort: "idle:desc" }
  blocked: { where: ["blocked=true"], sort: "blocks:desc" }
```

`views.default` is what pays for the mechanism: `quest list`'s implicit status
filter is hardcoded today and would silently list nothing in a log that overrode
`statuses:`.

Config overrides a built-in's *definition*, never its *command name* — argparse is built before any log resolves, and a CLI whose command list depends on cwd is a debugging nightmare.

Views live in the schema rather than the log config because once four logs share `development` they want the same ranking; that is what makes them the same *kind* of work.

`quest deps` is the exception — a graph walk, not a filter. `blocked_by` is many-to-many, so it is a **DAG, not a tree**: revisited nodes must be marked explicitly or edges get silently dropped. Hence `deps`, not `tree`.

**Rejected views:** `backlog`/`drafts`/`scrapped`/`active` — each is exactly one `--where` clause, and naming one status invites a subcommand per status, which **cannot survive custom schemas**. The real grooming query is `quest stale --where status=draft`. `archive` is reserved for the eventual *mutation* (`career-transition` ends someday). `quest status` is disqualified outright — it would collide with `quest set X status=` and `quest schema quest status`.

→ [[QST-37n0t--built-in-views-next-stale-blocked-and-quest-deps]]

### Scope legibility

Selective Syncthing makes multi-log mandatory — folder boundaries in this vault are access-control lists, not a preference. The v3 changes make scope explicit rather than implied:

- `--all` → **`--all-logs` / `-A`**. `--global` was rejected: it overstates (logs outside the roots are still excluded) and `git config --global` means "the user-level file", importing the wrong intuition.
- **Repeatable `--root`**, de-duplicating resolved log paths — nested roots would otherwise emit the same quest twice, and duplicate ids in a JSON export are a silent data bug. `QST_ROOT` accepts `os.pathsep`-separated paths (not `:` — the Makefile targets Windows).
- **Repeatable `--in`**, accepting names or paths, allowed on mutation commands too where it remains a bounded search set with no silent sweep past it.
- **One `resolve_log_set()`** with three sources replaces two divergent code paths. A simplification, not an addition.
- **Per-log grouping** whenever more than one log is in scope — sort order plus a table-only separator header. **JSON and CSV stay flat arrays**; nesting would break every `jq '.[].title'` consumer, including the Home Assistant sensor.
- **One column set for the whole result**, with the header repeated under each group separator. A `--select` field missing from some logs renders as an empty column (informative) rather than being dropped (hides it) or made ragged per group (unscannable); missing from *every* log in scope stays a hard error. CSV and JSON have to be uniform regardless, and a table disagreeing with them would be worse.
- **A summary block on stderr**, silenced by `--quiet`. Rows to stdout so pipes and `--out` stay clean. It names the view, the filters (including the *injected default status filter* and its override idiom), the sort, the paging, and one `logs` row per root.

Grouping replaced an earlier proposal to force a single global ranking. Concatenating per-log results means each log evaluates its own view definition, which is strictly more correct — and it makes `quest next -A` a legitimate standup view rather than an error.

**Two-layer limits:** a view's own `limit` is part of its per-log definition and applies per log; a command-line `--limit` truncates the final concatenated result.

→ [[QST-iqwjm--multi-log-query-ux-all-logs-repeatable-in-and-root-per-log-grouping-summary-block]], [[QST-fmk0p--resolving-questkit-log-in-specified-path-via]], [[QST-3ehhu--quest-logs-inventory-every-quest-log-under-a-root]], [[QST-8hjjk--allow-for-select-and-distinct-when-listing-quests]]

## 6. Cross-log references

`blocked_by` and wikilinks resolve within one log, deliberately. But real dependencies cross logs, and `quest deps --blocks` is near-useless without them.

**Decision: the reference declares its own scope.** `blocked_by: [questkit/QST-3ehhu]`. A bare id means "this log", forever.

| Reference | Log present in sweep | Log absent (unsynced device) |
|-----------|----------------------|------------------------------|
| `QST-abc12` (bare) | must resolve here, else **error** | identical — **error**. Device-independent. |
| `questkit/QST-abc12` | resolve there; missing → **error** | **note**, never an error |

| Alternative | Verdict | Reason |
|-------------|---------|--------|
| Qualified refs | ✅ Chosen | Converts a derived fact (local or foreign?) into a declared one, which is what restores device-independence |
| Single-log only, forever | ❌ | `--blocks` misleadingly empty; real cross-log deps get written as prose nothing resolves |
| `deps` sweeps, `validate` unchanged | ❌ | `deps` draws an edge `validate` calls an error, in the same repo |
| `deps` sweeps + a third "resolves elsewhere" verdict | ❌ | Makes validation **device-dependent** — the same file would pass on the workstation and hard-fail on the phone, where `work-a`/`work-b` are not synced. A false failure per device is worse than no cross-log support. |
| Generated `id → log` index | ❌ | `.stignore-realm` documents why generated artifacts must not sync (every device writes different bytes). And it has nowhere to live — see §2. |
| Split the field (`blocked_by` local, `depends_on` foreign) | ❌ | Two fields for one concept; still needs a qualifier to resolve |
| Drop reference validation | ❌ | Throws away a check that catches real typos in the common case |

Syntax is `project/QST-xxxxx`, matching `--in questkit`; it is a plain YAML scalar and cannot collide with a bare id. Bodies stay plain text — Obsidian cannot resolve wikilinks across vault boundaries at all. Ships with no migration: 21 edges, all intra-log.

→ [[QST-yiep7--qualified-cross-log-references-in-blocked-by]]

## 7. Git, Syncthing, and the designated committer

### What pathspec does and does not buy

Pathspec limiting **prevents staging unrelated files** — code changes stay out of a `quest(...)` commit even when already staged, because `git commit -- <paths>` ignores the index. That is a correctness guarantee.

It does **not** prevent `.git/index` churn (§2). So the Syncthing mitigation has to come from somewhere else: **one git writer per repo.**

### The `git: auto` trap

`git: auto` means "the CLI commits from whatever device it runs on". So `quest new --in family` on a workstation *and* a realm-01 timer are **two writers on the same repo** — precisely the silently-resolving index race documented in `.stignore-common` and confirmed in production on 2026-08-14. Deriving the timer's scope from `git: auto` guarantees the overlap rather than partitioning it.

**Decision:** flip the quest-only logs (`family`, `realm-common`, `grocy-ecosystem`) to `git: manual` and give the timer an **explicit multi-`--in` scope**. Workstations write quest *files*; Syncthing carries them; realm-01 commits them.

The four `git: manual` code repos are where the 46 conflicts actually live. **Decided 2026-08-20: they stay in Syncthing, `.git/` included** — the multi-device working experience is worth more than the conflict litter, and the 2026-08-16 revert of the `index`/`logs` exclusion was the right call for the same reason (excluding only those while syncing the worktree leaves the index describing a tree that is not there, so `git status` lies). This is a Realm decision, recorded here because it bounds what `quest commit` can promise: pathspec limiting prevents *staging unrelated files*, and nothing questkit does prevents index churn.

### `quest commit`

The commit convention belongs in the app, not duplicated across a systemd unit, a Home Assistant `shell_command`, and fingers. `gitutil.auto_commit` is already most of it.

- Stages and commits exactly the log's **`tracked:`** set — default `[<pattern>, .questkit.yaml, .gitignore, _template.md, quests.base]`. `_validation.md` is deliberately excluded: it is derived state whose transport is Syncthing, not git.
- **Deterministic message from the frontmatter diff.** No model — everything needed is structurally available, and reaching for a summarizer would make a git command non-deterministic.
- **`--no-verify` forwarded**, off by default: normal CLI use keeps hook enforcement; the timer opts out explicitly so a data-quality problem cannot become a silent history gap at 03:00. When hooks block a commit and `--no-verify` was *not* passed, `quest commit` exits non-zero and prints the hook output — `auto_commit` currently swallows this.
- **`--push` opt-in, off by default.**
- `git: auto` is reimplemented on top of it — one commit path instead of two.

### The timer

```bash
LOGS="--in family --in realm-common --in grocy-ecosystem"
find <log dirs> -name 'QST-*.md' -mmin -10 | grep -q . && exit 0   # whole-log quiescence
quest format $LOGS
quest validate $LOGS --report quests/_validation.md || true
quest commit $LOGS --no-verify
```

Quiescence is **whole-log, not per-file**: reformatting file A while someone edits file B is safe for A, but the commit would capture B mid-thought. Polling *is* debouncing — which is also why a file watcher is the wrong tool.

| Trigger | Verdict | Reason |
|---------|---------|--------|
| systemd timer | ✅ Now | Polling gives debouncing for free |
| Pensieve `TimedSummons` | ⏸ Later | The right primitive (interval triggers, coalescing overlap, supervised loop) — but binding to it blocks this behind Pensieve's deployment |
| Pensieve watcher | ❌ | `strands/watcher.py`'s `is_strand_ready` is a **filename** check (`.tmp`, `~$`), not a settle check, and the dedupe window is 50 ms. Obsidian writes straight to the real filename on every autosave. |
| Pensieve Transfiguration | ❌ | An ingress transform that re-injects into a queue; `PLAN.md:25` forbids writing back into the watched folder. `quest format` is in-place normalization. |
| obsidian-git on phones | ❌ | Another writer into `.git` directories that already lose races |

`quest validate --report FILE` writes findings as a Markdown note and deletes it when clean, leaving exit codes alone. The timer chooses leniency with `|| true`; questkit does not grow a `--no-fail` flag someone will later paste into a hook.

→ [[QST-e6g6t--quest-commit-and-the-realm-01-designated-committer]], [[QST-ombky--quest-validate-reports-informational-slug-drift-as-a-hard-error]]

## 8. Agent handoff

`agentic: afk` is validated but nothing consumes it — readiness enforced for a handoff with no receiver, used by 1 file in 129. A validated-but-unused axis is worse than no axis.

`quest brief <id>` gives it a receiver: a short, self-contained, **agent-agnostic** Markdown work order on stdout. Plain Markdown, no vendor keys, no JSON envelope, no tool definitions, no system-prompt framing — it describes **the work**, never **the worker**.

Six things a brief has that `cat` does not: resolved dependencies; location (repo root, branch, dirty state, log path, git mode); the schema inline **only when the log overrides the default vocabulary**; a write-back contract; reverse dependencies as a priority signal; and a stable format that scripts can target.

**`READY` is entirely schema-driven** — `brief` evaluates the log's `readiness:`
list and prints each rule's own message, hardcoding nothing. That is what lets a
`household` quest need only a description while `development` needs a spec, with
`brief` knowing neither domain exists. `STATE` stays computed and
non-configurable: READY is about what a human wrote, so a schema owns it; STATE
is about where the quest sits in the graph, so the tool owns it.

Readiness is a **verdict, not a gate** — an ungroomed quest's brief collapses to header, location and warnings, so short-by-default emerges exactly where a full brief would be meaningless.

The inbound half is `quest new --body -` and `--batch -`: today an agent that turns a spec into eight tickets must shell out eight times and cannot write a body at all. Together these make questkit own **both edges** of the tickets step in a grill → spec → tickets → implement → review flow.

Deliberately **not** built: a claim/lock/report-back protocol. `quest handoff` was rejected as a name for exactly that reason — naming a command after a mechanism that does not exist invites the missing half. `quest ready` is deferred until `brief` has been used by hand enough to know what the predicate should be.

→ [[QST-xk7js--quest-brief-a-self-contained-work-order-and-the-batch-capture-that-feeds-it]]

## 9. Capture surfaces

`02-projects/family/quests` is initialized, syncs to family devices, and contains **0 quests**. That is a missing surface, not youth: family members can already *read* (Bases) and *edit* (Properties panel); what does not exist is a way to **create** a valid quest without the CLI.

1. **Generated `_template.md`** — `quest init --template` writes it from the log's merged schema. `.md` (not `.tmpl`) because it must be editable in Obsidian on a phone, and because it renders as what it produces. `_` prefix so both `pattern` and the Bases `startsWith("QST-")` filter skip it. **Generating it is what makes an Obsidian template safe** — a hand-written one duplicates schema logic where `quest validate` cannot protect it, and drifts; a generated one is a build artifact like `quests.base`.
2. **Distribution via `topology.yaml`**, the route `quests.base` already uses. One hardcoded row per vault with an `.obsidian` directory: the Realm root and pensieve — not `common/beans`, the dead system questkit replaced. `.templates/` does not exist at the Realm root yet, so the row creates it.
3. **Bases triage view** — `status == "draft" and description == null`. Note the existing view named "Kanban" is a *table grouped by status*; Bases has no board type here.
4. **Home Assistant** — a `todo` list → automation → `shell_command` on realm-01 → `quest new --in family`. The family already uses HA to-do lists for groceries, so the interaction is learned, and it needs no new app. It is also the **cleanest write path in the system**: HA writes through the CLI on the committer machine, so those quests arrive normalized and correctly stamped.
5. **`_validation.md`** is the only error channel a phone user will ever read.

`quest ingest` (plain bullets promoted into quests) is held — add it only after watching the template go unused.

→ [[QST-5rjla--obsidian-capture-surface-generated-template-md-topology-rows-bases-triage-view]]

## 10. Log topology

Routing rule, first test that fires wins:

1. **Different device set?** → separate Syncthing folder → separate log. *The only test that forces separation.*
2. **Must travel inside a git repo for traceability?** → log inside that repo.
3. **Neither?** → an existing log, sliced by a field.

| Log | Verdict | Test |
|-----|---------|------|
| `home`, `work-a`, `work-c`, `work-b` | create | 1 — already separate sync folders with distinct device sets |
| `pensieve`, `questkit`, `realm-system` | keep | 2 |
| `grocy-ecosystem` | keep as one log, add `component` | 3 — 35 of 66 titles already carry a hand-typed prefix |
| `family` | keep | 1 |
| `realm-common` | keep, **re-charter as the inbox** | "shared in some way" routes nothing; an inbox has a real charter and something to be stale about |
| `career-transition` | keep — archive it when it ends | see below |

### Archival

A time-boxed project's log needs to stop talking without any file moving.

**Archival is orthogonal to status, because scrapping and archiving answer
different questions.** `status: scrapped` says what happened to the *work*
(declined, cancelled). `archived: true` says whether it should still be *in front
of you*, and applies to a quest at any status — `done` included. A finished quest
in a wound-up project is archived and emphatically not scrapped.

The corpus makes the cost of conflating them concrete: career-transition holds
**4 finished quests among its 13**, so `status: archived` would erase which ones
shipped.

So `archived` is a **core boolean field**. Stored rather than derived from log
config, because a stored field is visible in Obsidian's Properties panel,
filterable in Bases, and greppable — a config key is invisible to every non-CLI
surface, including the family's.

```bash
quest archive QST-9x2kf [--in career-transition]     # one quest
quest unarchive QST-9x2kf
quest archive-log career-transition                  # every non-archived quest in it
```

**`archive-log` writes no log state** — it is purely a bulk `quest archive` over
the log's quests. So log archived-ness is **derived** ("13/13 archived") rather
than stored, which means: one source of truth that cannot drift; no special rule
for `quest new` in an archived log (the new quest is unarchived, so the log is no
longer fully archived — correct, the project came back to life); and `quest logs`
reports a ratio instead of a boolean. The separate, deliberately clunky command
name is the safety feature: a flag typo cannot archive an entire log when the
whole-log operation is a different verb.

Query surface is one tri-state flag, **`--archived {exclude,include,only}`**,
defaulting to `exclude`. `--include-archived` plus a separate `--archived-only`
would be two flags for one axis.

**Archival affects listing, never id resolution.** `show`/`brief`/`deps` and
`blocked_by` references still resolve into archived quests — otherwise every
cross-log reference into a finished project would start failing validation the
day it was archived. `blocks` does not count them, per §5. Neither `status` nor
`status_changed` changes; `modified` does, which is exactly why the two date
fields were split (§4) — archiving 13 quests leaves `idle` untouched, so `stale`
is unaffected by the archival itself.

Moving files into `quests/archive/` remains forbidden outright by v1 — it breaks
the Obsidian link graph this system exists to build.

`project:` is **identity**, unique per log, enforced by `quest logs` and `quest validate`. The alternative (free label + disambiguation prompt) would build an interactive path into a tool that pipes into agents.

## 11. Out of scope

- **Recurrence** — the most sophisticated part of the Trello setup questkit replaced; it deserves its own design round.
- **Bulk multi-log writes** — every command still mutates one file per invocation.
- **A claim / lock / handoff protocol.**
- **`completed_at`.**
- **WIP limits and auto-scrapping** — policy, and policy needs usage evidence that does not exist.
- **`quest ready`** — deferred.
- **A membership / parent-child concept.** `milestone:` is a planning bucket, not a link; an epic's Scope table stays prose.
- **Renaming `completed` to `done`.**
- **Nesting commands into noun-verb groups.** v3 groups `--help` output only; every command stays reachable as `quest <verb>`.
- **A `quest migrate --move-field` verb.** Moving a field between schemas changes no quest file; the check is `quest validate` under `strict: true`.
- **A readiness rule that can block a commit.** `quest validate` enforces the file contract; `readiness:` is advisory (§13).
- **A second config key splitting CLI-auto-commit from daemon-commit** — the explicit timer scope removes the need.

## 12. Build order

| # | Quest | Why here |
|---|-------|----------|
| 1 | [[QST-mjuau--quest-save-writes-only-when-the-rendered-content-changes]] | live bug in two call sites; blocks the committer |
| 2 | [[QST-3h09k--status-changed-frontmatter-field-and-reusable-backfill]] | must precede `--fill-defaults` or the signal is lost permanently |
| 3 | [[QST-j68u5--schema-engine-field-order-defaults-macros-typed-fields-strict-writes]] | one shippable unit |
| 4 | [[QST-fmk0p--resolving-questkit-log-in-specified-path-via]] | the resolver three other quests need |
| 5 | [[QST-3ehhu--quest-logs-inventory-every-quest-log-under-a-root]] | enforces `project:` uniqueness |
| 6 | [[QST-iqwjm--multi-log-query-ux-all-logs-repeatable-in-and-root-per-log-grouping-summary-block]] | |
| 7 | [[QST-yiep7--qualified-cross-log-references-in-blocked-by]] | rides on #4's resolver |
| 8 | [[QST-b9lqo--computed-fields-and-comparison-operators-for-where]] | needs `status_changed` |
| 9 | [[QST-8hjjk--allow-for-select-and-distinct-when-listing-quests]] | |
| 10 | [[QST-xk7js--quest-brief-a-self-contained-work-order-and-the-batch-capture-that-feeds-it]] | needs `blocks` |
| 11 | [[QST-37n0t--built-in-views-next-stale-blocked-and-quest-deps]] | needs computed fields |
| 12 | [[QST-e6g6t--quest-commit-and-the-realm-01-designated-committer]] | |
| 13 | [[QST-5rjla--obsidian-capture-surface-generated-template-md-topology-rows-bases-triage-view]] | needs the schema engine |
| 14 | [[QST-lcsza--archive-a-whole-quest-log-instead-of-individual-quests]] | needs `quest logs` |
| 15 | [[QST-lc3co--quest-migrate-frontmatter-aware-corpus-migrations]] | runs the corpus migrations |
| 16 | [[QST-zl5xc--group-root-commands-in-help-output-as-the-cli-passes-20-verbs]] | 10 commands become 22 |

Independent: [[QST-ombky--quest-validate-reports-informational-slug-drift-as-a-hard-error]], [[QST-lc3d7--check-for-duplicates-when-adding-with-same-title]], [[QST-onxad--new-frontmatter-attributes]].

## 13. Open questions

None outstanding. Four were carried and are now resolved:

- **Terminal statuses under a custom schema** → an ordered `terminal_statuses` key defaulting to `[done, scrapped]`, which is the tail of the default `statuses` list (§4).
- **The archive story** → log-level `archived: true`, affecting listing but never id resolution (§10), tracked as [[QST-lcsza--archive-a-whole-quest-log-instead-of-individual-quests]].
- **Whether the code repos belong in Syncthing** → decided 2026-08-20 that they stay, `.git/` included (§7).
- **Readiness vs. validation** → `quest validate` stops enforcing readiness entirely. The old AFK rule was a category error: it turned a *grooming judgment* into a *commit-blocking contract*. `validate` answers "is this file well-formed and are its references real"; `readiness` answers "is this good enough to hand to someone". Never both — and a config-defined rule that could block commits would be considerably more dangerous than a hardcoded one.

### Migration

Two corpus-wide migrations are queued across 129 files in 7 logs: the `status_changed` backfill and `completed` → `done`. (**The `agentic` demotion needs no file migration** — the 16 files already carry the field; only `schema.py` and `development.yaml` change, and `quest validate` under `strict: true` is the check that they line up.) They ship as one tool ([[QST-lc3co--quest-migrate-frontmatter-aware-corpus-migrations]]) rather than documented `sed`, because **`sed` corrupts prose** — verified in this log:

```
QST-bmzl2:114  - [ ] Every quest in the Scope table is completed or explicitly scrapped
QST-whm2e:65   ... Completed quests stay exactly where they were created, forever.
```

Only a frontmatter-aware tool can rename a *value of a field* without touching text that happens to use the same word. Roughly 90 lines plus tests — most of the machinery is inherited from quests already scheduled. `--commit` is opt-in and refuses on a dirty index; each log commits separately in its own repo, making this the first command that writes to multiple repositories in one invocation.

Ordering constraint: `development` must exist and questkit's own log must adopt it **before** `agentic` leaves core, or the 16 files carrying it break under `strict`.

## 14. Provenance

Revised again 2026-08-21: archival reversed to a core per-quest `archived:` field
after the scrapped-vs-archived distinction was drawn correctly (retention is not
the same decision as the work's fate, and a stored field is the only form the
family's surfaces can see); `dropped` weighed against `scrapped` from scratch and
rejected; `quest migrate` cut from three verbs to two; command-group help
captured as the CLI passes 20 verbs. Revised 2026-08-20: `agentic` demoted out of core with configurable
`readiness:` replacing both its hardcoded guard rules, `completed` renamed to
`done`, vocabularies made ordered after finding `--sort priority` returns
`critical, deferred, ...` and multi-key sort silently drops keys, archival
confirmed log-level after the 4-finished-quests check, and corpus migration split
into its own tool. Revised 2026-08-20 after a review pass over the quest set: the `status`/computed-field
collision, terminal statuses, archival, `agentic`'s home, `milestone:`, and the
grouped-output column rules. Originally written 2026-08-19 from a design grilling session covering positioning, multi-log friction, schema defaults and macros, the agent handoff format, the Obsidian/mobile capture surface, and the git/Syncthing boundary. Corpus figures in §2 and the `.git/index` measurement in §7 were taken during that session.
