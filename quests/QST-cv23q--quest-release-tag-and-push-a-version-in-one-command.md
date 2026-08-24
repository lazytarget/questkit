---
id: QST-cv23q
title: "quest release: tag and push a version in one command"
project: questkit
type: feature
status: done
priority: medium
tags:
  - questkit
  - cli
  - release
created: 2026-08-22
status_changed: 2026-08-24
modified: 2026-08-24
agentic: hitl
aliases:
  - QST-cv23q
blocked_by:
  - QST-f6otu
effort: s
milestone: 0.4.0
tier: spark
description: "A scripts/release.py ritual: verify milestone completeness, assemble the CHANGELOG.md section via quest list --format md, confirm pyproject/installed version agreement, then tag and push."
---

## Notes (draft)

Cutting `v0.3.0` today was five manual steps, each easy to get wrong or skip
under `--no-verify`/scoping pressure: bump `pyproject.toml`, reinstall the
editable venv so `questkit.__version__` isn't stale against it (a real bug
found and fixed this same release — see [[QST-bmzl2--questkit-v3-loop-closure-multi-log-ux-and-agent-handoff]]'s
post-close addendum), update `CHANGELOG.md`, then `git tag -a vX.Y.Z -m ...`
and `git push <remote> vX.Y.Z` by hand.

Scope to converge during grooming — a `quest release` (or similar) command,
or a standalone script under `scripts/`, that at minimum:

- Confirms `pyproject.toml`'s `version` and `questkit.__version__` (installed
  metadata) actually agree before doing anything — the exact drift this
  session hit.
- Creates the annotated, signed tag (`vX.Y.Z`, message pulled from that
  version's `CHANGELOG.md` section) and pushes it, so tagging is one
  command instead of a hand-typed `git tag -a ... -m "..."` copied together
  from memory each time.
- Refuses on a dirty working tree or an already-existing tag, the same way
  `quest commit`/`quest migrate --commit` refuse rather than guess.

Related to [[QST-x4zw2--publish-questkit-remote-package-registry-and-tagged-releases]]
(the broader release-story epic, `milestone: 0.9.0`) but narrower and not
blocked by it — that epic is about *where* releases go (a package registry);
this is about not hand-typing the tag step every time, which is useful on
its own well before a registry exists.

### Converged with the R&D review (2026-08-22 — this is R&D REL-2)

Decision: a script under `scripts/` in this repo, **not** a CLI verb —
release conventions differ too much across teams for the core to own one.
Scope grows from "tag and push" to the full ritual:

- verify every `milestone: <version>` quest is terminal before doing
  anything
- assemble the `CHANGELOG.md` section from
  `quest list --where "milestone=X;status=done,scrapped" --format md`
  ([[QST-f6otu--markdown-output-format-for-quest-list-and-views]] — hence
  the new `blocked_by`), grouped release-drafter-style by `type`
  (feature → Added, bug → Fixed, chore/task → Changed)
- then the version-agreement / tag / push steps already listed above
- the same rendered body doubles as the Gitea release body once
  publishing lands (QST-x4zw2)

`agentic: hitl` — the exact format and ritual to finalize in-session.

## Log

- 2026-08-22: captured after manually tagging `v0.3.0` by hand.
- 2026-08-22: merged R&D REL-2 scope (changelog assembly via --format md, release-drafter type grouping); blocked_by QST-f6otu; agentic set to hitl.
- 2026-08-24: Implemented for questkit v4 (milestone 0.4.0), TDD, full suite green.
