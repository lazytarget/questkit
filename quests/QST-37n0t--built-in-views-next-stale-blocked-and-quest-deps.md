---
id: QST-37n0t
title: Built-in views (next, stale, blocked) and quest deps
description: Ship the loop-closing views as schema-defined prefills exposed as subcommands, plus a real dependency-graph walk.
created: 2026-08-19
status_changed: 2026-08-19
modified: 2026-08-20
type: feature
tier: brief
status: todo
priority: high
effort: m
project: questkit
tags:
  - questkit
  - cli
  - dx
blocked_by:
  - QST-b9lqo
aliases:
  - QST-37n0t
agentic: afk
---

## Description

The views are the point of v3 — the commands that answer *what should I do* and
*what is rotting*. With computed fields in place ([[QST-b9lqo--computed-fields-and-comparison-operators-for-where]]) they are pure
prefills over `quest list`, which is what they should have been all along.

`quest deps` is the exception: a graph walk, not a filter, so it stays a real
command.

## Spec

### Approach

**Views are defined in the schema file** ([[QST-j68u5--schema-engine-field-order-defaults-macros-typed-fields-strict-writes]]), overridable per log, and
exposed as **bare subcommands**:

```yaml
views:
  default: { where: ["status=todo,in-progress"] }
  next:    { where: ["blocked=false"], sort: "priority:asc,effort:asc,idle:desc", limit: 1 }
  stale:   { where: ["idle>14"], sort: "idle:desc" }
  blocked: { where: ["blocked=true"], sort: "blocks:desc" }
```

**`views.default` is the one that pays for the mechanism.** `quest list`'s
implicit status filter is hardcoded today (`todo, in-progress, blocked`) and
cannot survive a log that overrides `statuses:` — a `household` schema with
`waiting`/`doing` would silently list nothing. Moving it into the view layer
removes the last hardcoded status list rather than replacing it with another
config key, and it means a schema's vocabulary and its default listing are
declared in the same file.

Note `blocked` is gone from the default filter: [[QST-j68u5--schema-engine-field-order-defaults-macros-typed-fields-strict-writes]] removes
it from the core status enum, and derived-blocked quests stay visible via the
`todo [blocked]` marking in [[QST-b9lqo--computed-fields-and-comparison-operators-for-where]] instead of a status
value nobody maintains by hand.

- `quest next`, `quest stale`, `quest blocked` — real argparse subcommands that
  prefill `list`'s arguments and accept every `list` flag on top.
- Config **overrides a built-in's definition, never its command name**. argparse
  is built before any log resolves, so config cannot add subcommands — and a CLI
  whose command list depends on cwd is a debugging nightmare.
- User-defined views that are not built-ins are reachable as
  `quest list --view NAME`.
- Every field a view sets is a **default**, not a lock. `--limit N` overrides,
  per the two-layer rule in [[QST-iqwjm--multi-log-query-ux-all-logs-repeatable-in-and-root-per-log-grouping-summary-block]].

Views living in the schema rather than the log config matters once four logs share
`schema: development`: they want the same ranking, because that is what makes them
the same *kind* of work. A per-log `views:` block stays available for the genuinely
unique case.

**`quest deps <id>`** walks the dependency graph. `blocked_by` is many-to-many, so
this is a **DAG, not a tree** — render it strictly and you either duplicate nodes
or silently drop edges. Mark revisited nodes explicitly. `--blocks` walks the
reverse direction. With [[QST-yiep7--qualified-cross-log-references-in-blocked-by]] it traverses qualified refs and labels each
node's log.

### Rejected

| Candidate | Verdict | Reason |
|-----------|---------|--------|
| `quest backlog` / `quest drafts` | ❌ | Exactly `--where status=draft`. Naming one status invites a subcommand per status, which **cannot survive custom schemas**. The real grooming query is `quest stale --where status=draft`. |
| `quest archive` / `quest scrapped` | ❌ | Same. And `archive` is reserved for the eventual *mutation* — `career-transition` ends someday and its quests should not stay in `-A` forever. |
| `quest active` | ❌ | Already the default filter; it just has no name. |
| `quest status` | ❌ | Disqualified — `quest status`, `quest set X status=`, and `quest schema quest status` would mean three different things. |
| `--first` on `next` | ❌ | `--limit 1` is the view's default; a synonym buys nothing. |
| `quest tree` | ❌ | It is a DAG. `deps` is accurate. |

**`--any-status` was also rejected**: the fix for an invisible default filter is to
print it ([[QST-iqwjm--multi-log-query-ux-all-logs-repeatable-in-and-root-per-log-grouping-summary-block]]'s summary block), not to add a flag.

## Acceptance Criteria

- [ ] `views.default` drives `quest list`'s implicit filter, and a schema can override it
- [ ] A log overriding `statuses:` with its own `views.default` lists correctly
- [ ] `quest next` returns one quest and never one with an open dependency
- [ ] `quest next` accepts `--in`, `--where`, `--sort`, `--limit` on top of the view
- [ ] `quest stale` ranks by `idle` and its threshold is configurable
- [ ] `quest blocked` lists quests with an open dependency, ranked by `blocks`
- [ ] A log's `views:` override changes a built-in's definition, not its name
- [ ] A user-defined view is reachable via `quest list --view NAME`
- [ ] Views resolve from the named schema, with per-log override
- [ ] `quest deps <id>` renders the graph and marks revisited nodes
- [ ] `quest deps <id> --blocks` walks the reverse direction
- [ ] Under `-A`, views group per log ([[QST-iqwjm--multi-log-query-ux-all-logs-repeatable-in-and-root-per-log-grouping-summary-block]]) and each log uses its own definition

## Log

- 2026-08-19: captured. `quest blocked` was not in the original list — the corpus check that added it found 0 uses of `status: blocked` against 8 genuinely blocked quests.
