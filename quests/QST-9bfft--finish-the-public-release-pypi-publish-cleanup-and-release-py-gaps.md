---
id: QST-9bfft
title: "Finish the public release: PyPI publish, cleanup and release.py gaps"
description: "What is left after v0.4.0 shipped: the PyPI trusted publisher (blocked on the PyPI web interface), the 0.4.1 release that gives PyPI provenance and verified links, and revoking the token. release.py and the cleanup are done."
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

questkit v0.4.0 was tagged and published to the Gitea registry while the PyPI account
was not reachable. The PyPI token was added afterwards and 0.4.0 went to PyPI on
2026-10-21, but with no provenance and no project links. QST-x4zw2 (the public release)
and QST-tf4wc (CI and publish workflows) closed with the release. This quest holds
what is left.

## Spec

**PyPI: 0.4.0 is out, its provenance is not.** `questkit 0.4.0` is on PyPI and installs
from it (checked in a clean venv). It was uploaded with twine and a token, so it has
no attestations and no `[project.urls]`. From the PyPI documentation: provenance on the
project page is signed attestations (PEP 740), PyPI accepts those only from trusted
publishing, and it verifies project links only at upload time, and only a GitHub URL
for the repository a trusted publisher is configured for. Neither can be added to
0.4.0 (the documentation does not cover adding an attestation to an uploaded file; as
far as we know a released file is immutable), so the fix is a new release:

1. Repo side, branch `feat/pypi-trusted-publishing`: `publish-pypi.yml` uses
   `pypa/gh-action-pypi-publish@release/v1` with `id-token: write` on the publish job
   only and no secret, and `pyproject.toml` gains `[project.urls]` (Homepage, Source,
   Changelog, Documentation, all on GitHub).
2. On pypi.org, by hand: questkit, Manage, Publishing, GitHub Actions: owner
   `lazytarget`, repository `questkit`, workflow `publish-pypi.yml`, environment
   `pypi`. There is no API for this: PyPI's documentation lists none and says "the
   only manual step is configuring the publisher on PyPI". It does not say what an API
   token can do besides upload, and the account token was not tried on anything else.
3. Release 0.4.1: bump `pyproject.toml` and reinstall the editable venv (the script
   checks the two agree), then `scripts/release.py --remote gitea --remote github`,
   which commits the changelog, tags it and pushes the branch and the tag to both. The
   Gitea registry gets 0.4.1 from the same tag. **Waiting:** Peter has not been able to
   reach the PyPI web interface yet, so step 2 cannot be done and 0.4.1 is not built.
4. Check on PyPI that the files show provenance and the GitHub links show as verified,
   and that `pip install questkit==0.4.1` works. A manual run can not test this: only a
   `v*` tag enters the `pypi` environment.
5. Then delete the `PYPI_API_TOKEN` secret of the `pypi` environment and revoke the PyPI
   account token (1Password: `op://The Realm/PyPI/API TOKEN`). The account-wide token
   is the largest exposure until that is done.

**Older versions.** `v0.1.0`, `v0.2.0` and `v0.3.0` build and pass `twine check`, and
each tag's `pyproject.toml` matches its name (checked 2026-10-21). They have no publish
workflow, so they could only be uploaded with the token: no provenance, no links, and a
PyPI version can be yanked but never replaced. **Decided 2026-10-21: not published.**
Peter's message named `v0.1.0` and `v0.3.0`; `v0.2.0` was not mentioned, and it is
treated as declined with them because the reasons are the same. Correct this line if
that is wrong.

**Cleanup.**

- Devices: `dev-01`, `grocy-01`, the work device and the MacBook are repaired in place,
  and `realm-prod-01` needs no repair because it has not accepted the Syncthing invites
  (all reported by Peter, 2026-10-21). `LAZY-PROART` and `LazyNAS` need no action.
- The local `questkit---backup` checkout is gone (absent on `dev-01`, removed from the
  Syncthing `lazytarget` directory by Peter).
- The Gitea repository `peter/questkit---backup` is archived and kept, not deleted
  (Peter's decision; the Gitea API reports `archived: true`, `private: true` on
  2026-10-21). The bundle in `06-archive` stays.
- Dropped by Peter: removing the old `lazytarget` remote from devices that applied
  `repos.yaml` before the GitHub remote was renamed to `github`.

**scripts/release.py (done, branch `feat/release-script-remotes`).** It had never run end to
end, and the 0.4.0 release found two gaps, so 0.4.0 was cut by hand with the script's own
functions. Both are fixed:

- It now commits `CHANGELOG.md` on its own before it tags, so the tag holds its own
  changelog entry and the tree is left clean. A refused commit puts the file back; a tag
  that cannot be created undoes the script's own commit.
- `--remote` is repeatable and the branch and the tag are pushed together with
  `git push --atomic` to each remote in the order given. With none given it uses `origin`
  or the only remote, and refuses a repository with several remotes and no `origin`
  (this one). Unknown remotes and a detached HEAD are refused before anything is written,
  and a failure on a later remote prints the commands that finish the job.

Found while testing it: git 2.43 with ssh signing prints "Couldn't load public key" for an
unreadable signing key and still exits 0, leaving an **unsigned** annotated tag. The script
would have pushed it as a signed release. `create_tag` now checks the tag object carries a
signature and deletes the tag otherwise. Rehearsed end to end in a scratch clone of this
repository with two local bare remotes and a throwaway key (a pretend 0.4.1): both remotes
received the branch and the tag on the same commit, and the tag verified as `Good`.

## Acceptance Criteria

- [x] The `v0.4.0` tag published to the Gitea registry (Gitea run 720) and `questkit==0.4.0` installs from it with pip
- [x] `PYPI_API_TOKEN` added to the `pypi` environment (secret updated 2026-10-21 12:02 UTC)
- [x] `questkit 0.4.0` is on PyPI and installs from it (GitHub run 39580254037, files uploaded 12:02 UTC)
- [x] The trusted-publishing workflow and `[project.urls]` are merged (PR #6, merge commit `4f03b47`)
- [ ] The PyPI trusted publisher is added in the web interface (owner `lazytarget`, repository `questkit`, workflow `publish-pypi.yml`, environment `pypi`); blocked on access to the PyPI interface
- [ ] `questkit 0.4.1` is on PyPI with provenance and verified GitHub links, tagged on both remotes and on the Gitea registry
- [ ] The `PYPI_API_TOKEN` secret is deleted and the PyPI account token revoked
- [x] Decided: `v0.1.0` to `v0.3.0` are not published to PyPI
- [x] `dev-01`, `grocy-01`, the work device and the MacBook repaired; `realm-prod-01` needs no repair (reported by Peter)
- [x] The local `questkit---backup` checkout is gone
- [x] The Gitea repository `peter/questkit---backup` is archived and kept (not deleted)
- [x] `scripts/release.py` commits the changelog before it tags, and can push the branch and tag to several remotes (branch `feat/release-script-remotes`)

## Log

- 2026-10-21: captured when v0.4.0 shipped. Moved here from QST-x4zw2 and QST-tf4wc: the PyPI publish (blocked on the API token), the realm-prod-01 re-clone, deleting the backup repository, and the release.py gaps found while cutting the release.
- 2026-10-21: v0.4.0 published to the Gitea registry by the tag push (run 720) and verified by installing questkit==0.4.0. On GitHub the tag's PyPI run is waiting at the pypi environment; PyPI still has no questkit project.
- 2026-10-21: PyPI token added and 0.4.0 published to PyPI (run 39580254037). It has no provenance and no project links: PyPI accepts attestations only from trusted publishing and verifies links only at upload. Plan recorded: trusted-publishing workflow and [project.urls] in a PR, trusted publisher added by hand (no API), release 0.4.1, then revoke the token. MacBook repaired; realm-prod-01 needs no repair; local questkit---backup gone.
- 2026-10-21: Peter approved and merged PR #6 (trusted publishing, project URLs). release.py now commits the changelog before tagging and pushes the branch and tag atomically to several remotes (found and guarded: git 2.43 can create an unsigned tag with exit 0). Declined publishing the older tags to PyPI. peter/questkit---backup archived, not deleted; the old lazytarget-remote item dropped. 0.4.1 waits for access to the PyPI web interface.

