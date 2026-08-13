# questkit — Detailed Reference

This is the deep-dive companion to the top-level [README.md](../README.md).
The README is the pitch and the quickstart; this document is the reference
— implementation detail, rationale, and the full surface area, for anyone
extending questkit, running it across many machines, or just wanting to
know exactly what a given command or field does and why it exists.

## Table of contents

1. [Purpose & design philosophy](#1-purpose--design-philosophy)
2. [Role inside The Realm](#2-role-inside-the-realm)
3. [Core concepts](#3-core-concepts)
4. [Installation](#4-installation)
5. [Development](#5-development)
6. [CLI reference](#6-cli-reference)
7. [Make integration](#7-make-integration)
8. [Frontmatter reference](#8-frontmatter-reference)
9. [`.questkit.yaml` configuration reference](#9-questkityaml-configuration-reference)
10. [Multi-zone setup](#10-multi-zone-setup)
11. [Versioning: Syncthing + Git](#11-versioning-syncthing--git)
12. [Git hooks and validation](#12-git-hooks-and-validation)
13. [IDE and tool integration](#13-ide-and-tool-integration)
14. [Agentic support](#14-agentic-support)
15. [Known limitations and open questions](#15-known-limitations-and-open-questions)
16. [Appendix: full worked example](#16-appendix-full-worked-example)

---

## 1. Purpose & design philosophy

questkit exists to answer one narrow question well: *"where do I put a
piece of work I want to remember, and how do I find it again?"* — for
everything from "buy stamps" to "rebuild the deploy pipeline," for a human
skimming a kanban board and for an agent grepping frontmatter, without
requiring a server, a database, an account, or a sync service beyond
whatever already moves your files around.

It replaced two systems that both failed this test differently: **Beans**
(an upstream ticket framework whose frontmatter didn't match the Realm's
own metadata standard, and whose noun — "bean" — was welded to that one
framework) and **Trello** (a real server, a real account, and — per the
migration analysis in `QST-whm2e` — four boards running mostly on
Butler/Home-Assistant automation with declining human engagement, which is
what happens when the tracker lives somewhere you have to go to it instead
of it being where you already are).

Five design commitments fall out of that:

- **A quest is a file.** One Markdown file, YAML frontmatter on top, a
  `.md` file for a body. No database, so no schema migrations, no export
  format problem, no "what happens when the service shuts down." `grep`
  and `cat` are always valid query tools.
- **Filenames are immutable.** `QST-<id>--<slug>.md` is fixed at creation.
  A later title edit never renames the file. This is the single decision
  that makes cross-references safe to write by hand and safe for links to
  survive — the tradeoff is that `quest validate` will report filename/title
  drift as informational noise, forever, rather than "fixing" it by
  renaming (see [§12](#12-git-hooks-and-validation)).
- **One log, one scope, per command.** Every command resolves to exactly
  one quest log (a `quests/` directory) and operates only within it. There
  is no cross-log write, and no cross-log reference concept. This is a
  deliberate v1 boundary, not an oversight — see
  [§15](#15-known-limitations-and-open-questions) and `QST-vl9cq` for the
  live discussion about whether that should ever change.
- **Capture must be instant.** `quest new "title"` with nothing else is a
  complete, valid quest — `description` is the only field that's
  situationally required (waived while `status: draft`), specifically so a
  half-formed idea never has to wait on a fully-formed sentence.
- **Correctness should be structural, not enforced by discipline.** Where
  a rule can be made true by construction — list formatting, a self-alias,
  a `modified` date — questkit fixes it on every save rather than asking a
  human or a linter to remember it. Where it can't (a missing description,
  a dangling reference), `quest validate` says so and stops there; it
  never guesses at a fix (see [§12](#12-git-hooks-and-validation) on why
  `--fix` was deliberately not built).

## 2. Role inside The Realm

questkit is deliberately a **standalone, Realm-agnostic** tool — nothing in
`src/questkit/` imports or assumes anything about The Realm's directory
topology, Syncthing folders, or Obsidian vaults. That's on purpose: it
should work the same way if you dropped it into an unrelated project on an
unrelated machine.

Inside The Realm specifically, though, it plays a defined role:

- **The catch-all log** lives at `02-projects/common/quests/` — a
  dedicated Git repo whose root *is* the log (no nested `quests/` folder;
  `QST-*.md` files sit directly at the top, alongside `.questkit.yaml`).
  It holds anything without a home yet, and cross-cutting Realm-tooling
  ideas. `git: auto` there, since the repo's only content is quest files.
- **Per-zone logs** opt in one at a time via `quest init`, inside whatever
  repo the work actually belongs to. As of this writing: `pensieve/quests/`
  (`project: pensieve`, 26 quests, migrated from the old shared `beans`
  repo), `99-system/quests/` (`project: system`, migrated from
  `TODOS.md`), `02-projects/peter/2026-career-transition/quests/`
  (`project: career-transition`, migrated from `career-todos.md`), and
  questkit's own `quests/` (`project: questkit` — questkit tracks its own
  backlog in itself).
- **`make quest`/`make status`** are the Realm's own shims over the CLI,
  wired into `99-system/Makefile` (see [§7](#7-make-integration)).
- **The Realm's root `AGENTS.md`** routes "bean"/"ticket"/"todo" — spoken
  synonyms from before this existed — to quest creation, so an agent
  primed on the Realm's conventions never has to be told twice.
- **`QST-whm2e`**, in the central log, is the founding design document:
  every decision here, and every correction made discovering those
  decisions didn't quite survive contact with real data, is logged there
  with a date. Treat it as the historical record; treat this file as the
  current reference.

The old `beans` repo (`02-projects/common/beans/`) is kept only as a
frozen, marked-obsolete historical reference — do not create new tickets
there.

## 3. Core concepts

| Term | Meaning |
|---|---|
| **Quest** | One unit of work: a single `QST-<id>--<slug>.md` file, frontmatter + body. |
| **Quest log** | A directory containing quest files plus a `.questkit.yaml` marker. The unit of scope for every command. |
| **Zone** | Realm-specific term for "a repo that has opted a quest log in." Not a questkit concept — questkit just sees "a directory with `.questkit.yaml` in it." |
| **Marker** | `.questkit.yaml`'s real job: its mere *presence* inside a `quests/` directory is what makes that directory a log. A bare `quests/` folder with no marker is just a folder — this protects public repos from accidentally becoming a log just because someone made a folder with that name. |
| **Central/catch-all log** | The one log with no natural project owner — in The Realm, `02-projects/common/quests/`. Reached via the `QUEST_LOG` environment variable when no nearer log exists. |

Everything else in questkit is built out of these five ideas plus the
resolution order described next.

## 4. Installation

There are three separate things you might want, and they're independent:

### 4.1 For development on questkit itself

```bash
cd 02-projects/lazytarget/questkit
uv venv
uv pip install -e ".[dev]"
```
See [§5](#5-development) for the full loop.

### 4.2 For Make-shim usage only (`make quest`, `make status`)

Nothing to do manually — `make setup-venv` (part of `make init-system`)
already runs:

```makefile
@$(PIP_CMD) install -e $(DIR_PROJECTS)/lazytarget/questkit $(QUIET_REDIRECT)
```

installing questkit in editable mode into the same shared, per-OS venv
`99-system` uses for everything else (`$(VENV)`, resolved per-OS/per-device
— see the Makefile's OS-detection block). The Make targets call
`$(VENV)/bin/quest` by absolute path, so this alone is enough for
`make quest "title"` / `make status` to work from anywhere in the Realm,
with zero PATH configuration.

### 4.3 For a bare `quest`/`qst` on your interactive shell PATH

This is the one manual, per-device step, and it's why: Syncthing already
propagates questkit's *source* the moment it syncs to a device (it's just
files, in an ordinary `realm-projects-lazytarget`-synced folder) — what it
deliberately does **not** and *should* not propagate is a *compiled
install* (a venv is a set of platform- and Python-version-specific
binaries; syncing one across a Linux desktop, a Mac laptop, and Android
Termux would not work even if it did sync).

`make setup-venv` also runs this, best-effort:

```makefile
-@uv tool install --editable $(DIR_PROJECTS)/lazytarget/questkit $(QUIET_REDIRECT)
```

The leading `-` means a missing `uv` doesn't fail the whole target — you
still get the shared-venv install from §4.2 either way. If `uv` **is**
present (install it once per device if not:
<https://docs.astral.sh/uv/getting-started/installation/>), this step
alone gets you a global `quest`/`qst`:

```bash
$ uv tool install --editable /path/to/02-projects/lazytarget/questkit
Installed 4 executables: qst, quest, quest-bump-modified, quest-validate

$ cd anywhere/at/all && quest list
QST-0grby  in-progress  high      Integrate kivra-sync
...
```

`--editable` means future edits to questkit's source apply immediately —
no reinstall needed, same property as the shared-venv install. Executables
land in `~/.local/bin` (uv's managed tool-install location; it's added to
PATH automatically by `uv` on first use on most setups).

### 4.4 Outside The Realm entirely

```bash
pip install -e .          # from a checkout, for now
# pip install questkit    # once published to PyPI -- not yet
```

## 5. Development

```bash
cd 02-projects/lazytarget/questkit
uv venv
uv pip install -e ".[dev]"
.venv/bin/pytest -q
.venv/bin/ruff check .
```

Notes for anyone changing questkit itself:

- **Test before you commit, every time** — `pytest` (37 tests as of this
  writing) covers config load/save, discovery/resolution, id generation,
  the Quest round-trip and list-style normalization, schema validation
  (including AFK-readiness and the identity/slug-drift split), slugify's
  Unicode handling, and full CLI-integration lifecycles (init → new → list
  → show → set → done → validate, plus the reference-resolution checks).
  `ruff check .` (rules: `E W F I UP B SIM RUF`, line length 100, `E501`
  ignored since `_yaml.width = 4096` already keeps frontmatter lines long
  on purpose) catches the rest.
- **`Quest.save()` is the one place formatting happens.** If you're adding
  a new frontmatter field or command, don't hand-roll YAML dumping — build
  a `CommentedMap`/plain dict, assign through `Quest`, call `.save()`, and
  the list-style normalization and `---` framing happen for you
  automatically.
- **`schema.validate_quest()` is hard rules only.** If a new check has any
  legitimate reason to fire on correct, intentional data (see
  `check_slug_drift`'s reasoning), it does not belong in
  `validate_quest()` — add it as a separate function, call it from
  `commands/validate.py`'s CLI loop, and leave `hooks.py`'s
  `validate_main()` (which only calls `validate_quest()`) alone. Otherwise
  you will make the pre-commit hook block commits on things that were
  never bugs.
- **Bump the hook pin after committing.** Anyone consuming questkit's
  hooks (`quest init --hooks` was run against their repo) has a `rev:`
  pinned to a specific commit. A code change to `hooks.py`/`schema.py`
  doesn't take effect for them until their `.pre-commit-config.yaml`'s
  `rev:` is bumped to your new commit — see
  [§12](#12-git-hooks-and-validation).
- **The `secrets`/`unicodedata`/`re` standard-library choices are
  deliberate**, not placeholders: `secrets.choice` for id generation (not
  `random` — doesn't matter cryptographically here, but there's no reason
  to reach for the weaker one), `unicodedata.normalize("NFKD", ...)` +
  ASCII-ignore-encode for `slugify()` (transliterates `å/ä/ö/é/ñ/ü/...`
  instead of silently deleting the letter — found and fixed after it
  mangled every Swedish-titled quest during migration).

## 6. CLI reference

Every subcommand accepts `--in DIR` to override discovery entirely for
that one call (see [§10](#10-multi-zone-setup) for the full resolution
order). Examples below assume you're standing inside an already-opted-in
log unless `--in` is shown explicitly.

### `quest new "title" [options]`

```
quest new "title" [--type X] [--tier X] [--status X] [--priority X]
                   [--project X] [--description X] [--tag X ...]
                   [--in DIR] [--edit]
```

Generates a fresh random id, writes `QST-<id>--<slugified-title>.md` into
the resolved log, seeds the body from the default template (`##
Description`, `## Acceptance Criteria` with one empty checkbox, `## Log`
with a "captured" line dated today), and prints the created path.

- `--tag` is repeatable: `--tag home --tag electronics` → `tags: [home,
  electronics]`.
- `--status` defaults to the log's configured default (normally `draft`).
  While `status` is `draft`, `description` is *not* written at all — this
  is the mechanism that keeps capture to two seconds; fill it in later via
  `quest set`.
- `--project` overrides the log's own configured `project:` (see
  [§9](#9-questkityaml-configuration-reference)); if neither is set, the
  field is omitted entirely.
- `--edit` opens `$EDITOR` on the new file afterward; silently skipped
  (with a message) if `$EDITOR` isn't set.
- If the log's config has `git: auto`, the new file is committed
  immediately, pathspec-limited to just that file, with the message
  `quest(<log-dir-name>): new <id> <title>`.

```bash
$ quest new "Fix the garage door sensor" --type task --priority high --tag home
/home/.../quests/QST-x7k2m--fix-the-garage-door-sensor.md
```

### `quest list [options]`

```
quest list [--status a,b,...] [--type X] [--tag X] [--in DIR]
```

Prints one line per matching quest: id, status, priority, title — column
widths adjust to the widest id present. **Default status filter is
`todo,in-progress,blocked`** if `--status` isn't given — this is why a
freshly-`draft`-captured quest doesn't show up until it's groomed past
draft. `--status`/`--type` accept comma-separated lists; `--tag` currently
takes one tag per invocation and matches quests where that tag is present
among the quest's own (possibly multiple) tags.

```bash
$ quest list --status completed --tag gdrive
QST-15xxa  completed    medium    GDrive: Parse and Apply gdriveignore
QST-4idp1  completed    medium    GDrive: Document and Sheet Ingress Compilation
...
```

### `quest show <id> [--in DIR]`

Prints the full raw file content (frontmatter and body, unmodified) for
the quest matching `<id>`. Matching is by filename prefix — `QST-x7k2m` or
the full `QST-x7k2m--fix-the-garage-door-sensor` both work, and matching is
via `find_by_id()`'s glob (`{id}*.md`), not the `id:` frontmatter field, so
it's correct even if frontmatter were ever hand-edited to disagree (which
`quest validate` would also catch — [§12](#12-git-hooks-and-validation)).

### `quest set <id> field=value [field=value ...] [--in DIR]`

Applies one or more raw frontmatter assignments, then always bumps
`modified` to today and saves (which also runs list-style normalization).
There is no schema-aware coercion beyond one special case: `tags=a,b,c`
splits on commas into a list; every other field is assigned the literal
string you pass — `quest set QST-x priority=high` sets `priority: high`,
but there's nothing stopping `quest set QST-x priority=extremely-high`
from being written (that's what `quest validate` is for, deliberately —
see [§1](#1-purpose--design-philosophy) on why validation doesn't guess).
Same `git: auto` behavior as `new`, with message
`quest(<log-dir-name>): update <id>`.

```bash
$ quest set QST-x7k2m status=in-progress priority=high tags=home,urgent
/home/.../quests/QST-x7k2m--fix-the-garage-door-sensor.md
```

### `quest done <id> [--in DIR]`

Exactly `quest set <id> status=completed` — a two-character-shorter way to
write the single most common transition.

### `quest init [DIR] [options]`

```
quest init [DIR] [--project NAME] [--git auto|manual] [--base] [--hooks]
```

Opts a directory into being (or extends) a quest log. **Idempotent by
design** — safe to run any number of times; never overwrites an existing
`.questkit.yaml`, `quests.base`, or an existing questkit entry in
`.pre-commit-config.yaml`.

- **Target resolution**: `DIR` defaults to cwd. If the target's basename is
  already `quests`, it's used directly as the log root (this is how the
  central log works — the repo root *is* named `quests`); otherwise a
  `quests/` child is created under it. So `quest init` from inside a
  normal project repo creates `<repo>/quests/`; pointed at (or run from
  inside) something already named `quests/`, it uses that directory
  itself.
- `--project NAME` is written into the new config's `project:` key (only
  meaningful on first creation — see [§9](#9-questkityaml-configuration-reference)).
- `--git auto|manual` sets the config's `git:` key at creation time
  (default `manual` if omitted — see [§11](#11-versioning-syncthing--git)).
- `--base` writes `quests/quests.base`, an Obsidian Bases view (see
  [§13](#13-ide-and-tool-integration)). Skipped with a message if one
  already exists.
- `--hooks` wires questkit's own pre-commit hooks into the *git repo*
  containing the target (walks up looking for `.git`; a no-op with a
  message if there isn't one) — see [§12](#12-git-hooks-and-validation)
  for exactly what this does.

```bash
$ quest init --project pensieve --git manual --hooks --base
[quest init] .../pensieve/quests: wrote .questkit.yaml
[quest init] .../pensieve/quests: created quests directory
[quest init] .../pensieve/quests/quests.base: wrote Obsidian Bases view
[quest init] .../pensieve/.pre-commit-config.yaml: appended questkit hooks
[quest init] .../pensieve: pre-commit hook installed
```

### `quest validate [--in DIR]`

Checks every file matching the log's configured `pattern` (default
`QST-*.md`) against the full rule set — see
[§12](#12-git-hooks-and-validation) for exactly what's checked and why the
hook checks a strict subset of it. Exits `0` with a summary line if clean,
`1` with a `[!] path` / `error: ...` block per problem file otherwise.

```bash
$ quest validate
[quest validate] 26 quest(s) checked, no errors
```

### Global error handling

Every subcommand's exceptions are caught once, centrally, in `cli.main()`
— a domain error (no log found, config version mismatch, etc.) always
prints as `[quest] error: <message>` to stderr and returns exit code `1`;
you will never see a raw Python traceback from normal usage.

## 7. Make integration

`99-system/Makefile` wires two shims over the CLI:

```makefile
quest:
	@$(QUEST) new "$(QUEST_ARGS)"

status:
	@$(QUEST) list
```

`$(QUEST)` resolves per-OS to the shared venv's binary (`$(VENV)/bin/quest`
on POSIX, `Scripts\quest.exe` on Windows), so these work with zero PATH
setup as long as `make setup-venv` has run once. `QUEST_LOG` is
Makefile-defaulted (`?=`, so a real environment variable still wins) to
`$(DIR_PROJECTS)/common/quests` — meaning `make status` from the Realm
root, with no zone-local log nearby, still resolves to the central log
instead of erroring.

```bash
$ make quest "Fix the garage door sensor"
$ make status
```

**A note for anyone touching this Makefile block**: the multi-word-title
absorption trick (`ifeq (quest,$(firstword $(MAKECMDGOALS))) ...
.DEFAULT:`) exists because Make's own goal-parsing needs help — without
it, `make quest "two words"` errors with `No rule to make target "two
words"`. The comment in the Makefile right above that block explains a
real bug that was found and fixed here: the *obvious*-looking fix,
`$(eval $(QUEST_ARGS):;@:)`, re-splits the reconstructed title on
whitespace and defines a no-op **per word** rather than for the whole
phrase — which silently breaks if the title happens to contain the word
"quest" or "bean" itself (it collides with the real target). `.DEFAULT:`
was verified in isolation before landing here; don't revert to the
`$(eval ...)` pattern.

`make bean` still exists, as a deliberate deprecation stub — it absorbs
its arguments the same way but only ever prints a pointer at `make quest`,
on purpose, so the nudge is actually seen rather than silently routed
around.

## 8. Frontmatter reference

| Field | Required? | Type | Notes |
|---|---|---|---|
| `id` | Yes | `QST-xxxxx` | 5-char lowercase base36, random (not sequential — see [§1](#1-purpose--design-philosophy)/README on why). Must match the filename's id prefix (`quest validate`, hard rule). |
| `title` | Yes | string | Human-readable. Editing this after creation does **not** rename the file — see [§12](#12-git-hooks-and-validation) on slug drift. |
| `description` | Situational | string, ≤200 chars | Required unless `status: draft`. `quest new` defaults it to the title if `--description` isn't given (once status isn't draft). |
| `created` | Yes | `YYYY-MM-DD` | Set once, at creation. |
| `modified` | Yes | `YYYY-MM-DD` | Bumped by `quest set`/`done` and by the `quest-bump-modified` hook on every commit that touches the file. |
| `type` | Yes | enum | `feature \| task \| bug \| epic \| milestone \| chore` |
| `tier` | No | enum | `spark \| brief \| blueprint` — spec-workflow weight, inherited unchanged from the Realm's three-tier model. Sits directly after `type` by convention. |
| `status` | Yes | enum | `draft \| todo \| in-progress \| blocked \| parked \| completed \| scrapped` |
| `priority` | Yes | enum | `critical \| high \| medium \| low \| deferred` |
| `effort` | No | enum | `xs \| s \| m \| l \| xl` |
| `owner` | No | free text | Deliberately **not** a closed enum — questkit doesn't know who's on your team. (In The Realm specifically, the convention is `peter`/`jenika`, but that's a usage pattern, not a schema constraint — see `QST-whm2e`'s Open Follow-ups.) |
| `agentic` | No | enum | `afk \| hitl`. Absent means "not yet triaged for agent handoff." See [§14](#14-agentic-support). |
| `project` | No | free text | CLI-stamped from the log's config at creation if the log declares one (see [§9](#9-questkityaml-configuration-reference)); `quest validate` flags disagreement between a quest's own value and its log's declared value, but only if the log declares one at all. |
| `due` | No | `YYYY-MM-DD` | Rarely used in practice — most quests never need a hard date. |
| `tags` | Yes | list of strings | Presence of the *key* is required (an empty list is fine); lowercase kebab-case by convention. |
| `blocked_by` | No | list of `QST-xxxxx` | One direction only — there is no `blocks` field. The reverse relationship ("what does this block") is always computable from the full set of quests in a log (and is exactly what Obsidian backlinks do automatically); storing both directions invites drift when only one side gets updated. `quest validate` resolves every id here against the current log. |
| `aliases` | Yes (CLI-created) | list, always includes own `id` | Drives Obsidian search/quick-switcher/autocomplete. Does **not** make a bare `[[id]]` wikilink resolve on click — see [§13](#13-ide-and-tool-integration). `quest validate` (hard rule) flags a missing self-alias. |
| `related_adrs` | No, not schema-enforced | list of ADR references | Not part of the closed schema at all — carried over from the Beans-era migration as free-form extra metadata. Any field not listed here is accepted without complaint; `quest validate` never rejects unknown keys. |

List fields always render flow-style (`[a, b]`) at 0–1 items and
block-style (one per line) at 2+ — see the README's "List field style"
section for the mechanics; it happens automatically, there's no field-level
control over it.

## 9. `.questkit.yaml` configuration reference

Lives **inside** the `quests/` directory it governs — this is deliberate:
a quest log plus its config is a single, portable, self-contained unit
that can be pointed at with `--in` from anywhere, or copied elsewhere, and
takes its own rules with it.

```yaml
---
version: 1
pattern: "QST-*.md"
prefix: "QST-"
id_length: 5
git: manual
project: pensieve
defaults:
  type: task
  status: draft
  priority: medium
```

| Key | Default | Effect |
|---|---|---|
| `version` | `1` | Read-only in practice — if a future breaking config change ships, it will bump this, and an old questkit reading a newer config raises `ConfigVersionError` loudly instead of silently misinterpreting it. There is currently exactly one version. |
| `pattern` | `QST-*.md` | The glob every log-scanning command (`list`, `validate`) uses to enumerate quest files. Changing the `prefix` alone does **not** change this — they're independent knobs; keep them consistent by hand if you customize either. |
| `prefix` | `QST-` | Prepended to generated ids by `quest new`. |
| `id_length` | `5` | Random suffix length. `generate_id()` retries up to 50 times on a same-directory collision before giving up with an actionable message suggesting you raise this — raise it if a log ever gets large enough that collisions start happening in practice (extremely unlikely at 5 chars / base36 for any realistic log size). |
| `git` | `manual` | `manual`: questkit never touches git; you (or your existing commit conventions/agent instructions) commit. `auto`: `new`/`set`/`done` commit their own change immediately, pathspec-limited to the one touched file, with message `quest(<log-dir-name>): <new\|update> ...`. If the log isn't inside a git repo at all, `auto` mode prints a warning and continues rather than erroring. See [§11](#11-versioning-syncthing--git) for when to choose which. |
| `project` | *(absent)* | If set: `quest new` auto-stamps every new quest's `project:` field with this value (unless `--project` overrides it per-call), and `quest validate` flags any quest whose own `project:` disagrees. If absent (as in the central/catch-all log): no auto-stamping, no drift-checking — quests there can carry any `project:` value, or none, purely as free-form metadata. |
| `defaults.type` / `.status` / `.priority` | `task` / `draft` / `medium` | Used by `quest new` whenever the corresponding `--type`/`--status`/`--priority` flag isn't given. Loading a config that doesn't specify one of these three falls back to the same hardcoded defaults — `defaults:` in the file only needs to list the ones you want to override. |

Config values load through the exact same `ruamel.yaml` instance used for
quest files (`preserve_quotes=True`, wide line width, `---` document-start
marker on save) — so a hand-edited `.questkit.yaml` follows the same
formatting conventions as quest files themselves.

## 10. Multi-zone setup

**Resolution order, for every command, every time:**

1. **`--in DIR`** — explicit, wins over everything, errors immediately
   (with an actionable message pointing at `quest init`) if `DIR` isn't
   already a log.
2. **Walk up from cwd.** For each ancestor directory `A` starting at cwd:
   check `A/.questkit.yaml` (covers standing *inside* a log whose root is
   named `quests`, e.g. the central log), then `A/quests/.questkit.yaml`
   (covers standing anywhere inside a normal project repo that has opted a
   `quests/` child in). First hit wins; keep walking up to the filesystem
   root if neither matches.
3. **`QUEST_LOG` environment variable** — deliberately checked *last*, not
   first. Checking it first would break "nearest zone wins" on every
   machine where it's set, i.e. all of them (The Realm sets it via
   `make setup-venv`'s Makefile default so `make status`/`make quest` from
   the Realm root land in the central log).
4. **An actionable error** — `no quest log found: run 'quest init' here,
   or set QUEST_LOG to your central log.` Never an interactive prompt;
   scripts and agents get a clean failure to react to instead of hanging.

**Opting a new zone in** is exactly `quest init` (see [§6](#6-cli-reference)),
run once, from inside the repo that should get its own log. Nothing else
is required — no registry to update, no central config to edit. The
*only* signal that a directory is a log is the presence of
`.questkit.yaml` inside its `quests/` folder; there is no implicit
opt-in from a bare `quests/` directory existing with nothing in it.

**Choosing `--project`** at init time: give it a project name if the log
belongs to one clear thing (a single repo, a single initiative) — you get
auto-stamping and drift-checking for free. Leave it unset for a log that's
intentionally a catch-all for many unrelated things (this is exactly the
central log's situation) — there, `project:` on individual quests is
optional, free-form metadata with no log-level enforcement.

**There is no cross-log query or write.** Each command's log resolution
produces exactly one directory; nothing in questkit iterates over
multiple logs. See [§15](#15-known-limitations-and-open-questions) for the
current workarounds and the open question of whether that should change.

## 11. Versioning: Syncthing + Git

Quest logs in The Realm are typically versioned by **both** Syncthing (for
device-to-device sync) and Git (for history) simultaneously, and the two
interact in specific ways worth understanding:

- **Immutable filenames matter to both.** Syncthing's file-versioning
  (`.stversions/`) and Git's history both work best with stable paths —
  a renamed file looks like a delete+create to either system, discarding
  the "same object, new content" relationship that makes diffs and version
  history useful. questkit's immutable-filename design (§1) isn't just
  about links; it's also why quest history stays legible in `git log
  --follow` and in Syncthing's version archive.
- **`git: auto` vs `manual` is really a question of who else is committing
  to this repo.** The central/catch-all log's only content is quest files
  — every mutation is self-contained, so auto-committing there is pure
  convenience with no downside. A log living inside a code repo (pensieve,
  99-system, career-transition currently all use `manual`) usually wants
  one commit pairing a code change with the ticket update it resolves;
  auto-committing there would force two commits instead of one, and can
  surface git's own failure modes (mid-merge, mid-rebase) as a `quest`
  command error instead of a git error. `auto` mode's pathspec-limited
  commit (`git commit -- <exact file>`, never `-a`, never a push) is a
  safety rail if you do choose `auto` somewhere with other content — it
  can never accidentally sweep in unrelated staged changes.
- **Syncthing conflicts are handled the same way any other Markdown file's
  conflicts are** — questkit doesn't do anything special here. A
  simultaneous edit to the same quest from two offline devices produces a
  Syncthing conflict-copy file (`QST-x...sync-conflict-....md`), which
  `quest validate`/`quest list` will not recognize as a quest at all
  (`config.pattern` only matches `QST-*.md`, and a conflict-suffixed name
  doesn't match the *end* of that pattern in a way that breaks anything —
  it just sits there as an unrecognized file until you resolve it by hand,
  same as any other Syncthing conflict).
- **Random, non-sequential ids exist specifically for this environment.** A
  sequential counter (`QST-0001`, `QST-0002`, ...) has no safe home in a
  system where two devices can each create a new quest while offline from
  each other — they'd mint the same next number and collide the moment
  they resync. Base36 random ids make that collision astronomically
  unlikely instead of guaranteed; `generate_id()`'s same-directory glob
  check is a same-device belt-and-suspenders, not the actual collision
  defense (which is just "5 random base36 characters is a big enough
  space").

## 12. Git hooks and validation

### What ships

`.pre-commit-hooks.yaml` (at the root of the questkit repo) defines two
hooks, both `language: python`, both matching
`files: (^|/)QST-[^/]+\.md$` (deliberately *not* requiring a `quests/`
path segment — the central log's own files sit at its repo root with no
such segment in their git-relative path; an earlier version of this regex
missed that and the hooks silently never ran there):

- **`quest-validate`** → `hooks.validate_main()`. Runs `schema.
  validate_quest()` — and *only* that — against each staged file passed to
  it. Fails (nonzero exit, blocking the commit) if any hard rule fails.
- **`quest-bump-modified`** → `hooks.bump_modified_main()`. Rewrites
  `modified:` to today's date (and, as a side effect of calling
  `Quest.save()`, normalizes list styles) on each staged file, if it isn't
  already today. Pre-commit's own behavior then applies: a hook that
  modifies files fails that run so you can review/re-stage — this is
  standard pre-commit UX, not something questkit does specially.

### Hard rules vs informational — the split that matters

`schema.validate_quest()` — used by **both** `quest validate` and the
`quest-validate` hook — contains only rules where a failure means
something is *actually wrong*: missing required fields, an enum value
outside its allowed set, an AFK quest missing the substance to hand off,
a filename/frontmatter id mismatch, a missing self-alias.

Two checks are deliberately **excluded** from `validate_quest()` and thus
from the hook, even though `quest validate` (the CLI) reports them:

- **`check_slug_drift()`** — compares the filename's slug against a
  freshly-slugified title. This is *expected* to disagree the moment a
  title is edited after creation (filenames are immutable — §1) or
  whenever a migration deliberately chose a better slug than mechanical
  slugify would. Wiring this into the hook would block ordinary commits
  on dozens of already-accepted, intentional cases — confirmed the hard
  way: running the check for the first time against the whole Realm's
  migrated corpus produced ~30 such findings, none of them bugs.
- **Cross-reference resolution** (`blocked_by`/backlink checking, in
  `commands/validate.py`, not `schema.py`) — needs the log's directory to
  resolve against, which the hook's per-file invocation doesn't have
  cleanly available, and conceptually belongs with the CLI's full-log
  view rather than a per-file hook check.

If you're adding a new validation rule and unsure which bucket it belongs
in, ask: *"can this fire on data that is completely correct and
intentional?"* If yes, it's CLI-only, called from `commands/validate.py`,
never from `hooks.py`.

### Wiring hooks into a repo

`quest init --hooks` (see [§6](#6-cli-reference)) does this structurally,
not by string-matching a marker comment: it parses (or creates)
`.pre-commit-config.yaml`, checks whether a `questkit`/`quest-validate`
entry already exists (skips if so — safe to re-run), and otherwise appends
a `repo:` entry. Two things worth knowing:

- **The `repo:` value is a local filesystem path**, not a GitHub URL —
  questkit doesn't have a public remote yet. `pre-commit`'s `repo:` field
  accepts any git-clonable target, including a local path, so this works
  today; it can be pointed at a real URL later without changing the
  mechanism.
- **`rev:` is resolved dynamically** to questkit's own current
  `git rev-parse HEAD` at the moment `--hooks` runs, found by walking up
  from the *installed* package's `__file__` looking for `.git` — meaning
  this only resolves to a real commit if questkit itself is installed in
  editable mode from a git checkout (true for every install path described
  in [§4](#4-installation)). If questkit has no commits yet at all,
  `rev: HEAD` is written with an explicit console warning to re-run
  `--hooks` after committing.

### Keeping the pin current

Because `rev:` is pinned, a fix landed in questkit's own `hooks.py`/
`schema.py` does **not** retroactively apply to any repo that already ran
`--hooks` — their hook still runs whatever code existed at the pinned
commit. There is currently no automated "refresh the pin" command (that
gap is exactly what `QST-d8nu7`, in the central log, proposes solving with
a `make plan-git-hooks`/`make apply-git-hooks` pair); until that exists,
bumping a pin is a manual edit:

```bash
cd 02-projects/lazytarget/questkit && git rev-parse HEAD
# then, in each consuming repo's .pre-commit-config.yaml:
#   rev: <that sha>
```

Verify a bump actually works before trusting it:

```bash
pre-commit run quest-validate --files quests/QST-something.md
```

## 13. IDE and tool integration

### Obsidian

- **Bases** (core plugin, no install needed on any reasonably current
  Obsidian) renders `quests/quests.base` (written by `quest init --base`)
  as a kanban/table view grouped by `status`. Treat the generated file as
  a starting point — Bases is a new-ish format and worth checking it opens
  the way you expect.
- **Cross-reference links must use the full filename, no pipe** —
  `[[QST-x7k2m--fix-the-garage-door-sensor]]`, not a bare `[[QST-x7k2m]]`
  and not the piped `[[QST-x7k2m--fix-the-garage-door-sensor|QST-x7k2m]]`
  form either. The reasoning, confirmed against upstream Obsidian
  behavior rather than assumed:
  - A **bare alias-only link does not resolve on click** — Obsidian's
    wikilink resolver reads only `uniqueFileLookup` (built from
    filenames), never frontmatter `aliases`. Clicking one creates a blank
    new note instead of navigating anywhere.
  - The piped form *does* resolve (it's a real filename match with custom
    display text), but it's strictly more characters than the plain full
    name, and hides the descriptive slug behind a cryptic id — worse for
    a human scanning backlinks, no cheaper for an agent reading them. It
    was the first fix attempt and was superseded the same day it landed.
  - `aliases:` is still worth keeping regardless — it drives Obsidian's
    *search* and *quick-switcher* (`Ctrl/Cmd+O`), and its *autocomplete*:
    type `[[QST-x7k2m`, Obsidian matches on the alias and inserts the full
    correct link for you. It's only pre-written/scripted links (migration
    scripts, an agent generating a cross-reference programmatically) that
    need to write the full form by hand.
- **Wikilinks cannot cross Obsidian vault boundaries, at all** — confirmed
  against upstream behavior, not a setting or a plugin gap. A quest in one
  zone's log linking to a quest in another zone's log will only ever
  resolve when a vault containing *both* is open (a realm-root vault
  nesting every zone) — never when a narrower, single-zone vault is open.
  Every cross-reference in The Realm today happens to be same-zone, so
  this hasn't caused a real broken link yet, but it's a hard ceiling: for
  a genuinely cross-zone reference, write plain text (`QST-x7k2m` — still
  greppable, still `quest show`-able) instead of a wikilink that will
  silently fail to resolve in the common case of a narrower vault.
- **Validate code-fences before trusting backlink checks visually** —
  `quest validate`'s reference-resolution deliberately skips fenced code
  blocks and inline code spans when scanning for wikilinks, precisely so
  documentation showing wikilink *syntax* as an example (like this file,
  and `QST-whm2e`) isn't misread as a set of real, dangling references.

### Plain editors / VS Code / terminal

No special integration needed or provided — a quest is a Markdown file
with YAML frontmatter, and every tool that already understands that
(syntax highlighting, frontmatter-aware snippets, etc.) works unmodified.
`quest show`/`quest list`/`grep` cover the read path without an editor at
all.

### AI agents

See [§14](#14-agentic-support) — the short version is: the CLI's output is
plain, greppable text by design (no JSON mode yet, no need for one so
far), every command's failure mode is a clean one-line message rather than
a traceback, and the frontmatter schema itself carries the vocabulary
(`agentic:`) for marking which quests are safe to hand to an agent
unsupervised.

## 14. Agentic support

Two frontmatter fields exist specifically for human/agent collaboration,
deliberately **not conflated into one**:

- **`owner`** — human accountability. Whose quest is this, in the sense of
  who's answerable for it. Free text (§8) — not "who's currently running
  it."
- **`agentic: afk | hitl`** — execution mode. Can (and should) an agent run
  this without a human in the loop, or does it need one? Absent means "not
  yet triaged for handoff" — this is a deliberate third state, distinct
  from both `afk` and `hitl`: a quest doesn't have to declare its
  agent-readiness at creation time, only once it's actually been groomed
  for it.

This split — and the specific `afk`/`hitl` vocabulary — is adapted from
Matt Pocock's `skills`/`sandcastle` framing: **HITL** work is "worked
*with* a human who speaks for themselves"; **AFK** work is "driven by the
agent alone." Critically, in that framing (and here), AFK-readiness is a
*triage outcome you earn*, not a property you declare at capture time —
which is exactly what `quest validate`'s AFK-readiness rule enforces
mechanically:

> A quest with `agentic: afk` **must** carry a body with both a `##
> Acceptance Criteria` section containing at least one checklist item
> (`- [ ]` or `- [x]`) and a `## Spec` or `## Design` section. Missing
> either is a hard validation failure — it's caught by both `quest
> validate` and the pre-commit hook, because a quest without that
> substance is not something an agent can actually execute unsupervised,
> regardless of what its `agentic:` field claims.

```yaml
agentic: afk
```
```markdown
## Description
...
## Spec
1. Do the specific thing.
2. In this specific way.
## Acceptance Criteria
- [ ] The specific thing is verifiably done.
```
passes. The same frontmatter with only a `## Description` and no `## Spec`
or `## Acceptance Criteria` fails with a message naming exactly which
section is missing.

### Routing spoken language to quest creation

Inside The Realm, the root `AGENTS.md` carries the instruction that
"bean", "ticket", and "todo" are spoken synonyms for "quest" — an agent
told to "create a ticket for this" should create a quest via `make quest
"<title>"` (or `quest new` directly), landing wherever nearest-zone-wins
discovery puts it, with no clarifying question needed. This is a Realm
convention, not something questkit's code enforces (questkit itself has
no opinion on what a human calls the thing) — but it's worth knowing this
document's audience includes agents primed on that instruction, arriving
here specifically to learn *how* to act on it.

### Practical agent workflow

1. **Capture immediately, groom later.** `quest new "title"` — don't wait
   to have a description ready; `status: draft` exempts it.
2. **Update state as you go**, not just at the end: `quest set <id>
   status=in-progress` when starting real work on something, `quest done
   <id>` when verified complete, `quest set <id> status=scrapped` if
   abandoned. This mirrors the same authorization the Realm's Beans-era
   conventions granted agents for ticket state — questkit doesn't gate any
   of these transitions.
3. **Before marking something `agentic: afk`** for a *future* agent to
   pick up unsupervised, make sure the body actually has a `## Spec`
   section and real acceptance criteria — then `quest validate` confirms
   it, rather than trusting your own judgment that it's ready.
4. **Prefer `quest show`/`grep` over reading a whole log's directory** when
   you only need one quest's content or a targeted search — the same
   token-efficiency guidance that applied to Beans applies here
   unchanged: `quest list` for an overview, `quest show <id>` for one
   file, `grep` across `quests/*.md` for a targeted content search, rather
   than opening every file.

## 15. Known limitations and open questions

- **No cross-log query.** Every command resolves to exactly one log; there
  is no `quest list --all` spanning multiple logs. Two working
  workarounds exist today (a discovery loop over every `.questkit.yaml`
  found under a root, and plain `grep` across `quests/*.md` — both
  demonstrated with real, tested output in `QST-vl9cq`, in questkit's own
  log, along with three candidate designs for a real implementation and
  the open question of whether one is even worth building given the
  workarounds already work for free).
- **No cross-log write, and no cross-log reference concept.** By design,
  not yet-implemented — see §1 and `QST-vl9cq` for the reasoning. If this
  ever changes, it should be a deliberate decision, not a side effect of
  solving the query gap above.
- **Wikilinks cannot cross Obsidian vault boundaries.** Confirmed upstream
  behavior, not fixable by questkit or any Obsidian plugin — see
  [§13](#13-ide-and-tool-integration).
- **Recurrence is explicitly out of scope.** Recurring work (weekly
  chores, monthly reports) deserves its own design, not a bolt-on field —
  see the README's "What's deliberately not here" and `QST-whm2e`'s
  Out-of-Scope section for the fuller reasoning (this was the single most
  sophisticated part of the Trello setup questkit replaced, and doing it
  justice means not rushing it).
- **No hook-pin refresh command yet.** Bumping a consuming repo's
  `rev:` after a questkit change is a manual edit today — tracked as
  `QST-d8nu7` in the central log.
- **An unexplained Syncthing artifact.** A `.stversions/` version-archive
  copy of a quest file turned up once, in a Syncthing folder
  (`90-playground`) that shouldn't have any relationship to the quest logs
  at all. Noticed, not investigated — flagged in `QST-whm2e`'s Log as
  worth a look, since it might indicate a folder-scope overlap in the
  Realm's Syncthing configuration unrelated to questkit itself.
- **`owner` has no closed enum, on principle** — but that principle hasn't
  been tested by more than one real person using a shared log yet. Worth
  revisiting if that changes.

## 16. Appendix: full worked example

A quest that's been through a full lifecycle — created, groomed, worked,
and completed — with every field in play:

```markdown
---
id: QST-x7k2m
title: Fix the garage door sensor false-triggering at night
description: The Home Assistant garage door sensor reports "open" for a few seconds around 2-4am with the door physically closed.
created: 2026-08-01
modified: 2026-08-13
type: bug
tier: spark
status: completed
priority: high
effort: s
owner: peter
project: home-lab
tags:
  - home-assistant
  - sensors
blocked_by: []
aliases: [QST-x7k2m]
---

## Description

Reed switch sensor on the garage door reports a spurious "open" state for
a few seconds, almost always between 2 and 4am, with the door physically
and verifiably closed the whole time. Triggers a false "garage door open"
notification.

## Acceptance Criteria

- [x] Reproduce reliably or capture enough log data to diagnose
- [x] Identify root cause (temperature-related contact bounce, RF
      interference, or a HA automation retriggering the entity)
- [x] Apply a fix
- [x] Confirm no false triggers for at least one full week after the fix

## Log

- 2026-08-01: captured
- 2026-08-03: confirmed via HA history graph -- happens on cold nights
  specifically, correlates with temperature drop, not motion/RF
- 2026-08-05: root cause -- reed switch gap widened slightly from cold
  contraction, right at the edge of trigger tolerance
- 2026-08-06: adjusted magnet mounting bracket closer, added a 5-second
  debounce to the HA binary_sensor template as a second layer of defense
- 2026-08-13: one full week, zero false triggers -- done
```

Notice what's *absent* on purpose: no `agentic:` (never triaged for
handoff — this was worked directly), no `due` (never needed one), no
`related_adrs` (not every quest needs architectural context). A minimal
quest is valid with far less than this — see the default template in
[§6](#6-cli-reference)'s `quest new` section for the actual floor.
