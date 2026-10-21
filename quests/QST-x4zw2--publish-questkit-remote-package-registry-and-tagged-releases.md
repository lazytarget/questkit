---
id: QST-x4zw2
title: Publish questkit remote package registry and tagged releases
description: Take questkit public on GitHub with a Gitea registry, PyPI and tagged releases; live on GitHub with CI green, PyPI workflow written; the PyPI secret, environment rules, first publish and the 0.4.0 release still open.
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
modified: 2026-10-21
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
mature (0.9.0). (Superseded 2026-10-21: PyPI is in the 0.4.0 scope.)

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
- **Family member names:** redacted in the current tree (the owner example in
  `QST-whm2e`). The old commits that contain it stay as they are; that is
  accepted.
- **Redact:** employer and client names (kept in the private deny-list used by
  `scripts/sensitive_scan.py`, never in the repository). Done in the current tree;
  in history it needs the rewrite described below.
- **Undecided:** the private repository names listed below. Redacting them
  from history would rewrite all 110 commits (the very first commit has one);
  leaving them costs nothing extra, so they are left unless you decide otherwise.
- **If moving to GitHub entirely:** Gitea PRs and their discussion do not need
  to be migrated.
- **Deferred:** bumping `pyproject.toml` and tagging `v0.4.0` wait until every
  `milestone: 0.4.0` quest is complete.
- **Registry:** Gitea PyPI-compatible registry, owner `peter`. GitHub / PyPI
  publishing follows at 0.9.0. (Superseded 2026-10-21: PyPI is in the 0.4.0 scope.)
- **Approved to publish (2026-10-17):** 1Password item paths such as
  `op://The Realm/...`. They name a vault and an item, not a secret.
- **Placeholders in the tree:** employer and client names became `work-a`,
  `work-b` and `work-c`, and one household name became `home`. The mapping to
  the real names exists only in the private deny-list file.

### What the audit found, by category

Counts are for the current tree (files / lines); the history contains the same
strings in the number of commits shown.

| Term | Kind | Tree | Commits touching it |
|------|------|------|---------------------|
| family member's first name | personal | 1 / 2 (now removed) | 3 |
| four employer / client names | employer / client names | 13 lines in 7 files (now removed) | 4 commits in total |
| `pensieve` | private repo | 13 / 30 | 14 |
| `grocy-ecosystem` (and `grocy`) | private repo | 9 / 20 | 11 |
| `realm-system` | private repo | 5 / 10 | 7 |
| `home-lab` | private repo | 5 / 11 | 4 |
| `realm-01`, `realm-prod-01` | private hosts | 14 / 39 | 18 |
| internal IP and VM id | infrastructure | in history only | 1 |

The code, tests and user docs (`README.md`, `docs/questkit.md`) are already
free of these. What is left is in `quests/` and `docs/planning/`.

### What a redaction costs, measured (2026-10-16)

`scripts/sensitive_scan.py history` reports, for a set of terms, the matching
commits and how many commits would get new ids. Measured on this repository
(110 commits, all refs):

| Redact | Matching commits | Earliest match | Rewritten | Keep their ids |
|--------|------------------|----------------|-----------|----------------|
| employer and client names | 4 | 2026-08-19 | **85** | **25** |
| internal host and VM id | 5 | 2026-08-19 | 85 | 25 |
| family member name | 6 | 2026-08-13 | 101 | 9 |
| private repository names | 20 | 2026-08-13 (first commit) | 110 | 0 |

The cost is set by the *earliest* match, not by how many commits match. So with
the decisions above (family name stays, host and IPs approved, repository names
left), the only history redaction is the employer names: **85 commits get new
ids and the first 25 keep theirs**. All commits, authors and dates are kept.
The only way to keep every id is not to rewrite. Squashing does not help:
squashing the span from the first to the last match is 85 commits and the
commits after it still change, because a commit id includes its parents.

### Keeping it out in future: tooling

Credential scanners and a private deny-list solve different problems:

- **Credentials** (tokens, keys, high-entropy strings): gitleaks, the most
  widely used one, runs as a `pre-commit` hook on the staged diff and, on
  GitHub, as `gitleaks/gitleaks-action` over the full history in CI. The
  alternative is Yelp's `detect-secrets` (pure Python, baseline file). Both are
  what well-known repositories use. Both found nothing in this history.
- **Names, employers, hosts**: no scanner can know these. They need a
  deny-list, and the list is itself sensitive, so it lives outside the
  repository (`~/.config/questkit/sensitive-terms`, or `$SENSITIVE_TERMS_FILE`).
  `scripts/sensitive_scan.py` reads it and offers `history`, `tree`, `staged`
  (pre-commit hook) and `push` (pre-push hook). With no list configured the
  hooks pass, so contributors are not blocked. gitleaks can also take custom
  rules from a private `--config` file, but it does not report how many
  commits a rewrite would touch.
- Wired in `.pre-commit-config.yaml` (`pre-commit install` installs both the
  commit and push stages) and in `ci.yml` (gitleaks on GitHub only).

### Keeping a truncated GitHub history in sync with the full Gitea one

A commit id is a hash of its tree, author, message **and parent ids**. So two
remotes share a commit only if they share every ancestor of it. This decides
what is possible:

- **"Squash for GitHub, then merge an empty commit back into Gitea"** does not
  work. The merge commit `M` has the full Gitea history as one parent, so pushing
  `M` (or anything built on it) to GitHub sends all of that history too. Git
  always sends everything reachable.
- **"Never send parents older than commit X"** has no push-side option in git.
  A shallow clone cannot reliably push, and `git replace --graft` only changes
  your local view until it is baked in (the baked commits get new ids).
- **What does keep ids identical:** make the squashed commit `S` the shared base.
  Gitea's `main` continues from `S` as well, and the old full history stays on
  Gitea under an archive ref (for example `archive/pre-public` plus the existing
  tags). From `S` on, both remotes get the same commits with the same ids.
  Nothing is lost on Gitea, and PRs #1 to #3 keep resolving because their
  commits are still reachable from the archive ref. The cost: Gitea's `main`
  is replaced once (force-push), and a Gitea push mirror must not mirror the
  archive ref or the old tags (mirror `main` and new tags only, or push by
  script), or the old history reaches GitHub anyway.
- **Alternative, Gitea untouched:** a deterministic transform (graft the cut,
  optionally redact terms) applied to every new Gitea commit by a script. The
  public ids are then different from Gitea's but reproducible, so publishing is
  a fast-forward. No push mirror and no shared ids.

Squashing only the employer-name span (first to last match, 85 commits) and
keeping the commits before and after it individually is possible but gives up
the commit granularity there. A text redaction keeps all 110 commits, so it is
the better public history if shared ids with Gitea are not needed.

### Packages belong to the owner, linked to the repo

Gitea package registries are owner-scoped: the upload URL is
`/api/packages/<owner>/pypi`, never per repository. A package is then
*linked* to a repository so that it shows on the repository's Packages tab
(package settings, or `POST /api/v1/packages/<owner>/pypi/<name>/-/link/<repo>`).
`questkit` is linked to `peter/questkit`.

### Releasing by hand with twine

```sh
uv build                                  # dist/*.whl and dist/*.tar.gz
uvx twine check dist/*                    # validates the metadata and README
export TWINE_REPOSITORY_URL=https://<gitea-host>/api/packages/peter/pypi
export TWINE_USERNAME=peter
export TWINE_PASSWORD="$(op read 'op://The Realm/gitea-user-peter/PAT/gitea-pypi-reg')"
uvx twine upload dist/*                   # add --skip-existing to re-run safely
```

Install: the registry must be an *extra* index, because `--index-url` would
replace PyPI and lose the dependencies:

```sh
uv pip install --extra-index-url https://peter:<token>@<gitea-host>/api/packages/peter/pypi/simple questkit
```

A version can be deleted with `DELETE /api/v1/packages/peter/pypi/questkit/<version>`
but not re-uploaded under the same number with different content.

### Deploying to the Gitea registry

State: the registry token and the repository secrets and variable are set.
`publish.yml` runs on the Gitea runner on a `vX.Y.Z` tag, and can be run by
hand once it is on `main` (a manual run publishes `<version>.devN`, never the
real version, because a registry will not let a version be overwritten).

1. Prove the registry and token with a local upload of a `.dev` build.
2. Merge the pull request, then run the Publish workflow by hand from the
   Actions tab (a dry run of the CI path).
3. After the last 0.4.0 quest: bump the version, run `scripts/release.py`,
   tag; the tag push publishes for real.

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

### Agreed plan for the history (2026-10-17)

The tree and the commit graph are kept. Only the commits that introduced
sensitive text are redacted, which gives new ids to every descendant of the first
match, more than 85 commits. That cost is accepted.

1. **Merge order.** #4 (CI, hooks, scanner) and #5 (QST-03fim) are merged. Update
   #3 from `main`, review, merge it. Done before any rewrite, so the rewrite sees
   the final tree.
2. **Back up** the whole repository as a `git bundle` in the archive folder, then
   run `git bundle verify` on it. Keep the filter-repo commit map next to the
   bundle once step 4 has produced it.
3. **Rename** the current Gitea repository to `questkit---backup` (the name is
   accepted). Renaming keeps PRs #1 to #5, the Actions history and the registry
   package with the old repository. It becomes the private archive.
4. **Rewrite in a fresh clone**, never in a working checkout or a worktree. Clone
   the backup repository, run `git filter-repo` with the private deny-list
   replacements, and append a `Rewritten-from: <old commit id>` trailer to every
   commit whose id changes. The set of such commits is the first match and all its
   descendants; `scripts/sensitive_scan.py history --json` already finds the first
   match, so listing the set is a small addition. Tags are rewritten too, and the
   signatures on the signed tag and 30 signed commits are lost. Unverified:
   filter-repo's exact callback for the trailer. Try it on a throwaway clone first.
5. **Verify** in that clone before pushing anywhere: `sensitive_scan.py history`
   reports 0 matches, the commit count is unchanged, the tip tree differs from the
   pre-rewrite tip only in the redacted terms, tests pass, gitleaks is clean.
6. **Create fresh repositories** named `questkit` on Gitea and on
   `github.com/lazytarget/questkit`, push the rewritten history, then redo what is
   per repository: Actions variable and secrets, runner scope, the registry package
   link. PR numbers restart.
7. **Other devices.** Repaired in place, not re-cloned: `questkit` is still a hybrid
   repo, so deleting, moving or re-cloning it inside the Syncthing folder would be
   replicated to every device. See "Other devices after the rewrite" below.

Recomputed just before step 4: 100 of 125 commits change id and the 25 oldest keep
theirs (the earlier figure of 85 of 110 predates the 0.4.0 commits). The rewrite
did not wait for the remaining 0.4.0 quests.

Still open: how the two remotes stay in sync (see the answers below), and whether
the private repository names stay in history (left as is unless decided otherwise).

### Status of the plan (2026-10-20)

| Step | State |
|------|-------|
| 1. Merge #3 | Done 2026-10-17 (merge commit `f50790d` in the backup repository). |
| 2. Backup | Done 2026-10-17: `06-archive/git-bundles/02-projects-lazytarget-questkit-2026-10-17.bundle`, sha256 `d463e9797c5388b19f272b458f515c0a8cb044e990fa901fdd6aab1e5616bda3`. `git bundle verify` passes, and a scratch clone of it has a clean `git fsck` and the same tip tree as the server. A manifest and the commit map sit beside it. |
| 3. Rename | Done: `peter/questkit---backup`, private. The local checkout moved to `02-projects/lazytarget/questkit---backup`. |
| 4. Rewrite | Done 2026-10-17 in a fresh clone with `git filter-repo`: **100 of 125 commits** got new ids, each carries `Rewritten-from: <old id>`, and the 25 oldest keep theirs. Old tip `f50790d` became `4f345cd`. Signatures on rewritten commits are gone. Tags `v0.2.0` and `v0.3.0` were re-pushed unsigned; `v0.3.0`'s message lost its stale SSH signature block and nothing else. |
| 5. Verify | Done: tip tree identical to the original, 125 commits before and after, 0 deny-list matches in patches, messages, authors, file names, refs and tags, gitleaks clean, 855 tests pass. The five `Reviewed-on:` links in merge commits now name the backup repository. |
| 6. Fresh repositories | Gitea done: `peter/questkit` (private) holds the rewritten history, CI is green on the Gitea runner, and the Actions variable and secrets were added by the owner. Open: GitHub, and the package link (below). |
| 7. Other devices | Not started; see the next section. |

New commits in the fresh repository are signed and verify (checked 2026-10-17).

Found while closing the plan:

- The registry package `questkit 0.3.0.dev1` is still linked to
  `peter/questkit---backup`, because the link followed the renamed repository.
  Re-link it to `peter/questkit` before the backup repository is deleted.
- `repos.yaml` needed no change for the move. Only `core.fileMode` drifted on the
  new clone, and `make apply-repos REPO=questkit` fixed it (`REPO=` is new:
  realm/99-system PR #13).
- The new clone on `dev-01` was onboarded with `make onboard-zone` followed by
  `pre-commit install` (commit and push stages), which reproduces the backup
  repository's hook chain.

### Other devices after the rewrite (2026-10-20)

Derived from `syncthing.yaml`, `repos.yaml` and the runbook
`99-system/docs/syncthing-stale-folder-recovery.md`; the live Syncthing settings
were not checked. The commands were rehearsed in a scratch copy holding the old
history and a local branch, and have not been run on any real device except
`dev-01`.

**Why not just re-clone.** The git-zone cutover has not run, so Syncthing still
carries `questkit`'s working tree while each device keeps its own `.git`. Deleting,
moving or re-cloning it inside the synced folder is replicated to every device. And
the rewritten history reaches no device through Syncthing, so every other device's
`.git` still holds the old history, including the unredacted names, until it is
reset and pruned.

| Device | Gets the working tree | Own `.git` | Action |
|--------|-----------------------|-----------|--------|
| `dev-01` | yes | yes | Done 2026-10-20: fresh clone, onboarded. |
| `LAZY-PROART`, `LazyNAS` | yes | yes; the two sync `.git` between themselves (neither has an ignore list) | Repair on `LAZY-PROART` only, then check `LazyNAS` once it has caught up. |
| the work device, `grocy-01` | yes | yes | Repair in place. |
| MacBook, phone | yes | no (both ignore `.git`) | Nothing: they only receive files. |
| `realm-prod-01` | no (not in the Syncthing folder) | yes, cloned by `apply-repos` | Not synced, so re-cloning is safe: move the old checkout aside, then `make apply-repos REPO=questkit`. |

`questkit---backup/` will also arrive, as plain files without `.git`, on the devices
that receive the folder (expected, not verified). Deleting it later removes it
everywhere.

**Repair in place**, in `02-projects/lazytarget/questkit` on each device:

1. Wait until Syncthing reports the folder idle. Never pause it (runbook, part 1).
2. Before fetching, find work that exists only on this device. This reads the old
   remote-tracking refs, so it must come first:
   ```sh
   git log --branches --not --remotes --oneline   # unpushed commits, any branch
   git stash list
   git status -sb                                 # expect only "Syncthing ran ahead" dirt
   git bundle create ~/questkit-local-work.bundle --branches --not --remotes   # keeps any of it
   git merge-base <branch> main                   # per branch to keep: note its old base
   ```
3. `git fetch gitea --prune --tags --force`. The `gitea` remote URL does not change,
   because the new repository reuses the name. `--force` is needed: `v0.3.0` now
   points elsewhere.
4. `git reset gitea/main`, a mixed reset and never `--hard`: the working tree is
   already right, and `--hard` rewrites files and risks the clobber the runbook
   describes. `git status -sb` must then be clean. If it is not, wait for Syncthing
   and look again before going on.
5. Move each branch worth keeping onto the new history:
   `git rebase --onto main <old base from step 2> <branch>`. Delete the rest with
   `git branch -D`, and `git worktree prune` registered worktrees that point at old
   commits. `06-archive/git-bundles/02-projects-lazytarget-questkit-2026-10-17.commit-map.txt`
   maps every old id to its new one.
6. Drop the old history from the device, only once step 2 found nothing unsaved:
   ```sh
   git reflog expire --expire=now --all && git gc --prune=now
   git cat-file -e f50790dd76ee2971e19f3e66698916c70b66cc64 && echo STILL THERE
   ```
7. Re-wire what is per device: `uv venv && uv pip install -e ".[dev]"` then
   `.venv/bin/pre-commit install`; once Syncthing has delivered `.realm/`,
   `make refresh-zones` for the Realm hook; and `make apply-repos REPO=questkit` for
   `core.fileMode`. `REPO=` needs `99-system` from PR #13; until then run
   `make apply-repos` without it.

### Answers recorded (2026-10-17)

These come from memory and secondary sources, not from the Gitea or GitHub
documentation. Verify the marked points before relying on them.

- **Why two remotes.** Gitea is the private working remote: the runner, agent
  pull requests and the package registry behind the tailnet. GitHub is the public
  side: discovery, contributions and later PyPI.
- **Push or pull.** A Gitea push mirror force-pushes, so anything merged only on
  GitHub is overwritten on the next sync (unverified). The safer shape is a
  non-force push of `main` and `v*` tags from the runner: a GitHub `main` that has
  diverged then fails loudly instead of being clobbered. A pull mirror is
  read-only (unverified), which would end the PR flow on Gitea.
- **Two-way sync.** Nothing native. A scheduled job could fast-forward Gitea from
  GitHub when GitHub is strictly ahead and open a PR when it has diverged. Not
  worth building before outside contributions exist.
- **Releases and packages.** Tags are plain refs and sync. Releases and packages
  do not sync as such (unverified); each target gets its own publish step from the
  same tag. `scripts/release.py` already assembles the changelog section, which a
  workflow can reuse for both release pages.
- **SHA-256.** Not now. SHA-1 and SHA-256 repositories cannot exchange objects, and
  GitHub support is unconfirmed. Revisit once GitHub documents it.

### Decisions (2026-10-21)

- **No sync mechanism between the remotes.** Gitea (`peter/questkit`) and GitHub
  (`lazytarget/questkit`) are two independent remotes. Nothing mirrors either way,
  so every push goes to each remote by hand (`git push gitea ...`, `git push github ...`).
  A push mirror from GitHub to Gitea stays possible later, if outside contributions
  ever land on GitHub.
- **Pushed everything:** `main` (9cbcb90, 131 commits) and tags `v0.2.0`, `v0.3.0`.
  The rewritten commits and the two tags are unsigned; only future commits need to be.
- **The `Reviewed-on:` links are not rewritten.** Five merge commits still point at
  `peter/questkit---backup/pulls/N`, a private repository that will be deleted, so
  those links will not resolve for the public.
- **Before the push:** a full-history deny-list scan (0 of 131 commits), gitleaks
  over the history (clean), and the same scan over author names, file names, refs and
  tag text (all 0). The pre-push hook alone would not have covered it: for a new
  remote it scans only commits that no remote-tracking ref already has.
- **The `Publish` workflow did not run on GitHub.** The tags were pushed without it,
  and its job is also guarded by `vars.PYPI_REGISTRY_URL`, which is set only on Gitea.

### Decisions (2026-10-21): PyPI is in 0.4.0

- **Scope.** Publishing to PyPI moves from 0.9.0 into 0.4.0, together with
  QST-tf4wc (the workflows). There is no separate PyPI quest: both quests already
  carry `milestone: 0.4.0`, and their text now says so.
- **Remote name.** The GitHub remote is called `github`, and is declared under that
  name in `99-system/repos.yaml`. It was first named `lazytarget` after the account,
  like the other sibling remotes in that file (realm/99-system PR #14), and was
  renamed on 2026-10-21 because `github` says what it is.
- **Account.** The PyPI.org account is `lazytarget`; the GitHub environment `pypi`
  exists with a required reviewer; `PYPI_API_TOKEN` is added there by the owner.
  `questkit` is not registered on PyPI (404 on 2026-10-21), so the first upload
  creates the project.
- **Workflows.** `publish-gitea.yml` and `publish-pypi.yml`, one per registry and
  each guarded so it runs only on its own host (Gitea's runner reads
  `.github/workflows/` too). The Gitea job needs `PYPI_REGISTRY_URL` and never runs
  on github.com; every PyPI job runs on github.com only. Neither mentions the other's
  credentials, and tests enforce that. Both start from a `v*` tag or by hand.
- **Manual runs are safe.** Gitea publishes a `.devN` version. PyPI builds and
  checks only, unless started from a tag with "publish" ticked. Only the PyPI
  `publish` job sees the token and it runs no project code: the build runs in a
  separate job without secrets and hands over its files as an artifact.
- **Release procedure.** `scripts/release.py` pushes the tag to one remote, so:
  `release.py --remote gitea`, then `git push github vX.Y.Z`. Making `--remote`
  repeatable would remove the second step; not done, to be decided.

### Settings for the `pypi` environment (recommendation)

From memory of how GitHub behaves, not yet exercised: a dry run cannot prove the
tag rule, because the dry run never enters the environment.

- **Deployment branches and tags: "Selected branches and tags", with one tag rule
  `v*`.** Not "Protected branches only": the publish job is triggered by a tag, and
  a tag is not a branch, so that option would refuse the release. It would only
  suit a workflow that published from `main`, which this one does not. A manual
  re-publish started from a tag passes the same rule.
- **Required reviewers: keep you.** Leave "Prevent self-review" off while you are the
  only reviewer, because it blocks whoever started the run from approving it.
- **Administrator bypass: off,** if the setting is offered, so the rules also apply
  to you.
- **Secret in the environment**, not a repository secret, so only jobs that use
  `environment: pypi` can read it.
- **A ruleset on the tags `v*`** (Settings, Rules, Rulesets, target: tags), restricting
  creation to administrators and blocking updates and deletions. The environment rule
  only checks the tag's name; the ruleset stops a published tag being moved or
  deleted, and anyone else creating one.
- **A branch ruleset for `main`** is a separate choice (pull requests required, signed
  commits). The environment does not need it.
- **Token scope.** From memory: PyPI can only scope a token to a project that already
  exists, so the first release needs an account-wide token. Replace the secret with a
  token scoped to `questkit` straight after the first upload. Trusted publishing
  (a pending publisher on pypi.org, no secret at all) avoids this and is the
  alternative if the token is not wanted.
- **Not yet verified:** that the Run workflow button shows on GitHub (the file must
  first be on the default branch there) and that `twine upload` accepts the token.
  Nothing has been published to PyPI.

## Acceptance Criteria (follow-up)

- [x] Redact the family member's name in the current tree
- [x] Redact employer and client names in the current tree (placeholders `work-a`, `work-b`, `work-c`, `home`)
- [x] A private deny-list scanner with history, tree, staged and push modes, and hooks wired in (#4)
- [x] gitleaks on staged changes (pre-commit) and, on GitHub, over history in CI (#4, not yet run on a real runner)
- [x] Reusing one deny-list across repos captured as QST-03fim (#5)
- [x] Gitea PyPI registry: a local `.dev1` upload succeeded and installs from the registry (the package link must be redone, see below)
- [x] `ci.yml` runs green on the Gitea runner (runs 675 to 686, including the rewritten history)
- [x] `ci.yml` runs green on GitHub (run 39551580657 on the first push: pytest 3.11 to 3.13, lint and types, quest log, gitleaks)
- [ ] Manual run of `publish.yml` publishes a `.devN` version
- [x] Full history backed up as a `git bundle` in the archive folder and checked with `git bundle verify`, with the filter-repo commit map kept beside it
- [x] Current Gitea repository renamed to `questkit---backup` and kept private
- [x] History rewritten in a fresh clone: employer names redacted, a `Rewritten-from: <old id>` trailer on every commit whose id changes, `sensitive_scan.py history` reports 0 matches, commit count unchanged, tip tree identical apart from the redacted terms, tests pass
- [x] Fresh `questkit` repository on Gitea with the Actions variable and secrets re-added
- [x] Fresh repository at `github.com/lazytarget/questkit` (public, `main` plus tags `v0.2.0` and `v0.3.0` pushed 2026-10-21)
- [x] Registry package `questkit` re-linked to `peter/questkit` (done with `tea api` and the owner's PAT)
- [x] The new clone on `dev-01` onboarded (`make onboard-zone`, `pre-commit install`, `make apply-repos REPO=questkit`)
- [x] `LAZY-PROART` (not synced for six months, nothing to repair) and `LazyNAS` (will not accept this folder, Model C) need no action
- [ ] The remaining devices that hold the folder (the work device and `grocy-01`) repaired in place, and `realm-prod-01` re-cloned, with the old history pruned (see Other devices after the rewrite)
- [x] Decide how the two remotes stay in sync: they do not (see Decisions, 2026-10-21)
- [ ] Once every `milestone: 0.4.0` quest is complete: bump `pyproject.toml` to 0.4.0, run `scripts/release.py`, tag `v0.4.0` (and retro-tag `v0.1.0`) on the rewritten history
- [x] `publish-gitea.yml` and `publish-pypi.yml` written, tested and guarded per host (QST-tf4wc); the GitHub remote declared in `repos.yaml` (realm/99-system PR #14)
- [ ] PyPI: `PYPI_API_TOKEN` added to the `pypi` environment, the environment limited to the tag rule `v*`, and a ruleset protecting `v*` tags
- [ ] Both publish workflows pushed to GitHub and run by hand once (Gitea: `.devN`, GitHub: build and check)
- [ ] Publish 0.4.0 to the Gitea registry from the tag
- [ ] Publish 0.4.0 to PyPI from the tag, then replace the token with one scoped to the project
- [ ] Decide whether `scripts/release.py --remote` should accept several remotes
- [ ] Once the GitHub repository is live: delete the Gitea repository `peter/questkit---backup` and the local `questkit---backup` checkout, after re-linking the package and keeping the bundle in `06-archive`

## Log

- 2026-08-22: captured from R&D catalog REL-4 (draft, milestone 0.9.0)
- 2026-10-16: Bumped 0.9.0 -> 0.4.0; added public-GitHub scope (secret audit, push to github.com/lazytarget/questkit, GitHub/PyPI registry). Gitea remote stays.
- 2026-10-16: Registry decision: Gitea PyPI for now; GitHub / PyPI publishing at 0.9.0.
- 2026-10-16: History audit done (no credentials; personal and infrastructure detail found); follow-up criteria added.
- 2026-10-16: Recorded decisions, history-rewrite effects, mirror vs move, and the Gitea PyPI registry setup. Hostname, peteraslund.me, IPs and VM ids approved as public; family name redacted in the tree; version bump deferred until 0.4.0 is complete.
- 2026-10-16: Measured the cost of each redaction with scripts/sensitive_scan.py (employer names: 85 of 110 rewritten, 25 keep ids); wired gitleaks and the private deny-list into pre-commit and pre-push; registry deploy steps recorded.
- 2026-10-16: Verified the Gitea registry end to end: uploaded a .dev1 build, linked the package to peter/questkit, installed it from the registry. Recorded the history-sync analysis and a twine guide.
- 2026-10-17: #4 and #5 merged. Agreed the history plan: bundle backup, rename the current Gitea repo to questkit---backup, redact in a fresh clone with a Rewritten-from trailer, fresh repos on Gitea and GitHub. Recorded answers on remotes, sync, releases and SHA-256 (marked unverified). Placeholders: work-a/b/c and home. op:// paths approved as public.
- 2026-10-20: History rewrite done: bundle backup, repo renamed to questkit---backup, 100 of 125 commits rewritten with Rewritten-from trailers, fresh private repo on Gitea with CI green, dev-01 onboarded. Recorded the status of each plan step, the per-device repair procedure (rehearsed in a scratch copy), and that the registry package link still points at the backup repo.
- 2026-10-21: Pushed main and both tags to github.com/lazytarget/questkit; CI green on GitHub. Re-linked the registry package to peter/questkit. Decided: no sync mechanism between the remotes, nothing rewritten further, LAZY-PROART and LazyNAS need no repair. Recorded the PyPI-from-GitHub design for 0.9.0.
- 2026-10-21: PyPI moved into the 0.4.0 scope. Declared the GitHub remote as lazytarget in repos.yaml (99-system PR #14); wrote publish-gitea.yml and publish-pypi.yml; recorded the settings recommended for the pypi environment and the release procedure for two remotes.

