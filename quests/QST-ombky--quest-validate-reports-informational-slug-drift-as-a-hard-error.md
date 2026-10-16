---
id: QST-ombky
title: quest validate reports informational slug drift as a hard error
description: check_slug_drift documents itself as informational and is excluded from the pre-commit hook, but validate_cmd counts it toward the exit code.
project: questkit
type: bug
status: done
priority: medium
tags:
  - questkit
  - cli
created: 2026-08-19
status_changed: 2026-08-20
modified: 2026-08-20
agentic: afk
aliases:
  - QST-ombky
blocked_by: []
effort: xs
milestone: 0.3.0
tier: spark
---

## Description

`schema.check_slug_drift`'s own docstring says it is *"informational, not part of
`validate_quest()`'s hard rules, and deliberately excluded from the pre-commit
hook"* — because filenames are immutable by design, so drift after a title edit is
**expected**, not a defect.

But `commands/validate_cmd.py` merges its output into the same `errors` list,
prints it with an `error:` prefix, and counts it toward `total_errors`, which
drives `return 1`. The code contradicts its own documentation.

Consequence: a supported operation (`quest set <id> title=...`) makes
`quest validate` exit 1 **forever**. questkit's own log has been in that state
since 2026-08-16 because of [[QST-fmk0p--resolving-questkit-log-in-specified-path-via]], so the log never reports clean. That in
turn means:

- `quest validate --report` ([[QST-e6g6t--quest-commit-and-the-designated-committer]]) would write a permanent `_validation.md`
  for a non-problem, on a surface built specifically so real problems get noticed;
- it trains the reader to ignore validate output, which is the failure mode the
  report file exists to prevent.

## Spec

Separate **notes** from **errors** throughout.

1. `check_slug_drift` output prints under a `note:` prefix, visually distinct from `error:`.
2. Notes do not count toward `total_errors` and do not affect the exit code.
3. The summary line reports both: `8 quest(s) checked, 0 error(s), 1 note(s)`.
4. `--notes` / `--no-notes` toggles display; the exit code is unaffected either way.
5. `quest validate --report FILE` ([[QST-e6g6t--quest-commit-and-the-designated-committer]]) writes errors and notes in separate
   sections. A log whose only findings are notes counts as **clean** — the report
   file is deleted.

Any future informational check (project drift heuristics, orphan detection) uses
the same channel, so this is a structure, not a special case for one rule.

## Acceptance Criteria

- [x] Slug drift prints as `note:`, not `error:`
- [x] A log whose only finding is drift exits 0
- [x] A log with a real error still exits 1, and still prints its notes
- [x] The summary line counts errors and notes separately
- [x] `--report` omits the file when only notes exist
- [x] questkit's own log validates clean
- [x] The pre-commit hook's behavior is unchanged (it already excludes drift)

## Log

- 2026-08-21: implemented (batch B0). Sequenced first in the batch rather than treated as independent: "the corpus validates clean" is the gate every later batch checks itself against, and questkit's own log was the only thing failing it — on exactly the two retitles this check was documented to tolerate. `--notes/--no-notes` uses `argparse.BooleanOptionalAction` so one declaration gives both. A fixture lesson came out of it too: `write_quest` now defaults its slug from the title, because a test about something else should not have to know that passing `slug="broken"` also produces a drift note — which is precisely how one of these tests first miscounted.
- 2026-08-19: captured. Found while grooming [[QST-fmk0p--resolving-questkit-log-in-specified-path-via]] — the retitle that caused the drift is exactly the supported operation the check was documented to tolerate.
