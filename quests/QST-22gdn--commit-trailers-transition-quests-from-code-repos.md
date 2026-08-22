---
id: QST-22gdn
title: Commit trailers transition quests from code repos
description: A fixed Quest commit trailer whose token drives transitions (done, scrap, status=X), applied by a quest-apply-trailers hook script — not a CLI verb.
project: questkit
type: feature
status: todo
priority: high
tags:
  - questkit
  - git
  - hooks
  - agentic
created: 2026-08-22
modified: 2026-08-22
agentic: hitl
aliases:
  - QST-22gdn
blocked_by: []
component:
effort: m
milestone: 0.4.0
related_adrs:
---

## Spec (naming to finalize in-session — agentic: hitl)

Git trailers in code commits drive quest transitions, parsed with
`git interpret-trailers --parse` (never prose regex):

    Quest: QST-x7k2m done            # first terminal status of its log
    Quest: QST-x7k2m scrap           # last terminal status
    Quest: QST-x7k2m status=in-review
    Quest: QST-x7k2m                 # mention only -> ## Log append (CLI-3)

One canonical **fixed key** (`Quest:`); the **token** is the dynamic
part. Verbs map through the target log's schema (done -> first,
scrap -> last terminal status), so schema-overridden vocabularies work
without dynamic key names — keys must be knowable before any log
resolves, and a trailer must parse identically on every device.

**Not a CLI verb** (decided 2026-08-22 — the verb list stays slim): a
standalone console-script entry point `quest-apply-trailers`, joining
quest-format/quest-validate/quest-bump-modified. Callers: a post-commit
hook wired by `quest init --hooks`, and/or the realm-01 timer.
Stateless idempotency: a transition to the current status is a no-op;
## Log appends dedupe on the short sha — no synced state file.

Open, hitl: thematic alias keys (`Fulfills:` = done, `Abandons:` =
scrap) — idiomatic and fun, but every alias is parser + docs surface;
default scan range; unknown-id policy (warn vs error). GIT-3
(prepare-commit-msg suggestion from branch name) follows only after
this ships.

## Acceptance Criteria

- [ ] All four trailer forms parsed via interpret-trailers
- [ ] quest-apply-trailers entry point; idempotent re-runs
- [ ] Hook wiring via init --hooks; timer-callable
- [ ] Human sign-off on final key/alias naming before implementation
- [ ] Tests + docs (new §11 subsection)

## Log

- 2026-08-22: captured from R&D catalog GIT-1, accepted for 0.4.0 (hitl; naming discussion recorded in the review)
