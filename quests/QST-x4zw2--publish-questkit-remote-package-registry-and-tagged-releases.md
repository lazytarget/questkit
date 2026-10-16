---
id: QST-x4zw2
title: Publish questkit remote package registry and tagged releases
description: Take questkit public on GitHub with a Gitea PyPI registry and tagged releases; history audited, publishing steps pending.
project: questkit
type: epic
status: in-progress
priority: medium
tags:
  - questkit
  - release
  - infra
created: 2026-08-22
status_changed: 2026-10-16
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
mirror. Registry decision: the Gitea PyPI-compatible
registry for now; GitHub / PyPI publishing follows once the setup is more
mature (0.9.0).

## Acceptance Criteria

- [x] Audit the Gitea Git repo history for secrets and sensitive data (tokens, hostnames, personal data, Realm-internal paths) before anything is published to GitHub. The Gitea remote continues to live after GitHub goes live
- [ ] Push the code to the public GitHub repo `github.com/lazytarget/questkit`
- [ ] Set up a Gitea PyPI-compatible package registry so `pip install --index-url <gitea>/api/packages/<owner>/pypi/simple questkit` works. GitHub / PyPI publishing follows once the setup is more mature (0.9.0)

### History audit (2026-10-16)

Scanned every added line in all 102 commits (all refs) for key and token
shapes, credential-style assignments, sensitive file names, private
hostnames, addresses and email addresses.

- **No credentials, tokens, private keys or sensitive files** were found.
- **Personal and infrastructure detail** is present in the history and in the
  current `quests/` and `docs/planning/` files: an internal IP address and VM
  id, the private Gitea host name, employer and client names, a family
  member's name, and private repository names. Removing it from the current
  tree is easy; removing it from history needs a rewrite or a fresh history.
- The current code, tests and user docs were scrubbed of these details in the
  same pass.

## Acceptance Criteria (follow-up)

- [ ] Decide the history strategy for the public repo (publish a fresh squashed history, or rewrite and scrub), and decide whether `quests/` and `docs/planning/` go public as they are
- [ ] Scrub the remaining private-environment details from whatever goes public
- [ ] Bump `pyproject.toml` to 0.4.0 and tag `v0.4.0` (plus retro-tags `v0.1.0`) with `scripts/release.py`

## Log

- 2026-08-22: captured from R&D catalog REL-4 (draft, milestone 0.9.0)
- 2026-10-16: Bumped 0.9.0 -> 0.4.0; added public-GitHub scope (secret audit, push to github.com/lazytarget/questkit, GitHub/PyPI registry). Gitea remote stays.
- 2026-10-16: Registry decision: Gitea PyPI for now; GitHub / PyPI publishing at 0.9.0.
- 2026-10-16: History audit done (no credentials; personal and infrastructure detail found); follow-up criteria added.

