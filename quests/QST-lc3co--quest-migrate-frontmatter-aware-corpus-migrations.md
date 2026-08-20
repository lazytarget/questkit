---
id: QST-lc3co
title: "quest migrate: frontmatter-aware corpus migrations"
description: One migration command with backfill, value-rename and field-move verbs, because sed on frontmatter corrupts prose and every schema change needs the same three jobs.
created: 2026-08-19
status_changed: 2026-08-19
modified: 2026-08-20
type: feature
tier: brief
status: todo
priority: high
effort: s
milestone: 0.3.0
project: questkit
tags:
  - questkit
  - cli
  - schema
blocked_by:
  - QST-mjuau
aliases:
  - QST-lc3co
---

## Description

v3 queues **three** corpus-wide migrations across 129 quests in 7 logs, several
of which are shared with other people:

1. **Backfill `status_changed`** from `created` ([[QST-3h09k--status-changed-frontmatter-field-and-reusable-backfill]])
2. **Rename `status: completed` → `done`** ([[QST-j68u5--schema-engine-field-order-defaults-macros-typed-fields-strict-writes]] rule 11)
And `quest format --fill-defaults` is a third of the same shape.

**The `agentic` demotion needs no migration at all** — moving it from core to the
`development` schema changes `schema.py` and `development.yaml`; the 16 files
already carrying `agentic:` do not change. The only thing needed is a *check*
("which logs carry this field without declaring it"), and `quest validate` under
`strict: true` already reports exactly that. A migrate verb for it would be a
second implementation of an existing check.

**The decider is not convenience — it is that `sed` is unsafe here.** Quest
bodies and `description:` values contain these words in ordinary prose. Verified
in this very log on 2026-08-19:

```
QST-bmzl2:114  - [ ] Every quest in the Scope table is completed or explicitly scrapped
QST-whm2e:65   ... Completed quests stay exactly where they were created, forever.
```

A line-oriented substitution corrupts both. Only a frontmatter-aware tool can
rename a *value of a field* without touching prose that happens to use the same
word — and questkit is the only thing in the Realm that parses this format.

## Spec

### Scope

**In:** `quest migrate` with two verbs, `--dry-run`, `--commit`, and multi-log
scoping. Roughly 90 lines plus tests — most of the machinery (log-set resolution,
the summary block, safe writes) is inherited from quests already scheduled.
**Out:** schema *file* migration (config `version:` bumps), rollback/undo (git is
the undo), and any automatic migration on load — migrations are always explicit.

### Approach

```bash
quest migrate --backfill status_changed=created -A --dry-run
quest migrate --backfill status_changed=created -A

quest migrate --rename-value status:completed=done -A
quest migrate --rename-value priority:normal=medium --in family

```

Two verbs, one per migration shape that actually mutates files:

| Verb | Does | Guard |
|------|------|-------|
| `--backfill FIELD=SOURCE` | sets `FIELD` from `SOURCE` (another field, a literal, or a `{{ }}` macro) **only where FIELD is absent** | never overwrites an existing value |
| `--rename-value FIELD:old=new` | rewrites one enum value of one field | **only that field's value** — never the body, never other fields |

Shared behavior:

- Honors `--in` (repeatable) and `-A`/`--root` ([[QST-iqwjm--multi-log-query-ux-all-logs-repeatable-in-and-root-per-log-grouping-summary-block]]) — a migration must be scopeable to one log, because these logs are shared and you will not always want to touch someone else's.
- **`--dry-run` prints a per-file diff and writes nothing.** Not optional: a corpus-wide mutation with no preview is not shippable.
- Writes via `Quest.save()`, so it inherits write-only-on-change ([[QST-mjuau--quest-save-writes-only-when-the-rendered-content-changes]]) — a migration that is a no-op for a file leaves its mtime alone, which matters across Syncthing.
- Does **not** bump `modified` (a migration is not a content edit) and does **not** touch `status_changed` (renaming `completed`→`done` is the same status under a new name, not a transition). Both are deliberate: a migration must not launder the loop-closure signals v3 exists to create.
- Prints a summary block naming logs touched, files changed, and files skipped.
- **`--commit` is opt-in and refuses on a dirty index.** A migration touching 129
  files across **7 separate git repos** is a lot of unrequested writes, so it
  takes a flag; and with a dirty index there is no way to produce a commit
  containing only the migration, so that is a hard refusal rather than a warning.
  Each log commits separately in its own repo via `quest commit`
  ([[QST-e6g6t--quest-commit-and-the-realm-01-designated-committer]]) with a migration message:
  `quest(family): migrate — rename status completed→done (7 files)`. This is the
  first command that writes to multiple repositories in one invocation.

### Alternatives

| Option | Verdict | Reason |
|--------|---------|--------|
| `quest migrate` with three verbs | ✅ Chosen | One tool, four known jobs, and more on every schema change |
| `sed`/`ruby -pi -e` documented in the plan | ❌ | **Corrupts prose** — verified against this corpus |
| A one-off script per migration | ❌ | Three scripts now, one per schema change forever, none with `--dry-run` |
| Auto-migrate on load | ❌ | Silent mutation of files the user did not ask to touch; also unsafe across a Syncthing fleet mid-sync |
| A general migration framework (versioned steps, up/down) | ❌ | Over-built for a tool whose data is plain Markdown in git. Long-run this command earns its keep maybe twice a year; 90 lines clears that bar, a framework would not. |
| A `--move-field` verb | ❌ | Moving a field between schemas changes no quest file. The check it would perform is `quest validate` under `strict: true`. |
| Auto-commit by default | ❌ | Writes to 7 repos without being asked |

## Acceptance Criteria

- [ ] `--backfill status_changed=created` fills only files missing the field, and is idempotent
- [ ] `--rename-value status:completed=done` rewrites the frontmatter value only
- [ ] The same run leaves the word "completed" untouched in bodies and in `description:`
- [ ] `--commit` is opt-in and refuses outright on a dirty index
- [ ] `--commit` produces one commit per log, in that log's own repo
- [ ] `--dry-run` prints a per-file diff and writes nothing
- [ ] Migrations honor `--in` (repeatable), `-A` and `--root`
- [ ] A no-op migration changes no file mtimes
- [ ] `modified` and `status_changed` are not bumped by any migration
- [ ] A summary names logs touched, files changed and files skipped
- [ ] Tests cover: absent field, present field, prose collision, multi-log scoping

## Log

- 2026-08-21: moved from build-order #15 to **#2**. It was scheduled twelve items behind the quest that renames `status: completed`, and behind [[QST-3h09k--status-changed-frontmatter-field-and-reusable-backfill]], whose acceptance criteria name `quest migrate --backfill` outright — so every migration it exists to perform was scheduled before the tool. Its `blocked_by` (`QST-mjuau` alone) always said #2.
- 2026-08-19: captured. Split out of [[QST-3h09k--status-changed-frontmatter-field-and-reusable-backfill]] once v3 accumulated three corpus migrations rather than one, and once the prose-collision hazard was verified in this log.
