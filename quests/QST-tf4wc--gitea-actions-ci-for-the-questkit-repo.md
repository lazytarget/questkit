---
id: QST-tf4wc
title: Gitea Actions CI for the questkit repo
project: questkit
type: chore
status: draft
priority: medium
tags:
  - questkit
  - ci
  - infra
created: 2026-08-22
modified: 2026-08-22
agentic:
aliases:
  - QST-tf4wc
blocked_by: []
component:
milestone: 0.9.0
related_adrs:
---

## Notes (draft)

`.gitea/workflows/` CI on the self-hosted Gitea (Actions runner
exists; the `gitea` remote is already configured on this repo):

- on push/PR: pytest matrix (3.11–3.13 — `requires-python` promises
  >=3.11 but only 3.12 is ever exercised locally), ruff, pre-commit
- on tag: build + publish to Gitea's PyPI-compatible package registry
  + changelog assembly via `--format md` (QST-f6otu) / the release
  helper (QST-cv23q)
- value: makes "test before you commit, every time" structural rather
  than disciplinary, and guarantees any sha a consuming repo pins its
  hooks to has passed its own tests

The test/lint half is runnable today (remote exists); the publish half
waits for the registry decision in QST-x4zw2 — hence 0.9.0-adjacent.

From R&D catalog CI-1.

## Log

- 2026-08-22: captured from R&D catalog CI-1 (draft, milestone 0.9.0)
