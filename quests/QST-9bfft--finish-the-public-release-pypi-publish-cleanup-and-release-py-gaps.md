---
id: QST-9bfft
title: "Finish the public release: PyPI publish, cleanup and release.py gaps"
description: "What was left when v0.4.0 shipped to Gitea and GitHub: the PyPI publish blocked on the API token, the realm-prod-01 re-clone, deleting the backup repository, and two release.py gaps."
project: questkit
type: chore
status: todo
priority: medium
tags:
  - questkit
  - release
created: 2026-10-21
modified: 2026-10-21
agentic:
aliases:
  - QST-9bfft
blocked_by: []
component:
milestone:
related_adrs:
---

## Description

questkit v0.4.0 was tagged and published to the Gitea registry while PyPI was
blocked: the PyPI account was not reachable, so the API token could not be
created. QST-x4zw2 (the public release) and QST-tf4wc (CI and publish workflows)
closed with the release. This quest holds what they could not finish.

## Spec

**PyPI.** The tag `v0.4.0` is on GitHub, so its `Publish to PyPI` run is waiting for
approval in the `pypi` environment (GitHub run 39580254037: `build` passed, `publish`
waiting). The environment has no `PYPI_API_TOKEN` yet.
Once the PyPI account is reachable:

1. Create an account-wide token (a project-scoped token needs the project to exist
   first, from memory) and add it as the `PYPI_API_TOKEN` secret of the `pypi`
   environment.
2. Publish 0.4.0: approve the waiting run, or start `Publish to PyPI` again from the
   tag `v0.4.0` with "publish" ticked. `--skip-existing` makes a re-run safe.
3. Check `pip install questkit==0.4.0` from PyPI, then replace the token with one
   scoped to the `questkit` project.

**Cleanup.**

- `realm-prod-01` still holds the old history. It is not in the Syncthing folder, so
  it can be re-cloned: move the old checkout aside, then `make apply-repos
  REPO=questkit`.
- A device that applied `repos.yaml` while the GitHub remote was still called
  `lazytarget` keeps that remote; `git remote remove lazytarget` is safe.
- Once the package link is confirmed, delete the Gitea repository
  `peter/questkit---backup` and the local `questkit---backup` checkout. The bundle
  in `06-archive` stays.

**scripts/release.py.** It has never run end to end, and the 0.4.0 release found two
gaps, so 0.4.0 was cut by hand with the script's own functions:

- It writes `CHANGELOG.md` and then tags `HEAD`, so the tag does not contain its own
  changelog entry and the file is left uncommitted.
- It pushes the tag to one remote (`--remote`, default `origin`, which this repository
  does not have). With two remotes and no sync, a release needs a second push.

## Acceptance Criteria

- [x] The `v0.4.0` tag published to the Gitea registry (Gitea run 720) and `questkit==0.4.0` installs from it with pip
- [ ] `PYPI_API_TOKEN` added to the `pypi` environment
- [ ] `questkit 0.4.0` is on PyPI and installs from it
- [ ] The token is replaced by one scoped to the `questkit` project
- [ ] `realm-prod-01` re-cloned and the old `lazytarget` remote removed wherever it exists
- [ ] `peter/questkit---backup` and the local `questkit---backup` checkout deleted
- [ ] `scripts/release.py` commits the changelog before it tags, and can push the tag to several remotes

## Log

- 2026-10-21: captured when v0.4.0 shipped. Moved here from QST-x4zw2 and QST-tf4wc: the PyPI publish (blocked on the API token), the realm-prod-01 re-clone, deleting the backup repository, and the release.py gaps found while cutting the release.
- 2026-10-21: v0.4.0 published to the Gitea registry by the tag push (run 720) and verified by installing questkit==0.4.0. On GitHub the tag's PyPI run is waiting at the pypi environment; PyPI still has no questkit project.

