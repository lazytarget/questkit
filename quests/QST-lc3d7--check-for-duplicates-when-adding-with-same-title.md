---
id: QST-lc3d7
title: Check for duplicates when adding with same title
description: Warn at capture time when a new quest's title collides with an existing one in the same log, without ever blocking the capture.
project: questkit
type: feature
status: done
priority: low
tags:
  - questkit
  - cli
  - dx
created: 2026-08-16
status_changed: 2026-08-24
modified: 2026-08-24
agentic: afk
aliases:
  - QST-lc3d7
blocked_by: []
effort: xs
milestone: 0.4.0
tier: spark
---

## Description

`quest new` never checks whether it is creating a second quest for something
already captured. In a 129-quest corpus with capture deliberately frictionless
("capture immediately, groom later"), re-capturing the same idea weeks apart is
the expected failure, not an unlikely one.

## Spec

### Approach

On `quest new`, slugify the incoming title and compare against every existing
quest's filename slug in the target log. On a hit, **write the quest anyway** and
print a warning on stderr naming the matches:

```
[warning] similar quest(s) already in this log:
    QST-8hjjk  todo   Allow for --select and --distinct when listing quests
  created anyway as QST-p2m4x — use `quest set QST-p2m4x status=scrapped` if duplicate
```

**Never block, never prompt.** Capture must stay a two-second action; a quest
created in duplicate costs one `quest set`, while a capture that fails costs the
idea. This is deliberately *not* governed by `strict` ([[QST-j68u5--schema-engine-field-order-defaults-macros-typed-fields-strict-writes]]) — strict is
about field names being real, this is about a human having a thought twice.

Matching: exact slug equality plus a cheap token-overlap heuristic (e.g. ≥70% of
title tokens shared, ignoring stopwords). Scoped to the target log only —
cross-log duplicate detection would need the sweep and is not worth it for a
warning.

`--allow-duplicate` suppresses the warning for the intentional case.

### Alternatives

| Option | Verdict | Reason |
|--------|---------|--------|
| Warn, always create | ✅ Chosen | Preserves frictionless capture; the cost of a false negative is one command |
| Error and require `--force` | ❌ | Breaks the capture-in-two-seconds property questkit is built around |
| Interactive prompt | ❌ | questkit is piped into agents |
| Cross-log detection | ❌ | Needs a sweep on every capture, for a warning |

## Acceptance Criteria

- [ ] An exact title repeat warns on stderr and still creates the quest
- [ ] The warning names the matching id, status and title
- [ ] A near-match by token overlap also warns
- [ ] Unrelated titles do not warn
- [ ] `--allow-duplicate` suppresses the warning
- [ ] Exit code is 0 in all of the above — a warning is not a failure
- [ ] Detection is scoped to the target log

## Log

- 2026-08-16: captured
- 2026-08-19: groomed as part of [[QST-bmzl2--questkit-v3-loop-closure-multi-log-ux-and-agent-handoff]]. Deliberately kept outside `strict` — capture must never fail on a judgment call.
- 2026-08-24: Implemented for questkit v4 (milestone 0.4.0), TDD, full suite green.
