---
id: QST-tf4wc
title: GitHub Actions CI for the questkit repo
description: "CI for the questkit repo in .github/workflows (tests on 3.11-3.13, lint, types, quest log) and one publish workflow per registry, Gitea and PyPI, each guarded to its own host."
project: questkit
type: chore
status: in-progress
priority: medium
tags:
  - questkit
  - ci
  - infra
created: 2026-08-22
status_changed: 2026-10-16
modified: 2026-10-21
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
- on tag: build, then publish to two registries, each from its own workflow so
  they never share credentials: `publish-gitea.yml` to Gitea's PyPI-compatible
  registry (Gitea's runner) and `publish-pypi.yml` to PyPI (GitHub's runner).
  Both can also be started by hand from the Actions tab: Gitea publishes a
  `.devN` version, PyPI builds and checks only unless started from a tag with
  "publish" ticked. PyPI moved into the 0.4.0 scope on 2026-10-21; it was first
  deferred to 0.9.0. Changelog assembly via `--format md` (QST-f6otu) / the
  release helper (QST-cv23q)
- value: makes "test before you commit, every time" structural rather
  than disciplinary, and guarantees any sha a consuming repo pins its
  hooks to has passed its own tests

From R&D catalog CI-1.

## Acceptance Criteria

- [x] `.github/workflows/` runs pytest (3.11–3.13), ruff, mypy and pre-commit on every push and pull request
- [x] No workflow lives under `.gitea/workflows/`
- [x] Two publish workflows, `publish-gitea.yml` and `publish-pypi.yml`, each guarded to run only on its own host, so neither runner publishes to the other's registry
- [x] Both workflows can be started by hand (Run workflow); a manual run never publishes a release version by accident
- [ ] A tag push builds the package and publishes it to the Gitea PyPI registry
- [ ] A tag push builds the package and publishes it to PyPI
- [ ] A manual run of each workflow succeeds once the files are on the default branch (Gitea: `.devN` publish, GitHub: build and check)

## Log

- 2026-08-22: captured from R&D catalog CI-1 (draft, milestone 0.9.0)
- 2026-10-16: Bumped 0.9.0 -> 0.4.0; workflows live in .github/workflows (repo is going public on GitHub); package registry is Gitea PyPI for now, GitHub/PyPI at 0.9.0.
- 2026-10-16: Workflows written (ci.yml, publish.yml) and checked locally on Python 3.11, 3.12 and 3.13 from a copy with no private directory tree; not yet run on a real GitHub runner. Repo made self-contained by vendoring schemas/development.yaml.
- 2026-10-21: Scope widened: PyPI moved into 0.4.0. Replaced publish.yml with publish-gitea.yml and added publish-pypi.yml, both startable by hand; guarded so neither runner publishes to the other's registry; tests and actionlint pass.

