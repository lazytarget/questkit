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

### Decisions (2026-10-16)

- **Approved to be public:** the Gitea host name (it is only reachable over
  Tailscale and requires authentication even if exposed), the portfolio domain
  `peteraslund.me`, internal IP addresses and VM ids. These do not need
  scrubbing, though the host name may still be generalised in docs because
  nothing in questkit depends on it being Gitea.
- **Redact:** family member names. Done in the current tree (the owner example
  in `QST-whm2e`); the three commits that contain it are only fixable by a
  history rewrite (see below).
- **Undecided:** employer and client names (`work-a`, `home`, `work-c`,
  `work-b`) and the private repository names listed below.
- **Deferred:** bumping `pyproject.toml` and tagging `v0.4.0` wait until every
  `milestone: 0.4.0` quest is complete.
- **Registry:** Gitea PyPI-compatible registry, owner `peter`. GitHub / PyPI
  publishing follows at 0.9.0.

### What the audit found, by category

Counts are for the current tree (files / lines); the history contains the same
strings in the number of commits shown.

| Term | Kind | Tree | Commits touching it |
|------|------|------|---------------------|
| family member's first name | personal | 1 / 2 (now removed) | 3 |
| `work-a`, `home`, `work-c`, `work-b` | employer / client names | 4 / 7, 3 / 4, 1 / 1, 4 / 5 | 4, 1, 1, 2 |
| `pensieve` | private repo | 13 / 30 | 14 |
| `grocy-ecosystem` (and `grocy`) | private repo | 9 / 20 | 11 |
| `realm-system` | private repo | 5 / 10 | 7 |
| `home-lab` | private repo | 5 / 11 | 4 |
| `realm-01`, `realm-prod-01` | private hosts | 14 / 39 | 18 |
| internal IP and VM id | infrastructure | in history only | 1 |

The code, tests and user docs (`README.md`, `docs/questkit.md`) are already
free of these. What is left is in `quests/` and `docs/planning/`.

### Rewriting history: what it does

Nothing has been pushed to GitHub yet, so a rewrite now has no public-copy
problem. These are the effects, for a `git filter-repo --replace-text` pass
over all refs:

- **Commit ids change.** A commit id hashes the tree, the parent ids, the
  author and committer lines and the message. The first changed commit and
  every descendant get new ids. The earliest commit containing the family
  name is the second in the repository, so **99 of 108 commits** would change,
  whatever the scope of the redaction. Redacting only that name costs the same
  as redacting everything.
- **Timestamps and authors are kept.** filter-repo preserves the author and
  committer dates and names. Only ids change. Short ids written inside commit
  messages are rewritten to match, but ids written in quest or doc text are
  not (one occurrence found in tracked text).
- **Signatures are lost.** 30 of the 108 commits carry a good GPG signature
  and `v0.3.0` is a signed tag. Rewritten commits and tags are unsigned.
  Re-signing is possible afterwards but is its own step.
- **Gitea PRs.** #1 and #2 are merged and #3 is open. Gitea stores the head,
  base and merge commit ids. After a force-push, expect the merged PRs to keep
  their title and comments but lose a working Commits and Files tab, because
  the merge commits they point at no longer exist on `main`. The open PR
  follows its branch if that branch is force-pushed as well.
- **Which remotes are affected.** Only a remote you force-push to. Rewriting in
  place on Gitea rewrites the primary, and a push mirror would then overwrite
  GitHub to match. Rewriting only for a public copy leaves Gitea untouched but
  the two histories then have different ids, so a push mirror cannot be used:
  you would publish by running the same filter again and pushing. The filter is
  deterministic, so re-running it over a longer history reproduces the same
  rewritten prefix, and later publishes fast-forward.
- **Everything holding a copy breaks.** This repository and its worktrees,
  every other clone, and every `rev:` pin in a consuming repo's
  `.pre-commit-config.yaml` (consumers are told to pin a released rev) point at
  ids that no longer exist after a rewrite of the primary. Branches and tags
  must be rewritten too (`--all`), including `v0.2.0` and `v0.3.0` and the
  other remote branches.
- **Old objects linger.** The pre-rewrite objects stay on the Gitea server until
  it garbage-collects, and in any clone or reflog that already has them.
  Nothing the audit found is a credential, so that is a privacy matter, not a
  security one.

**Options**

1. **No rewrite.** Publish the history as it is, redact the current tree going
   forward. Ids, signatures, PRs and pins all stay. The family name, and
   whatever else you leave unredacted, stays visible in old commits.
2. **One rewrite before the first public push**, for the strings you choose.
   All commits and dates are kept; ids and signatures change; Gitea PRs #1 and
   #2 lose their commit views. Do it once, on the primary, so a push mirror
   still works, and do it before tagging `v0.4.0` so the tag is created on the
   final ids.
3. **Rewrite only a public copy.** Gitea is untouched and keeps working
   exactly as now; GitHub gets the scrubbed history through a repeatable
   filter script. No push mirror, and the two remotes have different ids.

### GitHub as a push mirror, or move entirely

| | Gitea primary + push mirror to GitHub | Move to GitHub |
|---|---|---|
| Source of truth | Gitea | GitHub |
| Gitea PRs, comments, agent runner (QST-2z8db), committer timer, hook pins that name the Gitea URL | keep working | need repointing, and PR discussion does not move with the git history |
| Contributions from outside | do not flow back: a GitHub PR or issue cannot be merged into Gitea, and anything pushed to GitHub is overwritten by the next mirror sync | normal GitHub flow |
| Visibility | read-only shop window; issues and stars land on GitHub only | full |
| CI | GitHub Actions run on the mirrored pushes; registry publishing stays on a Gitea runner, because GitHub-hosted runners cannot reach a Tailscale-only host | GitHub Actions throughout; PyPI trusted publishing (no stored token) |
| Branches | all branches and tags are mirrored, so work-in-progress branches go public too (check whether your Gitea version offers a branch filter) | you choose what to push |
| Credentials | Gitea stores a GitHub deploy key or token | none stored in Gitea |
| Reversibility | turn the mirror off | a migration |
| Backlog | the quest log is in the repository, so it is public either way | same |

**Recommendation:** keep Gitea as the primary with a push mirror now. It keeps
every Realm automation working, it is private-first, and it can be switched off.
Revisit moving at 0.9.0, when GitHub / PyPI publishing is on the table and
trusted publishing becomes attractive. If you want the mirror, decide on the
history option first, because option 3 rules the mirror out.

### Setting up the Gitea PyPI registry (owner `peter`)

Gitea's package registry is built in (Site Administration must have packages
enabled, which is the default). The registry for the user `peter` lives at:

- upload: `https://<gitea-host>/api/packages/peter/pypi`
- install: `pip install --index-url https://<gitea-host>/api/packages/peter/pypi/simple questkit`

1. **Token.** Signed in as `peter`: Settings, Applications, Generate New Token,
   scope `write:package` (add `read:package` for a token used only to install).
   The token must belong to `peter` (or to a user with write access to
   `peter`'s packages), because the owner in the URL decides where the package
   lands.
2. **Manual first upload**, to prove the registry works before involving CI:
   ```sh
   python -m pip install build twine
   python -m build
   twine upload --repository-url https://<gitea-host>/api/packages/peter/pypi \
     --username peter --password <token> dist/*
   ```
   The package then appears under the user's Packages tab; link it to the
   repository from the package settings.
3. **Actions.** In the repository's Settings, Actions: enable Actions, and
   confirm a runner is registered. Add the variable `PYPI_REGISTRY_URL` (the
   upload URL above) and the secrets `PYPI_REGISTRY_USER` (`peter`) and
   `PYPI_REGISTRY_TOKEN` (the token). Names cannot start with `GITEA_` or
   `GITHUB_`.
4. **Release.** Pushing a tag `vX.Y.Z` whose version matches `pyproject.toml`
   runs `.github/workflows/publish.yml`, which Gitea Actions also reads when
   there is no `.gitea/workflows/`. The job is skipped on github.com because
   `PYPI_REGISTRY_URL` is not set there.
5. **Installing** from another machine on the tailnet needs the same index URL
   and a `read:package` token (`pip` takes it in the URL, or via `~/.netrc`).

A published version cannot be overwritten; a failed release needs a new
version number.

## Acceptance Criteria (follow-up)

- [x] Redact the family member's name in the current tree
- [ ] Decide the history strategy (no rewrite, one rewrite on the primary, or a rewritten public copy) and which strings to redact; see Decisions
- [ ] Decide on employer, client and private repository names in `quests/` and `docs/planning/`
- [ ] Push mirror from Gitea to `github.com/lazytarget/questkit`, or the decision to move instead
- [ ] Gitea PyPI registry working for owner `peter`: Actions variable and secrets set, first upload succeeds from a tag
- [ ] Once every `milestone: 0.4.0` quest is complete: bump `pyproject.toml` to 0.4.0, run `scripts/release.py`, tag `v0.4.0` (and retro-tag `v0.1.0`)

## Log

- 2026-08-22: captured from R&D catalog REL-4 (draft, milestone 0.9.0)
- 2026-10-16: Bumped 0.9.0 -> 0.4.0; added public-GitHub scope (secret audit, push to github.com/lazytarget/questkit, GitHub/PyPI registry). Gitea remote stays.
- 2026-10-16: Registry decision: Gitea PyPI for now; GitHub / PyPI publishing at 0.9.0.
- 2026-10-16: History audit done (no credentials; personal and infrastructure detail found); follow-up criteria added.
- 2026-10-16: Recorded decisions, history-rewrite effects, mirror vs move, and the Gitea PyPI registry setup. Hostname, peteraslund.me, IPs and VM ids approved as public; family name redacted in the tree; version bump deferred until 0.4.0 is complete.

