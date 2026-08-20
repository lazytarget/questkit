---
id: QST-ombky
title: quest validate reports informational slug drift as a hard error
description: check_slug_drift documents itself as informational and is excluded from the pre-commit hook, but validate_cmd counts it toward the exit code.
created: 2026-08-19
status_changed: 2026-08-19
modified: 2026-08-20
type: bug
tier: spark
status: todo
priority: medium
effort: xs
milestone: 0.3.0
project: questkit
tags:
  - questkit
  - cli
blocked_by: []
aliases:
  - QST-ombky
agentic: afk
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

- `quest validate --report` ([[QST-e6g6t--quest-commit-and-the-realm-01-designated-committer]]) would write a permanent `_validation.md`
  for a non-problem, on a surface built specifically so real problems get noticed;
- it trains the reader to ignore validate output, which is the failure mode the
  report file exists to prevent.

## Spec

Separate **notes** from **errors** throughout.

1. `check_slug_drift` output prints under a `note:` prefix, visually distinct from `error:`.
2. Notes do not count toward `total_errors` and do not affect the exit code.
3. The summary line reports both: `8 quest(s) checked, 0 error(s), 1 note(s)`.
4. `--notes` / `--no-notes` toggles display; the exit code is unaffected either way.
5. `quest validate --report FILE` ([[QST-e6g6t--quest-commit-and-the-realm-01-designated-committer]]) writes errors and notes in separate
   sections. A log whose only findings are notes counts as **clean** — the report
   file is deleted.

Any future informational check (project drift heuristics, orphan detection) uses
the same channel, so this is a structure, not a special case for one rule.

## Acceptance Criteria

- [ ] Slug drift prints as `note:`, not `error:`
- [ ] A log whose only finding is drift exits 0
- [ ] A log with a real error still exits 1, and still prints its notes
- [ ] The summary line counts errors and notes separately
- [ ] `--report` omits the file when only notes exist
- [ ] questkit's own log validates clean
- [ ] The pre-commit hook's behavior is unchanged (it already excludes drift)

## Log

- 2026-08-19: captured. Found while grooming [[QST-fmk0p--resolving-questkit-log-in-specified-path-via]] — the retitle that caused the drift is exactly the supported operation the check was documented to tolerate.
