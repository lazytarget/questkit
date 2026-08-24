---
id: QST-22gdn
title: Commit trailers transition quests from code repos
description: A fixed Quest commit trailer whose token is the literal status name, applied by a quest-apply-trailers hook script wired via quest init --hooks.
project: questkit
type: feature
status: done
priority: high
tags:
  - questkit
  - git
  - hooks
  - agentic
created: 2026-08-22
status_changed: 2026-08-24
modified: 2026-08-24
agentic: hitl
aliases:
  - QST-22gdn
blocked_by: []
component:
effort: m
milestone: 0.4.0
related_adrs:
---

## Spec (naming decided 2026-08-22 — agentic: hitl)

Git trailers in code commits drive quest transitions, parsed with
`git interpret-trailers --parse` (never prose regex):

    Quest: QST-x7k2m done            # token = the literal status name
    Quest: QST-x7k2m scrapped
    Quest: QST-x7k2m                 # mention only -> ## Log append (CLI-3)

One canonical **fixed key** (`Quest:`) — keys must be knowable before any
log resolves, and a trailer must parse identically on every device. The
**token is the exact status value** written to the quest, validated
against the target log's declared statuses: a log overriding its
vocabulary writes its own words (`Quest: QST-x shipped`,
`Quest: QST-x abandoned`). No verb mapping, no `status=X` form, no
thematic alias keys — what the trailer says is what the frontmatter gets.

**Not a CLI verb** (decided 2026-08-22 — the verb list stays slim): a
standalone console-script entry point `quest-apply-trailers`, joining
quest-format/quest-validate/quest-bump-modified. Callers: a post-commit
hook wired by `quest init --hooks`, and/or the realm-01 timer.
Stateless idempotency: a transition to the current status is a no-op;
## Log appends dedupe on the short sha — no synced state file.

Open, hitl: default scan range; policy for an unknown id or an
out-of-vocabulary status token (warn vs error). GIT-3
(prepare-commit-msg suggestion from branch name) follows only after
this ships.

## Acceptance Criteria

- [ ] Both trailer forms (status token, bare mention) parsed via interpret-trailers
- [ ] Token validated against the target log's declared statuses
- [ ] quest-apply-trailers entry point; idempotent re-runs
- [ ] Hook wiring via init --hooks; timer-callable
- [ ] Tests + docs (new §11 subsection)

## Log

- 2026-08-22: captured from R&D catalog GIT-1, accepted for 0.4.0 (hitl; naming discussion recorded in the review)
- 2026-08-22: naming decided — fixed `Quest:` key, token is the literal status name (schema-overridden vocabularies write their own words); thematic aliases and `status=X` form rejected; `quest-apply-trailers` via `quest init --hooks` confirmed.
- 2026-08-24: Implemented for questkit v4 (milestone 0.4.0), TDD, full suite green.
