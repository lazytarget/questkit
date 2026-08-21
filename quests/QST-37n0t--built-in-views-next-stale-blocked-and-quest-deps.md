---
id: QST-37n0t
title: Built-in views (next, stale, blocked) and quest deps
description: Ship the loop-closing views as schema-defined prefills exposed as subcommands, plus a real dependency-graph walk.
project: questkit
type: feature
status: done
priority: high
tags:
  - questkit
  - cli
  - dx
created: 2026-08-19
status_changed: 2026-08-20
modified: 2026-08-20
agentic: afk
aliases:
  - QST-37n0t
blocked_by:
  - QST-b9lqo
effort: m
milestone: 0.3.0
tier: brief
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

**Two prerequisites in [[QST-j68u5--schema-engine-field-order-defaults-macros-typed-fields-strict-writes]] rule 10, without which `next` is
broken as written.** `list_cmd._apply_sort` sorts lexicographically, so
`priority:asc` today returns `critical, deferred, high, low, medium` — a
`deferred` quest ranks second. And `sort_expr.partition(":")` silently drops
every key after the first, so `effort` is never consulted at all. Ordered
vocabularies and multi-key sort are not polish for this view; they are what make
its definition mean what it reads like.

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

- [x] `views.default` drives `quest list`'s implicit filter, and a schema can override it
- [x] A log overriding `statuses:` with its own `views.default` lists correctly
- [x] `quest next` ranks by the schema's declared priority/effort order, not alphabetically
- [x] `quest next` honors every key in a multi-key `sort:`
- [x] `quest next` returns one quest and never one with an open dependency
- [x] `quest next` accepts `--in`, `--where`, `--sort`, `--limit` on top of the view
- [x] `quest stale` ranks by `idle` and its threshold is configurable
- [x] `quest blocked` lists quests with an open dependency, ranked by `blocks`
- [x] A log's `views:` override changes a built-in's definition, not its name
- [x] A user-defined view is reachable via `quest list --view NAME`
- [x] Views resolve from the named schema, with per-log override
- [x] `quest deps <id>` renders the graph and marks revisited nodes
- [x] `quest deps <id> --blocks` walks the reverse direction
- [x] Under `-A`, views group per log ([[QST-iqwjm--multi-log-query-ux-all-logs-repeatable-in-and-root-per-log-grouping-summary-block]]) and each log uses its own definition

## Log

- 2026-08-20: implemented. `schema.View`/`schema.DEFAULT_VIEWS` added, resolved per log in `SchemaConfig.load` with full-replacement semantics (matching `readiness:`). `list_cmd.run` resolves `args.view` (default `"default"`), builds a per-log `view_wheres_by_log` map (each row filtered against *its own* log's view, not the first resolved log's — an explicit `--where` on a field drops that field from every log's view clause first), then `_apply_view_sort`/`_apply_view_limits` apply each log's own `sort`/`limit` independently when the caller didn't override them with `--sort`/`--limit`. `cli._add_list_options` factors the full `list` flag set so `next`/`stale`/`blocked` are the same parser with `set_defaults(view=...)` — an explicit `--view` on the command line still wins, since argparse always prefers a given value over any default. `quest deps` is a new command (`commands/deps_cmd.py`): sweeps every log in scope by default (needed to traverse qualified cross-log refs from [[QST-yiep7--qualified-cross-log-references-in-blocked-by]]), builds a global adjacency map, and renders depth-first with a global `visited` set so a diamond dependency prints the shared ancestor twice but expands its own children only once, marked `(see above)`. 16 new tests in `tests/test_views_and_deps.py`.
- 2026-08-19: captured. `quest blocked` was not in the original list — the corpus check that added it found 0 uses of `status: blocked` against 8 genuinely blocked quests.
