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
7. [Frontmatter reference](#7-frontmatter-reference)
8. [`.questkit.yaml` configuration reference](#8-questkityaml-configuration-reference)
9. [Multi-zone setup](#9-multi-zone-setup)
10. [Versioning: Syncthing + Git](#10-versioning-syncthing--git)
11. [Git hooks and validation](#11-git-hooks-and-validation)
12. [IDE and tool integration](#12-ide-and-tool-integration)
13. [Agentic support](#13-agentic-support)
14. [Known limitations and open questions](#14-known-limitations-and-open-questions)
15. [Appendix: full worked example](#15-appendix-full-worked-example)

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
  renaming (see [§11](#11-git-hooks-and-validation)).
- **Capture is single-log; mutation and querying are not.** `quest new`
  always lands in exactly one log — nearest-zone-wins, with a fatal guard
  against an ambiguous destination — so where a *new* thing gets filed is
  never a silent guess. But since ids are globally unique, `quest set` /
  `show` / `done` resolve by id alone: the nearest log is checked first,
  then every other log under `QST_ROOT` is swept, and whichever single file
  matches gets mutated in place, wherever it lives. `quest list -A`
  aggregates read-only across every log the same way. There is still no
  *bulk* multi-log write, and still no cross-log reference concept — this
  is the v2 answer `QST-vl9cq` asked for (see
  [§9](#9-multi-zone-setup)/[§14](#14-known-limitations-and-open-questions)).
- **Capture must be instant.** `quest new "title"` with nothing else is a
  complete, valid quest — `description` is the only field that's
  situationally required (waived while `status: draft`), specifically so a
  half-formed idea never has to wait on a fully-formed sentence.
- **Correctness should be structural, not enforced by discipline.** Where
  a rule can be made true by construction — list formatting, a self-alias,
  a `modified` date — questkit fixes it on every save rather than asking a
  human or a linter to remember it. Where it can't (a missing description,
  a dangling reference), `quest validate` says so and stops there; it
  never guesses at a fix (see [§11](#11-git-hooks-and-validation) on why
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
  repo), `99-system/quests/` (`project: realm-system`, migrated from
  `TODOS.md`), `02-projects/peter/2026-career-transition/quests/`
  (`project: career-transition`, migrated from `career-todos.md`), and
  questkit's own `quests/` (`project: questkit` — questkit tracks its own
  backlog in itself).
- **The `quest`/`qst` CLI is used directly** — installed globally via `uv
  tool install --editable` (part of `make setup-venv`; see §4.3). There is
  no Make wrapper: an earlier `make quest`/`make status` shim was removed
  in favor of calling the CLI itself everywhere.
- **The Realm's root `AGENTS.md`** routes "bean"/"ticket"/"todo" — spoken
  synonyms from before this existed — to quest creation, so an agent
  primed on the Realm's conventions never has to be told twice.
- **`QST-whm2e`**, in questkit's own log, is the founding design document:
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

### 4.2 Shared per-OS venv (automatic, for 99-system tooling)

Nothing to do manually — `make setup-venv` (part of `make init-system`)
already runs:

```makefile
@$(PIP_CMD) install -e $(DIR_PROJECTS)/lazytarget/questkit $(QUIET_REDIRECT)
```

installing questkit in editable mode into the same shared, per-OS venv
`99-system` uses for everything else (`$(VENV)`, resolved per-OS/per-device
— see the Makefile's OS-detection block). This isn't itself a way to get a
bare `quest` command on your interactive shell PATH — for that, see §4.3.

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
Installed 5 executables: qst, quest, quest-bump-modified, quest-format, quest-validate

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

- **Test before you commit, every time** — `pytest` (99 tests as of this
  writing) covers config load/save, discovery/resolution (including the
  cross-log sweep, the ambiguity guard, and `ignore:`/`#include`
  resolution), id generation, the Quest round-trip and list-style
  normalization, schema validation (undeclared-field checks under
  `strict: true`, the
  identity/slug-drift split, the dynamic schema engine's `extends` merge
  and custom-field validation), `quest list`'s `--where` filter grammar and
  output formats, `quest schema`'s introspection output, slugify's Unicode
  handling, and full CLI-integration lifecycles (init → new → list → show
  → set → done → validate, plus the reference-resolution and cross-log
  checks). `ruff check .` (rules: `E W F I UP B SIM RUF`, line length 100,
  `E501` ignored since `_yaml.width = 4096` already keeps frontmatter lines
  long on purpose) catches the rest.
- **`Quest.save()` is the one place formatting happens.** If you're adding
  a new frontmatter field or command, don't hand-roll YAML dumping — build
  a `CommentedMap`/plain dict, assign through `Quest`, call `.save()`, and
  the list-style normalization and `---` framing happen for you
  automatically.
- **`schema.validate_quest()` is hard rules only.** If a new check has any
  legitimate reason to fire on correct, intentional data (see
  `check_slug_drift`'s reasoning), it does not belong in
  `validate_quest()` — add it as a separate function, call it from
  `commands/validate_cmd.py`'s CLI loop, and leave `hooks.py`'s
  `validate_main()` (which only calls `validate_quest()`) alone. Otherwise
  you will make the pre-commit hook block commits on things that were
  never bugs.
- **Bump the hook pin after committing.** Anyone consuming questkit's
  hooks (`quest init --hooks` was run against their repo) has a `rev:`
  pinned to a specific commit. A code change to `hooks.py`/`schema.py`
  doesn't take effect for them until their `.pre-commit-config.yaml`'s
  `rev:` is bumped to your new commit — see
  [§11](#11-git-hooks-and-validation).
- **The `secrets`/`unicodedata`/`re` standard-library choices are
  deliberate**, not placeholders: `secrets.choice` for id generation (not
  `random` — doesn't matter cryptographically here, but there's no reason
  to reach for the weaker one), `unicodedata.normalize("NFKD", ...)` +
  ASCII-ignore-encode for `slugify()` (transliterates `å/ä/ö/é/ñ/ü/...`
  instead of silently deleting the letter — found and fixed after it
  mangled every Swedish-titled quest during migration).

## 6. CLI reference

Every subcommand accepts `--in DIR` to override discovery entirely for
that one call (see [§9](#9-multi-zone-setup) for the full resolution
order). Examples below assume you're standing inside an already-opted-in
log unless `--in` is shown explicitly.

### Resolving `--in` by name

Every command that takes `--in DIR` also accepts a **project name**: `--in
family` resolves to whichever log declares `project: family`, matched against
every log discovered under the sweep root (`--root`, `QST_ROOT`, the git root,
or cwd). **One rule** decides name vs. path: a value containing a `/` or `\`,
or naming a directory that exists on disk, is a **path**; anything else is a
name. Disk existence wins the tie, so a directory that happens to share a
project's name still resolves as the path.

`project:` is therefore **identity, not a label** — unique per log, enforced by
`quest logs` and `quest validate`. A path that is not itself a log, but has
logs beneath it, expands to all of them for a read command (`--in
02-projects/grocy-ecosystem` behaves like `--in
02-projects/grocy-ecosystem/quests`); a single-target command (`new`, `show`,
`set`, ...) errors naming the candidates instead of guessing. Errors are
actionable: an unknown name lists the known project names and their paths.

### `quest new "title" [options]`

Beyond the shorthand flags below, **`--set field=value` (repeatable) writes any
declared field.** argparse is built before the log is resolved, so it cannot
grow a flag per custom field; `--type`/`--status`/`--priority`/`--description`/
`--tag` stay as shorthands for fields every schema has.

```bash
quest new "Fix the importer" --status todo --set component=api --set effort=s
```

Note `quest set` keeps *positional* assignments (`quest set <id> field=value`).
The asymmetry has a cause: `new` has a positional title, so
`quest new "fix thing" type=bug` is genuinely ambiguous, while `set`'s id plus
`nargs="*"` is not. Passing `--set` to `quest set` is an error naming the right
form rather than a second grammar.

**`--set` naming a field the schema does not declare is checked against
`strict`** (see [§8](#8-questkityaml-configuration-reference)): under the
default `strict: true` it is a hard error listing the log's declared fields
(core plus custom); under `strict: false` it is a warning on stderr and the
field is written anyway. The shorthand flags are never subject to this check —
they always name core fields.

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
  [§8](#8-questkityaml-configuration-reference)); if neither is set, the
  field is omitted entirely.
- `--edit` opens `$EDITOR` on the new file afterward; silently skipped
  (with a message) if `$EDITOR` isn't set.
- If the log's config has `git: auto`, the new file is committed
  immediately, pathspec-limited to just that file, with the message
  `quest(<log-dir-name>): new <id> <title>`.
- **Destination resolution is stricter than a plain walk-up**: if no
  ancestor log is found from cwd *and* two or more quest logs exist
  somewhere downward, `quest new` fails fast rather than guessing —
  `Ambiguous destination. Multiple quest logs found in subdirectories.
  Specify target with --in <DIR>.` (See [§9](#9-multi-zone-setup).)
- **Custom fields** (declared in the log's `schema.fields` — see
  [§8](#8-questkityaml-configuration-reference)) are written into the new
  quest's frontmatter as explicit `null`, one `[warning]` per field printed
  to stderr, so an agent (or a human) notices the field needs filling in
  rather than silently missing it.

```bash
$ quest new "Fix the garage door sensor" --type task --priority high --tag home
/home/.../quests/QST-x7k2m--fix-the-garage-door-sensor.md
```

### `quest list [options]`

```
quest list [--where EXPR ...] [-A|--all-logs] [--root DIR ...] [--in LOG ...]
           [--format table|json|csv|prompt]
           [--select a,b,c] [--distinct] [--count]
           [--sort field[:asc|desc][,field[:asc|desc] ...]]
           [--limit N] [--offset N] [--out FILE] [--quiet|-q]
```

A dynamic filter/export engine rather than a fixed set of flags — this is
the v2 rewrite that also answers `QST-vl9cq`'s open question about
multi-log querying.

- **`--where EXPR`** is repeatable; each `EXPR` is one of:
  - `field=value` — equality; case-insensitive; a list-valued field (like
    `tags`) matches if *any* of its own values are in the set.
  - `field~value` — substring match on a scalar field, or membership match
    on a list field (`tags~frontend`).
  - `field:exists` — the field is present and non-blank/non-empty.
  - `field!=value` — the negation of `=`. An **absent** field satisfies it: a
    quest with no `agentic` genuinely is `agentic != afk`.
  - `field>value`, `field<value`, `field>=value`, `field<=value` — comparison.
    Numeric where both sides look numeric (frontmatter is untyped, so a count
    may arrive as `20` or `"20"`), string otherwise. ISO dates need no special
    case: they compare correctly as plain strings, so
    `--where "status_changed<2026-08-05"` works with no date parsing.

  Operators are matched in the order `:exists`, `!=`, `>=`, `<=`, `~`, `>`,
  `<`, `=` — the compound ones **must** be tried before their single-character
  prefixes, or `>=` gets shredded into `>` with a value that silently gains a
  leading `=`.

  **`value` may be a comma-list for both `=` and `~`** — `status=todo,
  in-progress` or `tags~frontend,backend` — matched as OR: any one of the
  listed values satisfies that single clause. **Repeating `--where` for the
  same field is AND instead**: `--where "tags~frontend" --where
  "tags~urgent"` requires *both* tags present, whereas `--where
  "tags~frontend,backend"` requires *either*. Across *different* fields,
  every `--where` clause is always ANDed together regardless of repetition
  (`--where "status=todo" --where "tags~frontend"` means status is todo
  **and** tags contains frontend).

  **Default status filter is `todo,in-progress`** if no `--where` clause
  targets `status` at all — a synthesized `--where` clause under the hood; a
  freshly-`draft`-captured quest still doesn't show up until groomed past
  draft. (`blocked` left the core status enum in v0.3 — see
  [§4](#7-frontmatter-reference) — so it can no longer appear in this list; a
  quest with an open dependency is marked in the table instead, via the
  computed `blocked` field below.) Override the filter with an explicit
  `--where "status=..."`, or use `--where "status:exists"` as the "show every
  status" escape hatch.

- **Computed fields** — `blocked`, `blocks`, `idle`, `age` — are derived once
  per query over the whole active row set and behave like any other field for
  `--where`, `--select` and `--sort`. They are **read-only**: `quest set <id>
  blocked=true` is an error.

  | Field | Type | Meaning |
  |-------|------|---------|
  | `blocked` | bool | any `blocked_by` reference resolves to a quest that is neither terminal nor archived |
  | `blocks` | int | how many non-terminal, non-archived quests list this one in their own `blocked_by` |
  | `idle` | int | days since `status_changed` (falling back to `created` when absent) |
  | `age` | int | days since `created` |

  Both `blocked` and `blocks` resolve each referenced quest against **that
  quest's own log's** `terminal_statuses` — a cross-log reference (see
  [§14](#14-known-limitations-and-open-questions)) is judged by the log it
  actually lives in, not the querying log's vocabulary. A blocked row's
  `status` cell in table output reads `todo [blocked]`; JSON/CSV expose
  `blocked` as its own field instead, so nothing there is duplicated.

  ```bash
  quest list --where "idle>14"                 # stale: untouched status for 2+ weeks
  quest list --where "blocked=true" --sort blocks:desc
  ```
- **`-A` / `--all-logs`** aggregates quests from every log found by recursive
  descent from `--root` (repeatable; or `QST_ROOT`, or the git root, or cwd —
  see [§9](#9-multi-zone-setup)), instead of resolving to just one log. No
  hidden `--all` alias — the old flag is gone outright, not aliased (argparse's
  own unambiguous-prefix abbreviation still lets `--all` *type-ahead* to
  `--all-logs`, which is a general CLI property, not something this quest
  introduces). A `project` column (the log's configured `project:`, or its
  directory name if unset) is appended automatically in this mode. A log whose
  config fails to load (bad version, broken schema `extends`) is skipped with a
  `[quest list] skipping ...` warning rather than aborting the whole
  aggregation.
- **`--root DIR`** is repeatable, de-duplicating resolved paths so overlapping
  roots never emit the same quest twice. `QST_ROOT` accepts several paths
  separated by `os.pathsep` (`:` on Linux/macOS, `;` on Windows — not a literal
  `:`, since a Windows `C:\` would shred a colon split).
- **`--in LOG`** is repeatable and resolves each value by name or by path (see
  [§8](#8-questkityaml-configuration-reference)) — `--in family --in
  realm-common` sweeps exactly those two logs, expanding a directory value to
  every log beneath it. It stays a *bounded search set*: nothing beyond the
  named logs is ever swept in.
- **More than one log in scope groups the `table` output** — a separator names
  each log and its row count, with the column header repeating underneath it
  (a single header 60 rows up would make each group non-copy-pasteable on its
  own). `json` and `csv` stay flat arrays either way, ordered by log, so
  `quest list --format json | jq '.[].title'` is unaffected by grouping.
- **`--format`**: `table` (default, human-readable, a header row plus the
  resolved columns) · `json` (a JSON array — the full parsed frontmatter of
  every matching quest, unless `--select` narrows it) · `csv`
  (spreadsheet-friendly, list fields joined with `;`) · `prompt` (a compact
  per-quest text block meant for pasting into an agent's context:
  id/status/priority/title, then type/tags, then description, blank line
  between quests).
- **`--select a,b,c`** restricts output to the named fields, **in the given
  order**, and applies to **every** `--format` — table, csv, json and prompt
  alike. This is a **widened contract**, not a rename of the old `--columns`
  (which is gone outright, not aliased): rows are projected to the selected
  fields exactly once, before any renderer sees them, so `json`/`prompt`
  respect it too rather than always dumping the full frontmatter. Naming an
  unknown field is a hard error listing the valid fields (core fields plus
  every declared custom field across the logs in scope).
- **`--distinct`** collapses rows identical across the `--select`'d fields,
  preserving first-seen order. Requires `--select` — without a set of fields
  to compare, "distinct" has nothing to mean, so it errors rather than
  silently doing nothing.
- **`--count`** prints a bare integer to stdout, suitable for `$( )`. Honors
  `--where`, `--select` and `--distinct`; **ignores** `--limit`/`--offset` —
  "how many are there" and "show me the first ten" are different questions,
  and a `--count` that respected `--limit` could only ever return
  `min(n, limit)`.

  ```bash
  quest list -A --select project --distinct              # which projects have open quests
  quest list -A --select id,title --format prompt        # minimal agent digest
  quest list -A --where status=todo --count               # 86
  ```

  **When more than one log is in scope**, an unknown `--select` field is a
  hard error only if it is absent from *every* log's schema — one declared by
  at least one log gets a stderr note naming the logs that lack it, and
  renders blank there rather than dropping the column for the whole table.
- **`--quiet` / `-q`** silences the summary block below.
- **`--sort field[:asc|desc][,field[:asc|desc] ...]`** — multi-key, stable,
  and ranked by each field's **declared vocabulary order** rather than
  alphabetically. Quests missing the *first* key always sort last, regardless
  of direction: with a `desc` sort they would otherwise lead the table, and "no
  effort recorded" is not the largest effort.

  Vocabularies (`statuses`, `priorities`, `efforts`, `tiers`, `types`) are
  ordered sequences, so `--sort priority:asc` means critical-first. This is
  load-bearing, not cosmetic — as sets they sorted lexicographically, so
  `--sort priority:asc` returned `critical, deferred, high, low, medium` and
  `--sort effort:asc` returned `l, m, s, xl, xs`. A field with no declared
  vocabulary (a title, a free-text custom field) falls back to a string sort,
  and a value outside its vocabulary sorts *last* rather than first, so a typo
  cannot silently outrank `critical`.

  Under `-A` the ranking uses the first resolved log's vocabulary. For a
  single log that is exact; across logs declaring *different* vocabularies it
  is an approximation until per-log grouping lands (`QST-iqwjm`). Merging two
  independently declared orderings has no correct answer, so questkit does not
  invent one.
- **`--limit N` / `--offset N`** — applied after filtering and sorting.
- **`--out FILE`** — the rendered output is still printed to stdout as
  normal, *and* written to `FILE` (tee semantics, not a silent redirect).

```bash
$ quest list --where "status=done" --where "tags~gdrive"
QST-15xxa  done       medium  GDrive: Parse and Apply gdriveignore
QST-4idp1  done       medium  GDrive: Document and Sheet Ingress Compilation
...

# tags~frontend,backend -- OR within the clause: either tag qualifies
$ quest list --where "tags~frontend,backend"

# --where repeated on the same field -- AND instead: both tags required
$ quest list --where "tags~frontend" --where "tags~urgent"

$ quest list -A --root .. --where "status:exists" --format json | jq '.[].title'
```

### The stderr summary block

Every `quest list` invocation prints a scope summary to **stderr**, silenced
by `--quiet`/`-q`. Rows go to stdout, so `| jq` and `--out FILE` stay clean:

```
$ quest list --in questkit --in realm-system
...rows on stdout...
[quest list] where  status=todo,in-progress
[quest list]        (status filter is a default -- override with --where status:exists)
[quest list] sort   priority:asc
[quest list] logs   2 logs swept
```

It always states the *injected default status filter* and how to override it
— a query whose answer depends on an implicit default must say so, not leave
the reader to infer it from a suspiciously short result. When `--select`
spans logs with different declared fields, a `note` line names which logs
lack a selected field before the field-set (name-only, once) and enum-count
lines. Deferred to later quests: a `view` line (no named views exist until
`quest next`/`stale`/`blocked` ship) and an `--archived` scope line (no
`archived` query flag exists until archival ships) — both will extend this
same block rather than inventing a second one.

### `quest show <id> [--in DIR]`

Prints the full raw file content (frontmatter and body, unmodified) for
the quest matching `<id>`. `--in DIR` still means exactly what it always
has — a precise, single-log override, with no fallback if the id isn't
found there. Without it, resolution is: the nearest log (today's walk-up)
first; if the id isn't there, every other log under `QST_ROOT` (or the git
root, or cwd) is swept until it turns up somewhere (see
[§9](#9-multi-zone-setup)). Matching within a log is by filename prefix
— `QST-x7k2m` or the full `QST-x7k2m--fix-the-garage-door-sensor` both
work — via `find_by_id()`'s glob (`{id}*.md`), not the `id:` frontmatter
field, so it's correct even if frontmatter were ever hand-edited to
disagree (which `quest validate` would also catch —
[§11](#11-git-hooks-and-validation)).

### `quest set <id> field=value [field=value ...] [--in LOG ...]`

Applies one or more raw frontmatter assignments, then always bumps
`modified` to today and saves (which also runs list-style normalization).
There is no schema-aware coercion beyond one special case: `tags=a,b,c`
splits on commas into a list; every other field is assigned the literal
string you pass — `quest set QST-x priority=high` sets `priority: high`,
but there's nothing stopping `quest set QST-x priority=extremely-high`
from being written (that's what `quest validate` is for, deliberately —
see [§1](#1-purpose--design-philosophy) on why validation doesn't guess).
Same `git: auto` behavior as `new`, with message
`quest(<log-dir-name>): update <id>`. Id resolution is the same
nearest-then-sweep behavior as `quest show` (above) — this is what lets
`quest set QST-x7k2m ...` work from anywhere without `--in`, as long as
`QST_ROOT` (or a shared git root) covers the log the id actually lives in.
**`--in` is repeatable** (name or path) and, when given, is a *bounded search
set*: the id is looked up only in those named logs, nowhere else — a miss
there is a miss, with no silent sweep past it.

```bash
$ quest set QST-x7k2m status=in-progress priority=high tags=home,urgent
/home/.../quests/QST-x7k2m--fix-the-garage-door-sensor.md
```

### `quest done <id> [--in LOG ...]` / `quest scrap <id> [--in LOG ...]`

`done` writes the log's **first** `terminal_statuses` entry, `scrap` its
**last** — so a log declaring `terminal_statuses: [shipped, cancelled]` gets
`shipped` and `cancelled` from the same two commands, with nothing hardcoded.
Under the default vocabulary that is `done` and `scrapped`.

Otherwise exactly `quest set <id> status=...` — a shorter way to
write the single most common transition. Same id resolution as `set`.

### `quest mv <id> <dest> [--in DIR]`

Moves a quest from whichever log it's currently in to `<dest>` — an
already-`quest init`'d `quests/` directory (a raw path with no
`.questkit.yaml` errors the same way `--in` does everywhere else, pointing
at `quest init`). Id resolution for the source is the same
nearest-then-sweep behavior as `set`/`show`/`done` (see
[§9](#9-multi-zone-setup)); `--in` restricts that lookup, it doesn't affect
where the file ends up.

What it does, in order:

1. **Moves the file.** If the source and destination logs share a single
   git repo, it's a plain `git mv` — a real rename, not a delete+add, so
   `git log --follow` and blame keep working across the move. If they're in
   different repos (or either isn't a git repo at all), it's a filesystem
   move plus a `git add`/removal on whichever side(s) are actually tracked.
   Neither side in git — a plain move, no git involved.
2. **Updates `project:`** to the destination log's configured `project`
   (from its `.questkit.yaml`), if it has one, and bumps `modified`. A
   destination log with no `project:` configured leaves the field alone
   and prints a note — it's not `mv`'s call to guess or clear an existing
   value.
3. **Commits, if `git: auto`** — per log, independently. A same-repo move
   commits once (rename + field updates together, so the rename doesn't
   silently split into an uncommitted delete). A cross-repo move commits
   once per side that has `git: auto`, each in its own repo, with its own
   message. `git: manual` on either side leaves that side's changes staged
   (already `git add`-ed, thanks to step 1) for a human or the pre-commit
   hooks to review and commit.

What it deliberately does **not** do: rewrite the quest's own custom
fields for the new log's schema, fix up hyperlinks/wikilinks elsewhere in
the Realm that pointed at the old path, or resolve a filename/title slug
disagreement (see [§1](#1-purpose--design-philosophy) and
[§11](#11-git-hooks-and-validation) on `quest validate`'s slug-drift
check). The filename itself never changes — moving and renaming are two
separate decisions. Run `quest validate` after a move (in both logs, if
they differ) to see what it flags; a pre-commit hook does the same
automatically if one's wired up on the destination.

```bash
$ quest mv QST-x7k2m ../../lazytarget/some-project/quests
[quest mv] project: 'common' -> 'some-project'
[quest mv] /path/to/common/quests/QST-x7k2m--fix-the-garage-door-sensor.md -> /path/to/some-project/quests/QST-x7k2m--fix-the-garage-door-sensor.md
[quest mv] run 'quest validate' to catch any custom-field drift or now-broken hyperlinks/paths
```

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
  meaningful on first creation — see [§8](#8-questkityaml-configuration-reference)).
- `--git auto|manual` sets the config's `git:` key at creation time
  (default `manual` if omitted — see [§10](#10-versioning-syncthing--git)).
- `--base` writes `quests/quests.base`, an Obsidian Bases view (see
  [§12](#12-ide-and-tool-integration)). Skipped with a message if one
  already exists.
- `--hooks` wires questkit's own pre-commit hooks into the *git repo*
  containing the target (walks up looking for `.git`; a no-op with a
  message if there isn't one) — see [§11](#11-git-hooks-and-validation)
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
[§11](#11-git-hooks-and-validation) for exactly what's checked and why the
hook checks a strict subset of it.

Findings come in two kinds, and only one of them affects the exit code:

| Kind | Prefix | Exit code | Example |
|------|--------|-----------|---------|
| **Error** | `error:` | fails (`1`) | an out-of-vocabulary `status`, a `blocked_by` id that resolves nowhere |
| **Note** | `note:` | never | filename slug drift |

The split matters because filenames are immutable by design, so slug drift is
what *supposed* to happen whenever a title is edited after creation. Reporting
it as an error meant a supported operation made the flagship command red — and
a log that is permanently "failing" is a log whose output nobody reads.
`--no-notes` hides them; it does not change the exit code either way.

```bash
$ quest validate
[quest validate] 23 quest(s) checked, 0 error(s), 2 note(s)
```

### `quest format [PATH ...] [--in DIR] [--check] [--fill-defaults]`

Re-saves every file matching the log's `pattern`, applying `Quest.save()`'s
normalization (list style, date-field quoting, quote style — see
[§7](#7-frontmatter-reference) and the `quest-format` hook in
[§11](#11-git-hooks-and-validation)) with no field-value changes: no
`modified` bump, nothing content-wise touched. Prints one line per file
that actually changed plus a summary; a file already in normalized form is
silently a no-op. This is the bulk/standalone counterpart to the
`quest-format` pre-commit hook — the hook only ever sees staged files on a
commit, so reach for `quest format` to normalize an entire log in one shot
(a log with no git at all, a first-time sweep after a normalization rule
changes, or just checking a log without committing anything).

```bash
$ quest format
[quest format] quests/QST-03dh4--syncthing-custom-folder-groups.md: reformatted
[quest format] 26 quest(s) checked, 1 reformatted
```

Positional targets narrow it to specific files or log directories:

```bash
quest format quests/QST-3ehhu*.md                        # explicit files
quest format 02-projects/family/quests 99-system/quests  # dirs, each using its own pattern
quest format --check                                     # report only; exit 1 if anything would change
```

A directory target resolves **that directory's** config and globs **its**
`pattern`. `pattern`/`prefix`/`id_length` are per-log settings, so a hardcoded
`QST-*.md` would silently format nothing in a log that renamed its prefix — and
report `0 quest(s) checked` as though the log were clean.

`--check` writes nothing and exits `1` if any file would change, which makes it
usable in CI. It shares its predicate with `Quest.render()`, the same code
`save()` uses to decide whether to write, so it can never disagree with what a
real run would do.

`--fill-defaults` writes every declared default into fields a quest is
missing, expanding `{{ }}` macros as it goes. It never overwrites an existing
value and is idempotent. This is a **hard prerequisite** for adopting any
`required: true` field against a live corpus: the moment a log declares one,
`quest validate` fails every quest that predates it and the pre-commit hook
blocks every commit. It deliberately does **not** bump `modified` — backfilling
a field nobody asked about is not a content edit, and a corpus-wide
`--fill-defaults` giving every quest a fresh `modified` is exactly the
laundering `status_changed` exists to prevent.

`quest format` also imposes the schema's **`field_order`** (see
[§8](#8-questkityaml-configuration-reference)); reordering alone counts as a
change.

**A no-op `quest format` touches no mtimes.** `Quest.save()` compares the
rendered content against the file and returns whether it wrote. That is not
just tidiness: the designated committer ([§10](#10-versioning-syncthing--git))
gates on "has this log been quiet for N minutes", and a format run that touched
every file would make that gate permanently see a hot log.

### `quest migrate [--backfill FIELD=SOURCE | --rename-value FIELD:old=new] [options]`

Frontmatter-aware corpus migrations. Two verbs, one per migration shape that
actually mutates files:

| Verb | Does | Guard |
|------|------|-------|
| `--backfill FIELD=SOURCE` | sets `FIELD` from `SOURCE` — another field, a `{{ macro }}`, or a literal — **only where `FIELD` is absent** | never overwrites an existing value |
| `--rename-value FIELD:old=new` | rewrites one value of one field | **that field's value only** — never the body, never another field |

```bash
quest migrate --backfill status_changed=created -A --dry-run
quest migrate --rename-value status:completed=done --in questkit
quest migrate --backfill owner={{ env.USER }} --in family --commit
```

**Why this is a command and not a documented `sed`.** Quest bodies and
`description:` values contain the words being renamed, in ordinary prose.
Verified in questkit's own log:

```
QST-bmzl2  - [ ] Every quest in the Scope table is completed or explicitly scrapped
QST-whm2e  ... Completed quests stay exactly where they were created, forever.
```

A line-oriented substitution corrupts both. Only a frontmatter-aware tool can
rename a *value of a field* without touching text that happens to use the same
word — and questkit is the only thing in the Realm that parses this format.

**Field reference or literal?** Nothing in `FIELD=SOURCE` distinguishes
`status_changed=created` ("copy the `created` field") from `owner=peter` ("the
literal string peter"). The decision is made **once per log**, from that log's
field vocabulary: `schema.CORE_FIELDS`, its declared custom fields, and the
union of keys present in its quests. Per-log rather than per-file on purpose —
deciding per file would make one command mean two things in one directory, with
a quest missing `created` receiving the literal string `"created"` while its
neighbour got a real date.

Shared behavior:

- **`--dry-run` prints a per-file diff and writes nothing.** Not optional for a
  corpus-wide mutation.
- Honors `--in` (repeatable), `-A`/`--all-logs` and `--root`.
- Writes through `Quest.save()`, so a file the migration does not change keeps
  its mtime — which matters across Syncthing.
- **Neither `modified` nor `status_changed` is bumped.** A migration is not a
  content edit, and renaming `completed`→`done` is the same status under a new
  name rather than a transition. The migration that introduces the
  loop-closure signals must not be the thing that launders them.
- **`--commit` is opt-in and refuses outright on a dirty index.** With staged
  changes there is no way to produce a commit containing only the migration,
  and a run touching 129 files across 7 repositories is the wrong place to
  discover that afterwards. Each log commits separately, in its own repo.

### `quest logs [--root DIR ...] [--format table|json] [--verbose]`

Inventories every quest log found under the swept root(s) — read-only; it
never writes, creates, or migrates. Sorted by project name:

```
$ quest logs
PROJECT              QUESTS   OPEN  GIT     PATH
family                    0      0  auto    02-projects/family/quests
questkit                 23     12  manual  02-projects/lazytarget/questkit/quests
...

7 logs, 145 quests (132 open), swept from /home/gitops/realm
```

- **PROJECT** — the config's `project:`, or `-` for a catch-all log with none.
- **QUESTS** — files matching that log's own `pattern`.
- **OPEN** — quests not in a terminal status, per that log's own
  `terminal_statuses` (see [§8](#8-questkityaml-configuration-reference)) —
  never a hardcoded pair, so a log with a renamed vocabulary still reports
  correctly.
- **GIT** — `auto` | `manual`.
- **PATH** — relative to whichever swept root contains it.

The footer names every root swept and the totals — not decoration: selective
Syncthing means a log present on one device is absent on another, so the
scope of any sweep is device-dependent and must be stated, not implied. A
**fully archived log is excluded from the footer totals** (its work is done);
its own row still reports its real counts.

**`project:` uniqueness is enforced here.** A duplicate `project:` across two
logs is a hard error naming both paths — `--in`'s name resolution
([§9](#9-multi-zone-setup)) depends on that uniqueness being true, so a
collision is caught at the one command whose whole job is inventorying every
log at once.

`--format json` emits one object per log with the full config surface —
project, path, counts, `git`, declared custom fields, `strict`, `field_order`
— for programmatic consumers. `--verbose` (table only) adds a second line per
log naming its schema overrides.

A log whose config fails to load (a broken `schema.extends`, a future config
version) still appears as a row — with `?` in place of its counts — rather
than aborting the whole inventory; the warning prints once, after the table,
under a `warning:` line per broken log.

### `quest schema quest [field] [--format json|table] [--in DIR]`

Introspects the active, merged schema for a log — so an agent never has to
guess or hallucinate a valid `status`/`type`/etc. value, or the shape of a
custom field. `quest` is a literal, required first argument (the kind of
thing being introspected — forward-compatible if a second kind is ever
added; there's only ever `quest` today).

- No `field`: dumps the whole merged schema — `types`, `statuses`, `tiers`,
  `priorities`, `efforts` (each an array) plus `fields` (a map of custom
  field name → `{type, required}`).
- `field` given: `type`/`status`/`tier`/`priority`/`effort` (singular)
  return just that vocabulary's array; any other name is looked up as a
  custom field name, returning its `{type, required}` spec. An unknown
  name is a clean one-line error, exit `1`.
- `--format json` (default) or `table` (aligned plain text, same data).

```bash
$ quest schema quest status
["draft", "todo", "in-progress", "parked", "done", "scrapped"]

$ quest schema quest sprint
{"type": "string", "required": true}
```

### Global error handling

Every subcommand's exceptions are caught once, centrally, in `cli.main()`
— a domain error (no log found, config version mismatch, etc.) always
prints as `[quest] error: <message>` to stderr and returns exit code `1`;
you will never see a raw Python traceback from normal usage.

## 7. Frontmatter reference

| Field | Required? | Type | Notes |
|---|---|---|---|
| `id` | Yes | `QST-xxxxx` | 5-char lowercase base36, random (not sequential — see [§1](#1-purpose--design-philosophy)/README on why). Must match the filename's id prefix (`quest validate`, hard rule). |
| `title` | Yes | string | Human-readable. Editing this after creation does **not** rename the file — see [§11](#11-git-hooks-and-validation) on slug drift. |
| `description` | Situational | string, ≤200 chars | Required unless `status: draft`. `quest new` defaults it to the title if `--description` isn't given (once status isn't draft). |
| `created` | Yes | `YYYY-MM-DD` | Set once, at creation. Also the fallback for `status_changed`. |
| `modified` | Yes | `YYYY-MM-DD` | Bumped by `quest set`/`done`/`mv` and by the `quest-bump-modified` hook on every commit that touches the file. Normalizes to a real, unquoted `date` value on save. |
| `type` | Yes | enum | `feature \| task \| bug \| epic \| chore` |
| `tier` | No | enum | `spark \| brief \| blueprint` — spec-workflow weight, inherited unchanged from the Realm's three-tier model. Sits directly after `type` by convention. |
| `status` | Yes | enum | `draft \| todo \| in-progress \| parked \| done \| scrapped` |
| `status_changed` | No | date | the day `status` last changed. Written **only on a real transition**, so it measures staleness where `modified` cannot — `modified` is bumped by the `quest-bump-modified` hook on every commit. Absent means never changed; consumers fall back to `created`. |
| `priority` | Yes | enum | `critical \| high \| medium \| low \| deferred` |
| `effort` | No | enum | `xs \| s \| m \| l \| xl` |
| `owner` | No | free text | Deliberately **not** a closed enum — questkit doesn't know who's on your team. (In The Realm specifically, the convention is `peter`/`jenika`, but that's a usage pattern, not a schema constraint — see `QST-whm2e`'s Open Follow-ups.) |
| `agentic` | No | enum | `afk \| hitl`. Declared by the **`development`** schema, not the core — `afk\|hitl` is not a universal vocabulary, and household work has no unsupervised-agent axis. See [§13](#13-agentic-support). |
| `archived` | No | bool | Whether this quest should still be in front of you. **Orthogonal to `status`**: archiving answers a retention question, scrapping answers what happened to the work, and a `done` quest in a wound-up project is archived and emphatically not scrapped. Sorts into the alphabetical tail of `field_order` — rarely set, never scanned. |
| `milestone` | No | free text | A planning bucket (`0.4.0`, `spring-2027`), declared by the `development` schema. Named `milestone` because it is a bucket that can slip, not a fact. **Not** a membership link — questkit has no parent/child concept. |
| `project` | No | free text | CLI-stamped from the log's config at creation if the log declares one (see [§8](#8-questkityaml-configuration-reference)); `quest validate` flags disagreement between a quest's own value and its log's declared value, but only if the log declares one at all. |
| `due` | No | `YYYY-MM-DD` | Rarely used in practice — most quests never need a hard date. |
| `tags` | Yes | list of strings | Presence of the *key* is required (an empty list is fine); lowercase kebab-case by convention. |
| `blocked_by` | No | list of `QST-xxxxx` | One direction only — there is no `blocks` field. The reverse relationship ("what does this block") is always computable from the full set of quests in a log (and is exactly what Obsidian backlinks do automatically); storing both directions invites drift when only one side gets updated. `quest validate` resolves every id here against the current log. |
| `aliases` | Yes (CLI-created) | list, always includes own `id` | Drives Obsidian search/quick-switcher/autocomplete. Does **not** make a bare `[[id]]` wikilink resolve on click — see [§12](#12-ide-and-tool-integration). `quest validate` (hard rule) flags a missing self-alias. |
| `related_adrs` | No, not schema-enforced | list of ADR references | Not part of the closed schema at all — carried over from the Beans-era migration as free-form extra metadata. Any field not listed here is accepted without complaint; `quest validate` never rejects unknown keys. |

List fields render flow-style (`[]`) only when empty; any non-empty list
always expands to block style (one item per line, even a single item) —
matching Obsidian's own frontmatter writer (see the README's "Frontmatter
formatting" section and [§11](#11-git-hooks-and-validation)). `created`/
`status_changed`/`modified`/`due` normalize to real, unquoted `date` values the
same way.
This happens automatically on every save, there's no field-level control
over it.

**Custom fields** — beyond the closed set above, a log can declare its own
fields via `schema.fields` in `.questkit.yaml` (see
[§8](#8-questkityaml-configuration-reference)). `quest new` writes each as
an explicit `null` with a stderr warning; `quest validate` fails if one
marked `required: true` is still null or missing. This is the only
schema-agnostic escape hatch — everything else in this table is a fixed,
hardcoded vocabulary (itself overridable per-log — see the next section).

## 8. `.questkit.yaml` configuration reference

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
ignore:
  - dist
  - "#include ../../99-system/templates/dot-files/.stignore-code"
schema:
  extends: "../../.questkit.schema.yaml"
  statuses: [draft, todo, in-progress, in-review, shipped, cancelled]
  terminal_statuses: [shipped, cancelled]
  fields:
    sprint:
      type: string
      required: true
```

| Key | Default | Effect |
|---|---|---|
| `version` | `1` | Read-only in practice — if a future breaking config change ships, it will bump this, and an old questkit reading a newer config raises `ConfigVersionError` loudly instead of silently misinterpreting it. There is currently exactly one version. |
| `pattern` | `QST-*.md` | The glob every log-scanning command (`list`, `validate`) uses to enumerate quest files. Changing the `prefix` alone does **not** change this — they're independent knobs; keep them consistent by hand if you customize either. |
| `prefix` | `QST-` | Prepended to generated ids by `quest new`. |
| `id_length` | `5` | Random suffix length. `generate_id()` retries up to 50 times on a same-directory collision before giving up with an actionable message suggesting you raise this — raise it if a log ever gets large enough that collisions start happening in practice (extremely unlikely at 5 chars / base36 for any realistic log size). |
| `git` | `manual` | `manual`: questkit never touches git; you (or your existing commit conventions/agent instructions) commit. `auto`: `new`/`set`/`done` commit their own change immediately, pathspec-limited to the one touched file, with message `quest(<log-dir-name>): <new\|update> ...`. If the log isn't inside a git repo at all, `auto` mode prints a warning and continues rather than erroring. See [§10](#10-versioning-syncthing--git) for when to choose which. |
| `project` | *(absent)* | If set: `quest new` auto-stamps every new quest's `project:` field with this value (unless `--project` overrides it per-call), and `quest validate` flags any quest whose own `project:` disagrees. If absent (as in the central/catch-all log): no auto-stamping, no drift-checking — quests there can carry any `project:` value, or none, purely as free-form metadata. |
| `defaults.type` / `.status` / `.priority` | `task` / `draft` / `medium` | Used by `quest new` whenever the corresponding `--type`/`--status`/`--priority` flag isn't given. Loading a config that doesn't specify one of these three falls back to the same hardcoded defaults — `defaults:` in the file only needs to list the ones you want to override. |
| `ignore` | `[]` | Directory-name/glob patterns pruned when a cross-log sweep (`quest list -A`, cross-log id resolution) walks this log's own tree — see [§9](#9-multi-zone-setup). An entry may instead be `#include <path>` (relative to this file's own directory), pulling in another file's patterns recursively — the same convention `syncthing.yaml`/`scaffold_syncthing.py` uses elsewhere in the Realm, so a log inside the Realm can reuse an existing `.stignore-*` template instead of re-declaring `.venv`/`node_modules`/etc. A handful of common noise directories (`.git`, `.stversions`, `.venv`, `venv`, `node_modules`, `__pycache__`, `.pytest_cache`, `.ruff_cache`) are pruned by default regardless of this key. |
| `schema` | *(absent)* | Overrides/extends the built-in `type`/`status`/`tier`/`priority`/`effort` vocabularies, declares `terminal_statuses`, and/or declares custom fields, for this log only. See the dedicated subsection below — absent entirely, a log behaves exactly as if this key didn't exist at all (full backward compatibility). |

Config values load through the exact same `ruamel.yaml` instance used for
quest files (`preserve_quotes=True`, wide line width, `---` document-start
marker on save) — so a hand-edited `.questkit.yaml` follows the same
formatting conventions as quest files themselves.

### The `schema` block: dynamic vocabularies and custom fields

Absent this key, a log's valid `type`/`status`/`tier`/`priority`/`effort`
values are exactly the built-in vocabularies in `schema.py` (see
[§7](#7-frontmatter-reference)) — nothing below changes anything for a log
that doesn't opt in.

**Vocabularies are ordered, and the order is the sort order.** Declaration
order drives `--sort` (see [§6](#6-cli-reference)), so writing
`priorities: [critical, high, medium, low, deferred]` is what makes
`--sort priority:asc` mean critical-first. Membership checking is unaffected.

**`terminal_statuses`** declares which statuses mean "finished". Four things
need to know: the `OPEN` column of `quest logs`, the `blocked` computation,
`stale`'s exclusion set, and what `quest done` writes. It is **ordered** —
`quest done` writes the first entry, `quest scrap` the last.

It defaults to `[done, scrapped]` intersected with whatever `statuses` the log
declares, which in the default vocabulary is literally the tail of that list,
so the two agree by construction rather than by discipline. A log that
overrides `statuses:` and keeps **none** of the defaults, without declaring
`terminal_statuses`, is a **hard error at config load**. Degrading would mean
an `OPEN` column silently equal to `total` and a `blocked` field that is always
`false` — a wrong answer delivered confidently, which is worse than failing.

**`field_order`** is the explicit head of the frontmatter key order;
everything else sorts alphabetically after it. Default:

```yaml
field_order: [id, title, description, project, type, status, priority, tags,
              created, status_changed, modified]
```

**One rule, not three.** A three-group scheme (ordered natives → alphabetical
natives → alphabetical custom) was rejected because it needs questkit to know
which fields are "native", and that boundary is itself schema-defined — so the
same quest would sort differently in two logs and `quest mv` would silently
reorder frontmatter. It drives `quest new` as well as `quest format`; otherwise
every freshly captured quest is born non-conformant and the next `format`
rewrites it.

**Defaults live in one place.** `schema.fields.<name>.default` is canonical;
the top-level `defaults:` key is sugar writing into the same map. Precedence,
stated once: `--flag` > `fields.<n>.default` > `defaults.<n>` > built-in. A
log's `project:` acts as the lowest-precedence default for the `project` field.

**Macros.** A default may contain `{{ project }}`, `{{ log }}`, `{{ id }}`,
`{{ slug }}`, `{{ title }}`, `{{ today }}`, `{{ owner }}` or
`{{ env.SOMEVAR }}`. Expanded at **one** point — after id generation, before
first save — so `{{ id }}` and `{{ slug }}` are always available and there are
no ordering surprises. Plain substitution, no control flow: `{{ }}` is a strict
subset of Jinja's syntax, so adopting Jinja later would cost nothing, while
`{% if %}` turns a body template into something you debug. An **unknown** macro
is an error, not an empty string — a default silently expanding to nothing
writes a blank field into every quest the log captures and is only ever found
by grep months later.

**Typed fields.** A custom field may declare `type: enum` with `values:`, and
`quest validate` then rejects an out-of-vocabulary value. `values:` is ordered,
so `--sort component:asc` works. `type: enum` with no `values:` is a schema
error (an enum with no vocabulary validates nothing), and `values:` on a
non-enum type is too.

**`required: true` with a *static* default emits a warning.** The requirement
can never fail, so it enforces nothing — validation theater. It stays legal,
because a *computed* default that genuinely varies (`{{ env.USER }}` on
`owner`) carries real information, and the config cannot tell those apart.

**Named schemas.** An `extends:` value carrying a `/`, `\` or a `.yaml`/`.yml`
suffix is a **path**, resolved relative to the `.questkit.yaml`. Anything else
is a **name**, looked up as `<dir>/<name>.yaml` along a search path:
`QST_SCHEMA_PATH` (`os.pathsep`-separated) first, then
`99-system/questkit/schemas/` in each ancestor directory of the log. And
`schema: development` as a bare scalar is shorthand for
`schema: {extends: development}`, which is the common case — four logs sharing
one named schema and adding nothing.

Shared schemas live under `99-system/`, **never the Realm root**.
`99-system/syncthing.yaml` has no folder for `.`: the root is a local
composition of independently-synced folders, not a synced entity. A schema file
there would resolve on one machine and fail silently on every other — the worst
failure shape available. This generalizes to any questkit artifact that must
reach every device.

**Reserved names.** A schema may not declare an enum value or a custom field
named `blocked`, `blocks`, `idle`, `age` or `archived`. Those are computed
field names, and a status value sharing a name with a computed field would make
`--where blocked=true` and `--where status=blocked` two different questions one
word apart — with a quest able to satisfy either without the other. Enforced at
config load.

- **`extends: <path>`**, if present, must be the *first* key read
  conceptually (though YAML key order doesn't matter) — it names another
  file, resolved relative to this `.questkit.yaml`'s own directory, that is
  itself treated as a schema document (so it can chain its own `extends`,
  arbitrarily deep — a circular or missing chain is a loud
  `SchemaExtendsError`, not a silent fallback). Every **sibling key in this
  block fully replaces** the corresponding key inherited from the parent —
  there is no list-merging; a child's `statuses:` entirely overrides the
  parent's, it doesn't union with it.
- **`types` / `statuses` / `tiers` / `priorities` / `efforts`** — override
  the corresponding vocabulary. Any one omitted (here or in every file up
  the `extends` chain) falls back to the hardcoded default for that
  vocabulary specifically — overriding `statuses` doesn't require also
  restating `types`.
- **`fields`** — a map of custom field name → `{type, required}`. `type`
  is currently descriptive only (surfaced by `quest schema`, not enforced
  at write time); `required: true` is enforced by `quest validate` and the
  pre-commit hook — null or missing is a hard failure. `quest new`
  null-initializes every declared field and warns on stderr (see
  [§6](#6-cli-reference)).

Use `quest schema quest [field]` (see [§6](#6-cli-reference)) to introspect
the actual merged result for a log, rather than reading the YAML chain by
hand.

## 9. Multi-zone setup

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
   machine where it's set. Nothing in the Realm sets this for you
   automatically (there's no Make wrapper anymore to default it) — if you
   want `quest`/`qst` run from a directory with no nearby log (e.g. the
   Realm root itself) to fall back to the central log instead of erroring,
   export it yourself: `export QUEST_LOG=/path/to/02-projects/common/quests`
   in your shell profile.
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

### Global-id resolution: `set` / `show` / `done` / `mv`

Because ids are globally-unique random base36 strings, these four
commands don't need `--in` to know *where* to find the quest — they need
it only as a precise override. (`mv` is the odd one out in that it also
takes a second, explicit path — the destination — which follows the
regular `--in`-style resolution instead, i.e. must already be a log.)
Resolution for the id itself:

1. **`--in DIR`**, if given, is the only place searched — a miss there is
   a miss, full stop. No fallback, no sweep past it. This preserves `--in`
   as an unambiguous escape hatch for the rare case an id exists in more
   than one log (shouldn't normally happen, given random ids, but `--in`
   still lets you be exact).
2. Otherwise: the **nearest log** (today's walk-up, see above) is checked
   first.
3. If the id isn't there: every other quest log found by recursive descent
   from the **sweep root** is checked, in sorted-path order, until one
   matches. The sweep root is: an explicit `--root`-equivalent (not
   exposed on these three commands directly, but see `QST_ROOT` next) →
   the `QST_ROOT` environment variable → the git root of cwd → cwd itself.
4. No match anywhere: a clean `no quest matching id '<id>' found` message,
   exit `1` — never a traceback, never a guess.

This is a deliberate, narrow exception to "one log, one scope, per
command" (§1): it only ever *finds* a file across logs, and only ever
*mutates exactly one file* once found. It does not enable bulk multi-log
writes, and there is still no cross-log reference concept — a
`blocked_by`/wikilink still only resolves within its own log (see
[§11](#11-git-hooks-and-validation)).

### `QST_ROOT` and cross-log discovery

`QST_ROOT` is the analogue of `QUEST_LOG` for *sweeps* rather than
single-log resolution — it names the directory `quest list -A` and the
id-resolution sweep above start descending from. Set it once, the same way
`QUEST_LOG` is set today (`make setup-venv`'s Makefile default, or your own
shell profile), to the Realm root (or any ancestor covering every log you
care about). Without it, the git root is a reasonable fallback *if* your
logs share one — they typically don't in The Realm, where `common`,
`pensieve`, `99-system`, and `career-transition` are four unrelated git
repos, which is exactly why `QST_ROOT` exists rather than relying on git
alone.

The sweep (`discovery.find_all_logs()`) walks the tree recursively looking
for `.questkit.yaml`, pruning as it goes:

- A small hardcoded default list is always pruned — `.git`, `.stversions`,
  `.venv`, `venv`, `node_modules`, `__pycache__`, `.pytest_cache`,
  `.ruff_cache` — this alone fixes the noise `QST-vl9cq`'s investigation
  notes flagged (a stray `.stversions/` copy of a quest file showing up in
  a naive `find`/`grep`).
- Each log's own `ignore:` config (see
  [§8](#8-questkityaml-configuration-reference)) extends that for its own
  project — in practice, its parent directory's tree too, since the
  common shape is `project/quests/.questkit.yaml` naming a sibling like
  `project/dist`. A one-level lookahead means declaration order among
  siblings (`dist` sorting before `quests`) doesn't matter.
- A log whose config fails to load during the sweep (bad version, broken
  `schema.extends`, broken `ignore` `#include`) doesn't abort the whole
  sweep — it's skipped with a `[quest]`/`[quest list]` warning printed to
  stderr, and everything else still gets discovered.

### `quest list -A`

The read-only, aggregating counterpart to the above — see
[§6](#6-cli-reference) for the full `--where`/`--format`/`--select`/
`--sort` grammar. This is the v2 answer to `QST-vl9cq`'s open question:
built-in, one process, unified sort/filter across logs, instead of the
discovery-loop and plain-`grep` workarounds that quest previously
documented here (both still work fine for a one-off, but no longer the
only option).

**Writes still don't aggregate.** `quest list -A` is read-only; there
is still no command that mutates more than one file per invocation.

## 10. Versioning: Syncthing + Git

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

## 11. Git hooks and validation

### What ships

`.pre-commit-hooks.yaml` (at the root of the questkit repo) defines three
hooks, all `language: python`, all matching
`files: (^|/)QST-[^/]+\.md$` (deliberately *not* requiring a `quests/`
path segment — the central log's own files sit at its repo root with no
such segment in their git-relative path; an earlier version of this regex
missed that and the hooks silently never ran there). Order matters — a
freshly-wired `.pre-commit-config.yaml` (see below) lists them in exactly
this order, so each hook sees the previous one's output rather than
re-litigating it:

- **`quest-format`** → `hooks.format_main()`. Pure re-save of each staged
  file — normalizes list style, date-field quoting, and quote style (see
  [§7](#7-frontmatter-reference)) with no field-value changes. Runs
  *first* so a file edited outside questkit (Obsidian, by hand) arrives at
  `quest-validate`/`quest-bump-modified` already in normalized form,
  instead of the three hooks disagreeing with each other about style on
  successive commits. See also `quest format` ([§6](#6-cli-reference)) for
  the same normalization run over a whole log outside of a commit.
- **`quest-validate`** → `hooks.validate_main()`. Runs `schema.
  validate_quest()` — and *only* that — against each staged file passed to
  it. Fails (nonzero exit, blocking the commit) if any hard rule fails.
- **`quest-bump-modified`** → `hooks.bump_modified_main()`. Rewrites
  `modified:` to today's date on each staged file, if it isn't already
  today (compared with `str()` on both sides, since `modified` is a real
  `date` object once normalized — a naive `!=` against a plain string
  would never match and rewrite every staged file on every commit). Pre-
  commit's own behavior then applies: a hook that modifies files fails
  that run so you can review/re-stage — this is standard pre-commit UX,
  not something questkit does specially.

### Hard rules vs informational — the split that matters

`schema.validate_quest()` — used by **both** `quest validate` and the
`quest-validate` hook — contains only rules where a failure means
something is *actually wrong*: missing required fields, an enum value
outside its allowed set, an undeclared field under `strict: true`, a
filename/frontmatter id mismatch, a missing self-alias. Readiness (is this
quest *good enough to hand off*, not just well-formed) is a separate,
advisory check — see [§13](#13-agentic-support).

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
  `commands/validate_cmd.py`, not `schema.py`) — needs the log's directory to
  resolve against, which the hook's per-file invocation doesn't have
  cleanly available, and conceptually belongs with the CLI's full-log
  view rather than a per-file hook check.

If you're adding a new validation rule and unsure which bucket it belongs
in, ask: *"can this fire on data that is completely correct and
intentional?"* If yes, it's CLI-only, called from `commands/validate_cmd.py`,
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
gap is exactly what `QST-d8nu7`, in `99-system`'s log, proposes solving with
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

`pre-commit run <hook-id> --all-files` (or `--files <path>...` for a
narrower set) isn't limited to what's staged — it's the bulk-normalization
path for a log that already has hooks wired up, e.g. right after a
`quest-format` normalization rule changes:

```bash
pre-commit run quest-format --all-files
```

For a log with no git repo at all (hooks can't run there, staged or not),
use `quest format [--in DIR]` instead ([§6](#6-cli-reference)) — same
normalization, no git or pre-commit dependency.

## 12. IDE and tool integration

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

See [§13](#13-agentic-support) — the short version is: `quest list
--format json|csv|prompt` gives a structured or agent-tuned view when one
helps, `quest schema quest` (see [§6](#6-cli-reference)) means an agent
never has to guess a valid enum value, every command's failure mode is a
clean one-line message rather than a traceback, and the frontmatter schema
itself carries the vocabulary (`agentic:`) for marking which quests are
safe to hand to an agent unsupervised.

## 13. Agentic support

Two frontmatter fields exist specifically for human/agent collaboration,
deliberately **not conflated into one**:

- **`owner`** — human accountability, in the core schema. Whose quest is this,
  in the sense of who's answerable for it. Free text (§8) — not "who's
  currently running it."
- **`agentic: afk | hitl`** — execution mode, declared by the **`development`**
  schema, not the core. Can (and should) an agent run this without a human in
  the loop, or does it need one? Absent means "not yet triaged for handoff" —
  a deliberate third state, distinct from both `afk` and `hitl`: a quest
  doesn't have to declare its agent-readiness at creation time, only once it's
  actually been groomed for it.

This split — and the specific `afk`/`hitl` vocabulary — is adapted from
Matt Pocock's `skills`/`sandcastle` framing: **HITL** work is "worked
*with* a human who speaks for themselves"; **AFK** work is "driven by the
agent alone."

**`agentic` is not universal, so it is not core.** Household work has no
unsupervised-agent axis, and shipping this vocabulary in the core would be
questkit having an opinion about what kind of work its users do. A log adopts
it by declaring `schema: development` (see [§8](#8-questkityaml-configuration-reference)),
and under `strict: true` (the default) `--set agentic=afk` in a log that
hasn't is a hard error naming the fields that *are* declared.

**AFK-readiness moved from a hardcoded validation rule into `readiness:`, a
schema-driven, advisory check.** The old rule was a category error: it turned
a *grooming judgment* ("is this good enough to hand off?") into a
*commit-blocking contract* — the same job `quest validate` does for "is this
file well-formed at all". `quest validate` enforces **none** of this now and
cannot fail on it. The `development` schema declares the equivalent as a
conditional rule:

```yaml
readiness:
  - require: { where: "description:exists" }
    message: "no description"
  - require: { where: "status!=draft" }
    message: "still a draft — not groomed"
  - require: { sections: ["## Spec", "## Design"] }
    message: "no spec or design section"
  - require: { checklist: "## Acceptance Criteria", min: 1 }
    message: "no acceptance criteria"
  - when: "agentic=afk"
    require: { where: "owner:exists" }
    message: "AFK work needs an accountable owner"
```

The core ships the first four rules (universal — "a spec and acceptance
criteria make work handoff-ready" is not an opinion about a domain); a
`household`-style schema can override the list down to as few as it needs.
`schema.evaluate_readiness(quest, schema_config)` returns every failing rule's
own `message`, in declared order — this is what the future `quest brief`
command's READY verdict reads from, once it ships.

### Routing spoken language to quest creation

Inside The Realm, the root `AGENTS.md` carries the instruction that
"bean", "ticket", and "todo" are spoken synonyms for "quest" — an agent
told to "create a ticket for this" should create a quest via `quest new
"<title>"`, landing wherever nearest-zone-wins discovery puts it, with no
clarifying question needed. This is a Realm
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
   section and real acceptance criteria. `quest validate` no longer checks
   this — it is a `readiness:` rule now, advisory rather than
   commit-blocking; use `schema.evaluate_readiness()` (or the future
   `quest brief`) to confirm it mechanically rather than trusting your own
   judgment.
4. **Prefer `quest show`/`grep` over reading a whole log's directory** when
   you only need one quest's content or a targeted search — the same
   token-efficiency guidance that applied to Beans applies here
   unchanged: `quest list` for an overview, `quest show <id>` for one
   file, `grep` across `quests/*.md` for a targeted content search, rather
   than opening every file. When the overview itself is what you want to
   hand to another agent or paste into a prompt, `quest list --format
   prompt` (or `--format json` for programmatic consumption) is usually a
   better fit than reading raw files.

## 14. Known limitations and open questions

- **Cross-log query and global-id mutation resolution shipped in v2** —
  `quest list -A` and the `set`/`show`/`done` sweep (see
  [§9](#9-multi-zone-setup)) are the answer `QST-vl9cq` asked for; see
  `QST-v0hnq` (questkit's own log) for the full design and the decision
  record. What's still deliberately *not* here: **bulk multi-log writes**
  (every command still only ever mutates one file per invocation) and a
  **cross-log reference concept** (`blocked_by`/wikilinks still only
  resolve within their own log — see [§11](#11-git-hooks-and-validation)).
  If either of those ever changes, it should be its own deliberate
  decision, not a side effect of the query/resolution work already done.
- **`ignore:`/`schema.extends` failures during a sweep degrade per-log,
  not silently** — a broken config anywhere in the swept tree is skipped
  with a printed warning rather than aborting `quest list -A`, but it's
  still worth actually reading those warnings when they show up; nothing
  currently aggregates or de-duplicates them across a large sweep.
- **Wikilinks cannot cross Obsidian vault boundaries.** Confirmed upstream
  behavior, not fixable by questkit or any Obsidian plugin — see
  [§12](#12-ide-and-tool-integration).
- **Recurrence is explicitly out of scope.** Recurring work (weekly
  chores, monthly reports) deserves its own design, not a bolt-on field —
  see the README's "What's deliberately not here" and `QST-whm2e`'s
  Out-of-Scope section for the fuller reasoning (this was the single most
  sophisticated part of the Trello setup questkit replaced, and doing it
  justice means not rushing it).
- **No hook-pin refresh command yet.** Bumping a consuming repo's
  `rev:` after a questkit change is a manual edit today — tracked as
  `QST-d8nu7` in `99-system`'s log.
- **An unexplained Syncthing artifact.** A `.stversions/` version-archive
  copy of a quest file turned up once, in a Syncthing folder
  (`90-playground`) that shouldn't have any relationship to the quest logs
  at all. Noticed, not investigated — flagged in `QST-whm2e`'s Log as
  worth a look, since it might indicate a folder-scope overlap in the
  Realm's Syncthing configuration unrelated to questkit itself.
- **`owner` has no closed enum, on principle** — but that principle hasn't
  been tested by more than one real person using a shared log yet. Worth
  revisiting if that changes.

## 15. Appendix: full worked example

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
status: done
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
