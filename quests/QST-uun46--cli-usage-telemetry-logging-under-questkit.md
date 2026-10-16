---
id: QST-uun46
title: CLI usage telemetry logging under ~/.questkit/
project: questkit
type: feature
status: draft
priority: low
tags:
  - questkit
  - cli
  - telemetry
  - dx
created: 2026-09-03
modified: 2026-10-16
agentic:
aliases:
  - QST-uun46
blocked_by: []
component:
effort: m
milestone:
related_adrs:
---

## Spec

Local, opt-out CLI usage telemetry: every `quest` invocation appends one
JSONL record to `~/.questkit/telemetry/` (path TBD, never synced/committed —
this is local-machine-only, not quest-log content). Never transmitted
anywhere; purely for the user to introspect their own usage later.

Each record captures, at minimum:

- timestamp
- subcommand invoked (`new`, `list`, `done`, ...)
- flag/option *names* used, not their values — never log title, body,
  description, or other free-text field content
- questkit version
- cwd at invocation
- which log was targeted, and whether that resolution was explicit
  (`--in`/`--project`) or implicit (cwd walk up to a log root)
- exit status (success/error)

A query surface reports on the accumulated log, e.g. `quest usage`
(name/placement TBD — not the same thing as REP-1's `quest stats`, which
is quest*-content* distribution, not CLI-invocation frequency): command
frequency, most-used flags per command, explicit-vs-implicit log
resolution ratio.

### Open question: does this even see most quest creation?

AI agents (and humans) can write/edit `QST-*.md` files directly, bypassing
the CLI entirely — this telemetry only sees invocations of the `quest`
binary. Before or alongside building this, worth checking how much quest
activity in practice actually goes through the CLI vs direct file edits by
agents. If direct-edit is common, CLI telemetry alone gives a skewed
picture of "how questkit is used."

Recommend for v1: accept the gap and document it explicitly (telemetry
measures CLI usage, not quest-log activity) rather than trying to detect
non-CLI writes up front. If the gap turns out to matter, a future
`quest doctor`-style check correlating git history (files touched) against
recorded CLI events could close it — not in scope here.

## Acceptance Criteria

- [ ] Every `quest` invocation appends one JSONL record under
      `~/.questkit/telemetry/`
- [ ] Record includes: timestamp, subcommand, flag names used, questkit
      version, cwd, resolved log target + explicit/implicit
- [ ] No quest content (titles, bodies, field values) is ever logged —
      flag/option names only
- [ ] Opt-out via env var, documented
- [ ] A `quest usage`-shaped command summarizes: command frequency,
      most-used flags per command, explicit vs implicit log resolution
- [ ] Docs note the CLI-only visibility gap (direct Markdown edits by
      agents/humans aren't captured) and point at the open question above

## Log

- 2026-09-03: captured from user request (not yet in R&D ideas catalog)

