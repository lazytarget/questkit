---
id: QST-whm2e
title: Questkit — Design Blueprint for File-Based Quest Tracking
description: Design blueprint for questkit, a standalone Markdown+frontmatter quest tracker replacing Beans and Trello across The Realm. (v1)
created: 2026-08-13
status_changed: 2026-08-14
modified: 2026-08-20
type: epic
tier: blueprint
status: completed
priority: high
effort: xl
owner: peter
agentic: hitl
project: questkit
tags:
  - questkit
  - quests
  - framework
  - tooling
  - beans-migration
blocked_by: []
aliases:
  - QST-whm2e
---

## Description

**Questkit** is a standalone, open-source Python framework and CLI for tracking work as **quests** — one Markdown file with YAML frontmatter per item, stored in plain `quests/` directories ("quest logs") scattered across The Realm's Git/Syncthing zones, plus one central log for anything zone-less. It replaces three parallel, drifting systems: the `beans` framework (frontmatter incompatible with the Realm standard), Trello (four boards, mostly running on automation autopilot with declining human engagement), and a scatter of ad-hoc markdown todo lists (`TODOS.md`, `career-todos.md`, `career-next-actions-2026.md`, …).

This document is the founding blueprint: the single source of truth for questkit's design until the repo exists and a plan/ADR trail takes over. It is quest `QST-whm2e` itself — originally the first file in the central log it describes (`02-projects/common/quests/`), relocated on 2026-08-14 to questkit's own `quests/` (`project: questkit`), since a design blueprint for questkit belongs in questkit's own log rather than the project-less central one.

## Problem Statement

- **Vocabulary collision.** Generic nouns (task, todo, issue) carry default behavior in agent tooling (Claude Code's own `TaskCreate`, `gh issue create`, etc.), so "create a task" is ambiguous instruction. "Bean" avoided this but welded the noun to one specific upstream framework (`hmans/beans`) whose frontmatter (`created_at`/`updated_at`, id-as-comment, non-standard `status` values) already fails the Realm's own `frontmatter.py validate`.
- **Capture friction kills ideas.** The user's mind spins off rabbit-holes quickly and forgets them just as fast. Any filing decision required at capture time (which project? which board?) is friction that a fleeting idea won't survive.
- **Fragmentation.** Real work is currently split across `.beans/` (26 groomed tickets), `.beans-wip/` (14 ungroomed), four live Trello boards (730 open cards) running mostly on Butler/Home-Assistant automation with 72% of archived cards bot-generated and human engagement declining since ~2024–2025, and multiple independent markdown todo files with legacy frontmatter.
- **Selective sync is a real constraint, not a preference.** Syncthing folder boundaries in this vault are access-control lists (work zones never reach family devices and vice versa) — any tracker topology has to respect that, not fight it.

## Decisions

### Identity & naming

| | |
|---|---|
| Repo / PyPI package | `questkit` |
| Path | `02-projects/lazytarget/questkit` |
| CLI binary | `quest` (alias `qst`) |
| Item noun | **quest** (fixed — "side quest" / "epic quest" flavor is load-bearing, not decorative) |
| Directory | `quests/` (visible, not dotted — Obsidian/ripgrep both skip hidden dirs by default) |
| Marker/config file | `.questkit.yaml`, lives **inside** `quests/` |
| Filename | `QST-<5-char lowercase base36>--<kebab-slug>.md`, e.g. `QST-x7k2m--fix-garage-door.md` |

Why `quest`: distinctive, collision-free with agent tooling defaults, and matches The Realm's existing fantasy register (a realm has a quest log). Considered and rejected: task/todo/issue (tool-default collisions), story/PBI/PRD (scrum jargon, absurd for gift shopping), card (bound to Trello's model). Repo-name alternatives considered and rejected for prior mindshare or product collisions: `quests` (PyPI-taken by an active scientific package), `questlog`/`sidequest` (crowded gaming-app namespace), `questforge`/`questline`/`questbook`/`questmark` (each collides with a live company or product). `questkit` reads as "a toolkit for tracking work," which is accurate, and had only a single dormant 2015 repo as prior art.

Filename ID is random (base36, 5 chars), not sequential — forced by the topology: a sequential counter has no safe home in a multi-device, offline-capable, Syncthing-replicated system (two devices minting the same next ID while offline is a guaranteed collision). `quest new` collision-checks by globbing at creation time as a cheap same-device guard.

### Topology & discovery

- **No per-project folders forcing a filing decision at capture.** `quest new` is zone-aware: it walks up from `$PWD` to find a `quests/.questkit.yaml` marker and lands the file there. No marker found → falls through to the central log via `QUEST_LOG`. This is "nearest zone wins" — capture never requires deciding where something belongs.
- **A directory is a quest log iff it contains `quests/.questkit.yaml`.** Presence of the marker is the *only* opt-in signal — never an implicit bare `quests/` dir. This protects public `lazytarget/` repos (a `quests/` dir with no marker is just a folder) and gives `.questkit.yaml`'s own `version:` key a place to force a loud failure on breaking config changes, rather than silently misreading old config.
- **Resolution order for every command:** `--in DIR` (explicit override) → walk-up from cwd checking each ancestor for `quests/.questkit.yaml` → `QUEST_LOG` env var (points at the central log) → actionable error ("no quest log found: run `quest init` here, or set QUEST_LOG"). `QUEST_LOG` is deliberately *last*, not first — resolving it before walk-up would break nearest-zone-wins on every machine where the var is set, i.e. all of them.
- **Central log** = `02-projects/common/quests/` — a **fresh** Git repo (the old `beans` repo is frozen, not restructured in place; it carries `.beans-wip/`, drifted Obsidian plugin baggage, and a stale branch state not worth inheriting). The repo root *is* the log: `QST-*.md` files sit directly at the top, `.questkit.yaml` beside them. This is the directory this very file lives in.
- **Per-zone logs** opt in explicitly via `quest init [DIR]`, one time, per repo.
- **No `active/`/`archive/` subdirectories, ever.** Completed quests stay exactly where they were created, forever. `status: completed` is a query filter, not a filesystem move. At realistic volume (~1,000 items across 6 years of prior Trello use) a flat directory of markdown files doesn't strain anything, and a move-on-completion policy would be the one design most likely to break the Obsidian link graph this whole system exists to build.
- **Discovery glob:** `**/quests/QST-*.md` from the Realm root, restricted to that prefix so it can never match `README.md` or other prose files that happen to live in a directory named `quests` (including, ironically, the framework repo's own docs).

### Frontmatter schema

```yaml
---
id: QST-x7k2m
title: Human-readable title
description: One-line purpose (<200 chars) — exempt when status is draft
created: 2026-08-13
modified: 2026-08-13          # bumped by the pre-commit hook and by `quest set`
type: task                    # feature | task | bug | epic | milestone | chore
tier: spark                   # spark | brief | blueprint — optional, spec-workflow weight
status: draft                 # draft | todo | in-progress | blocked | parked | completed | scrapped
priority: medium              # critical | high | medium | low | deferred
effort: m                     # xs | s | m | l | xl — optional
owner: peter                  # peter | jenika — optional, human accountability
agentic: hitl                 # afk | hitl — optional; absent = not yet triaged for handoff
project: pensieve             # optional; CLI-stamped at creation, `quest validate` warns on path drift
due: 2026-09-01                # optional — YYYY-MM-DD
tags: []
blocked_by: []                 # QST ids this is blocked by — one direction only, reverse is computed
aliases: [QST-x7k2m]           # surfaces the short id in Obsidian search/quick-switcher/autocomplete; does NOT make a bare `[[QST-x7k2m]]` link resolve on click -- see Log, 2026-08-13
---

## Description

## Acceptance Criteria

- [ ] ...

## Log

- 2026-08-13: captured
```

Notable choices and why:
- **`tier` sits directly after `type`**, kept as `spark`/`brief`/`blueprint` unchanged from the Beans workflow (see `99-system/workflow/README.md`) — the terms describe the spec artifact's weight, not the quest's theme, so no renaming benefit existed.
- **`blocked_by` only, no `blocks`.** Two-directional dependency storage drifts (one side gets updated, the other doesn't); the reverse edge is always computable from the full set of quests and is exactly what Obsidian backlinks already do for free.
- **`owner` and `agentic` are two different axes**, deliberately not conflated into `assignee: agent`. `owner` is human accountability (whose quest is this); `agentic` is execution mode (can/should an agent run this AFK, or does it need a human in the loop). Inspired by Matt Pocock's `skills`/`sandcastle` vocabulary, which draws the same split: every ticket there is either **HITL** ("worked *with* a human who speaks for themselves") or **AFK** ("driven by the agent alone"), and `ready-for-agent` is a *triage outcome* requiring an attached spec, not a property assigned at capture. Questkit mirrors that: `quest validate` flags any quest with `agentic: afk` but no Acceptance Criteria and no `## Spec`/design substance — AFK-readiness is earned at grooming time, not declared at creation.
- **`project` survives**, against the initial instinct to derive it purely from path. Central-log quests have no path to derive it from, and a stored field beats tags-only discipline for query power — the tradeoff (staleness) is closed by `quest validate` warning when a zone-local quest's `project` disagrees with the zone it's actually filed under.
- **`description` is exempt when `status: draft`** — otherwise the Realm's own required-field rule would force a sentence out of the user at the exact moment (mid rabbit-hole) speed matters most. `quest new "title"` must stay a two-second action.
- **No `pinned` field.** Its only job in Trello was preventing auto-archival — moot once nothing auto-archives.
- **No `recurrence`/`last_done`.** See Out of Scope.

### CLI surface (v1)

```
quest new "title" [--type X] [--priority X] [--in DIR] [--edit]
quest list [--status a,b] [--type X] [--tag X] [--in DIR]   # default: todo,in-progress,blocked
quest show QST-x7k2m
quest set QST-x7k2m status=in-progress [field=value ...]     # bumps modified
quest done QST-x7k2m                                          # sugar for set status=completed
quest init [DIR] [--base] [--hooks]
quest validate [DIR]
```

- `quest init` is **idempotent**: never overwrites, only fills gaps. Bare `quest init` creates `quests/` + `.questkit.yaml` only if absent. `--base` scaffolds an Obsidian Bases kanban view (`quests.base`) but skips with a message if one already exists — a markdown-ticket framework shouldn't assume Obsidian, so this stays opt-in. `--hooks` structurally parses (not marker-comment-hacks) the zone's `.pre-commit-config.yaml`, appends a `repo:` entry for questkit's own hooks if not already present, and runs `pre-commit install`; it's a no-op with a message if the target isn't a git repo.
- The CLI is **pure file I/O** — it never calls `git commit` itself by default. Auto-commit is convenient exactly once (the central log, whose only content is quest files, so every mutation is self-contained) and actively dangerous elsewhere (splits atomic code+ticket commits, surfaces git's failure modes — mid-merge, mid-rebase — as CLI errors, and assumes every log is a git repo when some are Syncthing-only). Resolved as a **per-log config key**, not a global switch: `.questkit.yaml` carries `git: auto | manual` (default `manual`), overridable per invocation with `--commit`/`--no-commit`. Auto mode is pathspec-limited to the touched file, skips with a warning rather than failing when git state blocks committing, and never pushes.
- Commit prefix convention for manual-mode zones (mirrors the existing Beans convention): `quest(<zone>): <summary>`.
- Framework ships its own `.pre-commit-hooks.yaml`: `quest-validate` (frontmatter/schema check) and `quest-bump-modified` (bumps `modified:` on commit). `realm-hooks` and `onboard-zone` should shell out to `quest init --hooks` rather than reimplementing this logic — single-sourced in questkit.

### Obsidian integration

Obsidian **Bases** (core plugin) is already enabled in every vault/profile on this device with no community plugins needed (confirmed by inventory — `dataview`, `obsidian-projects`, `obsidian-kanban` are all absent and unnecessary). The central repo ships `all-quests.base` (kanban grouped by `status`, table views filtered by `project`/`priority`/`owner`) as repo content, so it syncs everywhere the central log syncs. It shows the full cross-zone picture only from the realm-root vault — the one vault positioned above every zone — which is per-device provisioned (`make pull-obsidian-realm`) rather than itself Syncthing-replicated. On narrower vaults the same file gracefully shows only the quests that zone can see, which is the selective-sync ACL doing its job in the UI rather than a limitation.

## Out of Scope

- **Recurrence and `last_done` tracking.** Trello's checklist-embedded scheduling DSL (`[month:26@09:30]`, business-day arithmetic like `[work_month:19+2@16:00]`) is the most sophisticated part of the current system and deserves its own design round, not a bolt-on. Butler/Home-Assistant keep generating recurring cards in the meantime.
- **Non-ticket collections** — Matschema (recipes + times-cooked), Städschema (chores + last-completion), People (CRM + last-meet + cadence), Film & TV (watchlist), and Trello's card-as-standalone-list pattern (packing lists, pantry inventories, reading queues). These share a `last_done` + interval or plain-list shape that doesn't belong on a ticket schema. Possible future sibling document types in the same framework; not quests.
- **Trello as a live migration target.** Deprioritized to "if the need arises" (2026-08-13) — the four boards' automation can keep running; nothing here blocks on importing them. If revisited, note the finding that at least one work card stores plaintext credentials in its description — any import needs a secrets scan first.

## Migration Plan (scope, not yet executed)

1. **26 legacy beans** (`.beans/`, all groomed) + **14 WIP beans** (`.beans-wip/`, dissolve into `status: draft` on import) — frontmatter rewrite from hmans/beans format (`created_at`/`updated_at`, id-as-comment) to the questkit schema above.
2. **Stray markdown todo docs**: `99-system/TODOS.md`, `02-projects/peter/2026-career-transition/career-todos.md`, and its duplicate `career-next-actions-2026.md` — each a checkbox list with legacy frontmatter that exists because creating a proper ticket from that context had friction. One-quest-per-actionable-item, or per-section, to be decided at execution time.
3. **In-repo `TODO`/`FIXME` code comments** — a distinct migration mechanism (grep-and-triage across the Realm's code repos) rather than a frontmatter rewrite. Not yet designed; flagged here so it isn't lost.
4. **Trello** — deferred, see Out of Scope.

## Acceptance Criteria

- [x] `questkit` repo scaffolded at `02-projects/lazytarget/questkit`, installable, ships `quest`/`qst` entry points
- [x] `quest new/list/show/set/done/init/validate` implemented per the CLI surface above
- [x] `quest init --base` and `--hooks` implemented, both idempotent
- [x] Central log at `02-projects/common/quests/` initialized as its own git repo with `.questkit.yaml` (`git: auto`, `project: common`) and a Bases view (`quests.base` — see Log for the `all-quests.base` naming correction)
- [x] `99-system` make shims (`make quest "<title>"` → `quest new`, `make status` → `quest list`) wired
- [x] `make bean` becomes a deprecation stub pointing at `make quest`
- [x] 11 beans + 14 WIP beans migrated and passing `quest validate` (see Log for the 26→25 count correction)
- [x] `99-system/TODOS.md` and `career-todos.md` migrated; `career-next-actions-2026.md` reviewed and deliberately kept as-is (see Log)
- [x] AGENTS.md / CLAUDE.md updated so "bean", "ticket", "todo" route to quest creation as spoken synonyms

## Open Follow-ups

- In-code TODO/FIXME sweep mechanics (per-comment quest vs. batch triage) — needs its own design pass. Not started.
- Whether `quest validate`'s AFK-readiness check (Acceptance Criteria + `## Spec`/design substance present) needs to be configurable per-project, or is fine as a fixed rule. Not revisited.
- Trello import stays deferred (see Out of Scope) — untouched by this implementation pass.
- `owner` is currently free text with no enum, by design (questkit is generic OSS) — the Realm-specific `peter`/`jenika` convention is a usage pattern, not a schema constraint. Worth confirming that stays the right call once more than one person actually uses a shared log.

## Log

- 2026-08-12: Naming exploration begins; "bean" retired in favor of "quest" after reviewing Realm topology, existing Beans/frontmatter implementation, and Trello usage (4 active boards, automation-driven, recurrence-heavy).
- 2026-08-12: Topology, frontmatter schema, CLI surface, git behavior, Obsidian view strategy, and `owner`/`agentic` split settled across several grilling rounds; Pocock `skills`/`sandcastle` vocabulary adopted for the AFK/HITL axis.
- 2026-08-13: Repo/package name locked to `questkit` after two rounds of availability research; config file renamed `.questkit.yaml` to match; `git: auto|manual` folded into that config; `quest init --hooks` designed. Trello migration deprioritized. This blueprint written.
- 2026-08-13: Implementation pass. Corrections made against the plan above, in the order found:
  - **Bean count corrected 26→11.** `.beans/` holds 11 files (BEAN-0001..0010 + BEAN-yof1), not 26 — the original estimate was an unverified early guess. Combined with the 14 WIP beans, 25 files were migrated in total, all passing `quest validate`.
  - **WIP status preserved, not flattened to `draft`.** The plan said "dissolve `.beans-wip/` into `status: draft` on import," but reading the actual 14 files showed several were already accurately `completed` (e.g. `BEAN-wgth`, real finished grooming work) or `in-progress` (`BEAN-b5oe`, most acceptance criteria checked). Forcing those to `draft` would have misrepresented real historical status. Each WIP bean's own `status` field was carried over instead (with `done`→`completed` normalized, same as the groomed beans).
  - **`BEAN-0004`'s malformed `blocks` entry** (a full wikilink string stored as a list item instead of a plain id) was manually resolved and folded into `BEAN-zn08`'s `blocked_by` — the only case where `blocks`-folding actually added information beyond what `blocked_by` already recorded symmetrically.
  - **`all-quests.base` → `quests.base`.** The shipped `quest init --base` template uses a generic filename (works identically for zone and central logs) rather than a central-log-specific name; the central log's `.questkit.yaml` was set to `git: auto` and `project: common` as directed.
  - **ruamel line-wrapping bug found and fixed in questkit itself** (`quest.py`/`config.py`: `_yaml.width = 4096`) — long `description` values were wrapping across lines, hurting greppability. Fixed at the framework level, not patched per-file, then the 25 migrated files were regenerated.
  - **Makefile absorption bug found and fixed** — the inherited `$(eval $(ARGS):;@:)` pattern (used by both the new `quest`/`status` shims and the pre-existing root-level `bean` target) re-splits a reconstructed multi-word title on whitespace and defines a no-op per *word*, which never matches Make's real (space-preserved) second goal from argv, and silently breaks worse when a title happens to contain the word "quest"/"bean" itself. Replaced with the `.DEFAULT:` pattern (verified in isolation first) in both places. `QUEST_LOG` is Makefile-defaulted to the central log (`?=`, so a real env var still wins) so `make quest`/`make status` work from anywhere without shell-profile changes.
  - **`project: questkit` dropped from this file's own frontmatter** — redundant with the `questkit` tag already present, and created a real (correctly-firing) drift warning once the central log declared `project: common`. `project:` now consistently means "which zone/log this belongs to," not "which subject this is about."
  - **99-system and `peter/2026-career-transition` opted into questkit** (`project: realm-system`, `project: career-transition` respectively, both `git: manual`) to hold the `TODOS.md`/`career-todos.md` migration.
  - **`career-next-actions-2026.md` reviewed, not migrated.** Despite its name, it's a strategy/reference document (`scope: 03-knowledge/career`, prose sections cross-linked to other knowledge notes) with only two genuinely actionable items, both already covered by `career-todos.md`. Fragmenting it into quests would have destroyed its narrative structure for no gain — left in place untouched.
  - **`career-todos.md` migrated as 13 quests** (one per top-level bullet, nested sub-items preserved as each quest's own Acceptance Criteria checklist rather than split into separate quests), then deleted. Swedish content preserved verbatim (`language: sv` on each).
  - **`99-system/TODOS.md` migrated as 14 quests** (13 in the new `99-system` log, one routed to `pensieve` since it was Pensieve-specific), then deleted. The Android `make bean` bug item was marked `scrapped` (`superseded_by: QST-uq9io`) since its exact failure mode — a nested `make -C` delegation passing a bogus target name — can't recur now that `quest`/`status` call the CLI directly; a fresh quest tracks verifying the new targets on real Android/Termux hardware instead. The "create a custom skills repo" item was marked `completed` — `02-projects/lazytarget/skills` and the `skills.yaml`/`make *-skills` targets already exist.
- 2026-08-13: **Bare `` [[QST-xxxxx]] `` alias-links don't resolve on click** — confirmed as a real Obsidian gap (the wikilink resolver reads only `uniqueFileLookup`, which is built from filenames, not frontmatter `aliases`; clicking a bare alias link creates a blank note instead). `aliases:` is kept — it still drives search, quick-switcher, and typing-autocomplete. First fix attempt used the piped form `` [[QST-xxxxx--slug|QST-xxxxx]] ``, which resolves correctly but is *more* characters than just writing the full name, and hides the descriptive slug behind a cryptic id — worse for a human scanning backlinks, and no cheaper for an agent reading them. **Superseded same day**: the primary convention is now the plain full name, no pipe — `` [[QST-xxxxx--slug]] `` — every cross-reference across all logs (and this file's own examples) rewritten accordingly. Separately: wikilinks cannot cross Obsidian vault boundaries at all (confirmed — not a setting, not fixable by a plugin), so a quest in one zone linking to a quest in another zone/log can only ever resolve when the realm-root vault is open; every cross-reference created so far happens to be same-zone, so this hasn't bitten anything yet, but a future cross-zone reference should be plain text (`QST-xxxxx`, greppable and `quest show`-able) rather than a wikilink that silently won't resolve outside the root vault.
- 2026-08-13: **`quest validate` extended**: cross-checks filename id vs frontmatter `id`, filename slug vs a title-derived slug (informational — filenames stay immutable by design, so this reports drift rather than implying a rename is owed; running it against the full migrated corpus surfaced dozens of "disagreements," all expected — migration deliberately reused shorter/original/language-appropriate slugs instead of mechanically slugifying the title, e.g. Swedish titles with English filenames), and that `aliases` includes the quest's own id. Also resolves `blocked_by` ids and body wikilinks against the current log, flagging anything dangling — caught two false positives from this very file's own illustrative `` [[QST-x7k2m]] ``/`` [[QST-xxxxx]] `` placeholder examples, fixed by backtick-wrapping them (they're syntax examples, not real links).
- 2026-08-13: **`quest new` now sets `blocked_by: []`** — it never did before; backfilled onto every existing quest that lacked it.
- 2026-08-13: **List-valued fields normalize to flow style (`[a, b]`) at 0-1 items, block style (one per line) at 2+**, applied on every `Quest.save()` — self-heals on the next command or bump-modified-hook run rather than needing a separate lint-and-fix pass.
- 2026-08-13: **`slugify()` fixed to transliterate instead of drop non-ASCII letters** (NFKD-decompose + ASCII-encode-ignore) — `"på"` was slugifying to `"p"` (silently dropping "å"), now correctly `"pa"`. Existing Swedish-titled filenames in `career-transition/quests/` predate the fix and were not renamed (immutable by design); their title/slug "drift" per the check above is expected.
- 2026-08-13: **`make quest`/`make status`/`make bean` removed entirely** from
  `99-system/Makefile` and `pensieve/Makefile` — direct `quest`/`qst` CLI
  usage (already globally installed via `uv tool install --editable`, part
  of `make setup-venv`) replaces the Make wrappers everywhere, including in
  every doc that referenced them (root `AGENTS.md`/`CLAUDE.md` templates,
  `99-system/README.md`, `workflow/README.md`, `realm-metadata-standard.md`,
  pensieve's own `AGENTS.md`/`CLAUDE.md`/agent-instruction files, and
  questkit's own `docs/questkit.md`, whose now-empty "Make integration"
  section was removed rather than left as a stub). The dead `QUEST_LOG ?=`
  Makefile default and the `onboard-beans` target (which only ever existed
  to propagate `bean` Makefile stubs into project repos) were removed too.
  `QST-uq9io` (verify the Android Make shim) is now moot and was scrapped.
  Net effect: no functional change to `quest`/`qst` itself, only to how
  it's invoked — and one real, callable-out gap: `QUEST_LOG`'s
  fall-back-to-central-log behavior for a bare `quest`/`qst` invocation
  from a directory with no nearby log now depends entirely on the user's
  own shell profile exporting it (the Makefile default never actually
  reached an interactive shell anyway, only `make`-spawned subprocesses,
  so this isn't a regression from direct CLI use, just newly worth calling
  out now that it's the *only* path).
- 2026-08-14: Relocated from the central log (`02-projects/common/quests/`)
  to questkit's own log (`02-projects/lazytarget/questkit/quests/`),
  `project: questkit` set to match; filename slug expanded from
  `questkit-design-blueprint` to `questkit-design-blueprint-for-file-based-quest-tracking`
  to resolve the title/filename slug-drift `quest validate` was flagging.
  Cross-references to this file across the Realm updated to the new path.

## Related

- [[../../../common/beans/docs/beans.md]] — the framework being replaced; authoritative for legacy ticket-schema details during migration
- [[../../../../99-system/workflow/README.md]] — spark/brief/blueprint tier definitions, inherited unchanged
- [[../../../../03-knowledge/realm-metadata-standard.md]] — the frontmatter standard this schema extends
- [[../../realm-hooks/README.md]] — hub-and-spoke hook model questkit's own hooks follow
