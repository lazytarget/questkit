---
id: QST-tf4wc
title: GitHub Actions CI for the questkit repo
project: questkit
type: chore
status: draft
priority: medium
tags:
  - questkit
  - ci
  - infra
created: 2026-08-22
modified: 2026-10-16
agentic:
aliases:
  - QST-tf4wc
blocked_by: []
component:
milestone: 0.4.0
related_adrs:
---

## Notes (draft)

`.github/workflows/` CI for the questkit repo, which is going public on
GitHub (QST-x4zw2). The self-hosted Gitea stays a remote, but the workflows
are written for GitHub Actions so they run where the public repo lives:

- on push/PR: pytest matrix (3.11–3.13 — `requires-python` promises
  >=3.11 but only 3.12 is ever exercised locally), ruff, mypy, pre-commit
- on tag: build, then publish to Gitea's PyPI-compatible package registry
  for now; GitHub / PyPI publishing waits for 0.9.0, when the setup is more
  mature. Changelog assembly via `--format md` (QST-f6otu) / the release
  helper (QST-cv23q)
- value: makes "test before you commit, every time" structural rather
  than disciplinary, and guarantees any sha a consuming repo pins its
  hooks to has passed its own tests

From R&D catalog CI-1.

## Acceptance Criteria

- [ ] `.github/workflows/` runs pytest (3.11–3.13), ruff, mypy and pre-commit on every push and pull request
- [ ] No workflow lives under `.gitea/workflows/`
- [ ] A tag push builds the package and publishes it to the Gitea PyPI registry
- [ ] GitHub / PyPI publishing is explicitly out of scope until 0.9.0

## Log

- 2026-08-22: captured from R&D catalog CI-1 (draft, milestone 0.9.0)
- 2026-10-16: Bumped 0.9.0 -> 0.4.0; workflows live in .github/workflows (repo is going public on GitHub); package registry is Gitea PyPI for now, GitHub/PyPI at 0.9.0.

