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
modified: 2026-10-16
agentic:
aliases:
  - QST-x4zw2
blocked_by: []
component:
milestone: 0.4.0
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

From R&D catalog REL-4. Draft by request; originally deferred to milestone 0.9.0.

### Scope update (2026-10-16)

Pulled into 0.4.0, and widened: questkit goes **public on GitHub**
(`github.com/lazytarget/questkit`). The self-hosted Gitea remote does not go
away; it stays the private-first working remote, and GitHub is the public
mirror. That changes two of the notes above: public PyPI is no longer an
"if/when" (it is in scope), and the Gitea registry is optional rather than
the only registry.

## Acceptance Criteria

- [ ] Audit the Gitea Git repo history for secrets and sensitive data (tokens, hostnames, personal data, Realm-internal paths) before anything is published to GitHub. The Gitea remote continues to live after GitHub goes live
- [ ] Push the code to the public GitHub repo `github.com/lazytarget/questkit`
- [ ] Set up a package registry on GitHub / PyPI so `pip install questkit` works

## Log

- 2026-08-22: captured from R&D catalog REL-4 (draft, milestone 0.9.0)
- 2026-10-16: Bumped 0.9.0 -> 0.4.0; added public-GitHub scope (secret audit, push to github.com/lazytarget/questkit, GitHub/PyPI registry). Gitea remote stays.

