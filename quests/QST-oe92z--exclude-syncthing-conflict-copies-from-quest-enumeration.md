---
id: QST-oe92z
title: Exclude Syncthing conflict copies from quest enumeration
description: Conflict copies match the quest pattern and find_by_id globs — exclude them from enumeration and commit tracking, warn on presence, fix docs §10.
project: questkit
type: bug
status: done
priority: high
tags:
  - questkit
  - syncthing
  - validation
created: 2026-08-22
status_changed: 2026-08-24
modified: 2026-10-16
agentic: afk
aliases:
  - QST-oe92z
blocked_by: []
component:
effort: s
milestone: 0.4.0
related_adrs:
---

## Repro

    python3 -c "import fnmatch; print(fnmatch.fnmatch('QST-x7k2m--fix.sync-conflict-20260814-120000-ABCDEF.md', 'QST-*.md'))"
    # True — matches config.pattern (list_cmd.py:322) and find_by_id's
    # '{id}*.md' glob (quest.py:234); no exclusion anywhere in src/

Syncthing inserts `.sync-conflict-...` *before* the extension, so a
conflict copy is enumerated as a quest: duplicate id in `list`,
inflated counts in `logs`, passes `validate` (id prefix and self-alias
both match), and — worst — matches the log's `pattern` and therefore
`quest commit`'s default `tracked:` set, so the unattended realm-prod-01
committer would commit conflict litter into history. Id resolution
survives today only because `.md` happens to sort before
`.sync-conflict-...`. Contradicts docs §10's claim that a conflict
copy "will not be recognized as a quest at all".

## Spec

Decision (2026-08-22): **exclude + surface**.

- Exclude `*.sync-conflict-*` at both enumeration sites and from
  `quest commit`'s tracked expansion.
- Never silent: `list`/`validate` print one stderr line when copies
  exist in the log ("N sync-conflict copies present — resolve by hand").
- Correct docs §10.
- `quest doctor` (QST-whcdp) reports them as its check 2.
- Companion, Realm-side (R&D SYNC-2 — deliberately NOT questkit core):
  a resolver under 99-system using questkit as a library for a
  frontmatter-aware field diff and rule-based merge of a copy against
  its original. Tracked here as a scope item; the code lands
  Realm-side.

## Acceptance Criteria

- [ ] Conflict copies excluded from list/validate/find_by_id and commit tracking
- [ ] Stderr presence warning; regression test with a conflict-named file
- [ ] docs §10 corrected
- [ ] Realm-side resolver: minimal diff+merge script under 99-system
- [ ] Cross-referenced from the doctor quest's check list

## Log

- 2026-08-22: captured from R&D catalog SYNC-1 (verified bug) + SYNC-2 (Realm-side tool), accepted for 0.4.0
- 2026-10-02: hit for real. A Syncthing conflict on QST-nxxk8 (phone offline
  while an agent edited on another device) produced
  `QST-nxxk8--….sync-conflict-20261002-074306-OE7VUMG.md`. `quest validate`
  counted it as a 61st quest and only noted a slug mismatch, with no
  duplicate-id error. Merged by hand. Sibling of QST-f0329's worktree
  duplicates; both should follow one duplicate policy.
- 2026-08-24: Implemented for questkit v4 (milestone 0.4.0), TDD, full suite green.

