---
id: QST-x4zw2
title: Publish questkit remote package registry and tagged releases
project: questkit
type: epic
status: draft
priority: medium
tags:
  - questkit
  - release
  - infra
created: 2026-08-22
modified: 2026-08-22
agentic:
aliases:
  - QST-x4zw2
blocked_by: []
component:
milestone: 0.9.0
related_adrs:
---

## Notes (draft)

Give questkit a real release story. Scope to converge during planning:

- A git remote. Candidate: the self-hosted **Gitea** (exists, has an
  Actions runner) rather than GitHub — keeps the Realm private-first.
- Tagged releases: retro-tags for 0.1.0/0.2.0 (flagged in plan v3 §2),
  then a tag per release going forward.
- Package publishing: Gitea ships a **PyPI-compatible package registry**,
  so `pip install --index-url https://<gitea>/api/packages/<owner>/pypi/simple questkit`
  works without public PyPI. Public PyPI only if/when it goes OSS.
- Hook pins become human-readable (`rev: v0.4.0` instead of a sha) and
  the pin bump folds into the release ritual — revisit GIT-4 / QST-d8nu7
  here.
- Unblocks CI (CI-1) on the Gitea runner.

From R&D catalog REL-4. Draft by request; deferred to milestone 0.9.0.

## Log

- 2026-08-22: captured from R&D catalog REL-4 (draft, milestone 0.9.0)
