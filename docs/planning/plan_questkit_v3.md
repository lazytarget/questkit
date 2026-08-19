---
title: questkit v3 — loop closure, multi-log UX, and agent handoff
description: "Design record for questkit v3: the decisions, the evidence behind them, and the alternatives rejected along the way."
created: 2026-08-19
modified: 2026-08-19
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

### Core vs. schema

`tier` and `effort` **stay core**. The test is not "is this field used everywhere" but "is this vocabulary universal": `xs|s|m|l|xl` and `spark|brief|blueprint` describe any unit of work including a household chore. `component` and `related_adrs` are meaningless outside software and belong in the `development` schema. Demoting a universal vocabulary to shrink the core would also lose validation on the 20 files already carrying `effort`.

`language` follows the same rule and is therefore **not** a core field — see [[QST-onxad--new-frontmatter-attributes]].

### Defaults, macros, typed fields, strict

Shipped as one unit because they are unshippable apart: the moment any log declares `required: true`, `quest validate` fails every quest that predates it and the pre-commit hook blocks every commit, unless `--fill-defaults` lands in the same release.

- **Defaults in one place** — `schema.fields.<n>.default` canonical, top-level `defaults:` as sugar. Precedence: `--flag` > `fields.<n>.default` > `defaults.<n>` > built-in.
- **Macros** — `{{ project }} {{ log }} {{ id }} {{ slug }} {{ title }} {{ today }} {{ owner }} {{ env.USER }}`, expanded after id generation and before first save. Plain substitution, no control flow. Jinja2 was rejected as a large dependency for string substitution into a Markdown skeleton, and because `{% if %}` turns a body template into something you debug; `{{ }}` is a strict subset, so adopting Jinja later costs nothing. `$PROJECT` was rejected because it reads as shell interpolation in YAML and the first thing anyone tries is `$HOME`.
- **`FieldSpec` gains `type: enum` + `values:`** — three separate features need it, and today `type` is validated against nothing.
- **`strict`, default `true`** — governs the **CLI write path only**; hand-edited frontmatter stays lenient forever because Obsidian must remain free to add fields. `strict: false` still warns on stderr: the failure mode is a field that appears in no filter, fails no validation, and is only ever found by grep months later. A lenient default was rejected because every existing log has no schema block, so the protection would be absent exactly where typos are most likely.
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

They behave like any other field for `--where`, `--select` and `--sort`, and are read-only.

**This is the right layer.** An earlier framing gave each view its own bespoke logic, justified by "things `--where` cannot express". Pushing the derivation down one level is better: one computation, many consumers. The same `blocked` value marks the default list, defines the `blocked` view, filters `next`, and gives `quest brief` a priority signal.

`--where` gains `>`, `<`, `>=`, `<=`, parsed before `=` so `>=` is not shredded. ISO dates compare correctly as strings, so no date parsing is needed.

→ [[QST-b9lqo--computed-fields-and-comparison-operators-for-where]]

### Views

Views are **pure prefills** defined in the schema file, overridable per log, exposed as bare subcommands:

```yaml
views:
  next:    { where: ["blocked=false"], sort: "priority:asc,effort:asc,idle:desc", limit: 1 }
  stale:   { where: ["idle>14"], sort: "idle:desc" }
  blocked: { where: ["blocked=true"], sort: "blocks:desc" }
```

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

The four `git: manual` code repos are where the 46 conflicts actually live. Nothing questkit does helps there — the fix is `#include .stignore-gitmeta` plus Gitea as the reconciliation point, or not Syncthing-ing them at all. That is a Realm decision, outside this plan. Worth noting *why* the 2026-08-16 revert felt bad: excluding only `index`/`logs` while syncing the worktree leaves the index describing a tree that is not there, so `git status` lies. Excluding all of `.git/` does not have that failure mode.

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
| `career-transition` | keep — but it is time-boxed with no exit | needs an archive story before there are three dead logs |

`project:` is **identity**, unique per log, enforced by `quest logs` and `quest validate`. The alternative (free label + disambiguation prompt) would build an interactive path into a tool that pipes into agents.

## 11. Out of scope

- **Recurrence** — the most sophisticated part of the Trello setup questkit replaced; it deserves its own design round.
- **Bulk multi-log writes** — every command still mutates one file per invocation.
- **A claim / lock / handoff protocol.**
- **`completed_at`.**
- **WIP limits and auto-scrapping** — policy, and policy needs usage evidence that does not exist.
- **`quest ready`** — deferred.
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

Independent: [[QST-ombky--quest-validate-reports-informational-slug-drift-as-a-hard-error]], [[QST-lc3d7--check-for-duplicates-when-adding-with-same-title]], [[QST-onxad--new-frontmatter-attributes]].

## 13. Open questions

- **Terminal statuses under a custom schema.** Needed by `quest logs`' `OPEN` column *and* by the `blocked`/`next` computations. Either `SchemaConfig` declares its terminal set or consumers degrade. Load-bearing in two places — decided in [[QST-j68u5--schema-engine-field-order-defaults-macros-typed-fields-strict-writes]], not separately.
- **An archive story.** `career-transition` is time-boxed; when it ends its 13 quests stay in `-A` forever. Archiving as a *mutation* (move to cold storage, drop out of sweeps) is a real feature, and the `archive` command name is reserved for it.
- **Whether the code repos belong in Syncthing folders at all.** Realm-side, not questkit's, but it is the root cause of the 46 conflict files.

## 14. Provenance

Written 2026-08-19 from a design grilling session covering positioning, multi-log friction, schema defaults and macros, the agent handoff format, the Obsidian/mobile capture surface, and the git/Syncthing boundary. Corpus figures in §2 and the `.git/index` measurement in §7 were taken during that session.
