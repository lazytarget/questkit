---
id: QST-03fim
title: Share one sensitive-terms deny-list across all repos, sourced from 1Password
description: One private deny-list of names, employers and hosts, kept in 1Password and materialised on every machine, so every repo's hooks can refuse to commit or push them.
project: questkit
type: task
status: draft
priority: medium
tags:
  - questkit
  - security
  - hooks
  - privacy
created: 2026-10-16
modified: 2026-10-16
agentic: hitl
aliases:
  - QST-03fim
blocked_by: []
component:
effort: m
milestone:
related_adrs:
---

## Description

`scripts/sensitive_scan.py` blocks names, employers and hosts that no credential
scanner can know about, but it reads its deny-list from one file on one machine
(`~/.config/questkit/sensitive-terms`). Every other repo, machine and agent
worktree is unprotected, and the cost of a miss is high: removing a term from
history rewrote 85 of 110 commits in questkit's case
([[QST-x4zw2--publish-questkit-remote-package-registry-and-tagged-releases]]).

Goal: write the list once, keep it out of every git repository, and have it
enforced in **all** repos without per-repo setup.

## Design

### 1. Source of truth: 1Password

A Secure Note named `sensitive-terms` in the Realm vault. The note body is the
file, in the scanner's format: one case-insensitive regex per line, `lit:` for a
literal, `#` for comments.

- **Not in git, not even a private repo.** A visibility change, a mirror or an
  accidental push would make it permanent, and a synced folder copies it to every
  device. The list is itself the sensitive thing.
- One item for all repos. Per-repo extras go in `$SENSITIVE_TERMS_FILE` or
  `--terms-file` if ever needed.
- Item history gives an audit trail and rollback for free.

### 2. Materialise it on each machine

The environment scaffolding (`make apply-realm`, plus a standalone
`make sync-sensitive-terms`) writes `~/.config/questkit/sensitive-terms`:

```sh
op read "op://<vault>/sensitive-terms/notesPlain" > "$tmp" && install -m 600 "$tmp" "$dest"
```

- Authenticate with the existing read-only service-account token
  (`OP_SERVICE_ACCOUNT_TOKEN`) on headless machines; interactive `op` on
  workstations.
- Write atomically and only when the content changed; never print the terms.
- `op` or the token missing: keep the existing file, warn loudly, exit 0. The
  hooks stay fail-open, but the scaffolding says it did not sync.
- The `notesPlain` field name is unverified; check it with `op item get`.

### 3. Cover every repo: a global hook dispatcher

Set `core.hooksPath` to a directory holding `pre-commit` and `pre-push` scripts
that run the scanner (and gitleaks), then **chain to the repo's own**
`.git/hooks/<name>`. Chaining is required because `core.hooksPath` replaces
per-repo hooks, and `pre-commit install` refuses to run while it is set.

| Option | Covers | Trade-off |
|--------|--------|-----------|
| Global `core.hooksPath` dispatcher | every repo, clone and agent worktree | invasive; must chain and must fail open when the tools are missing |
| `init.templateDir` | new clones only | misses everything that exists |
| Per-repo `.pre-commit-config.yaml` entries (what questkit does) | that repo, visibly | needs setup in each repo |

Recommendation: the dispatcher as the safety net, plus the visible
`.pre-commit-config.yaml` entry in repos that have collaborators or CI. Git
2.54's config-based hooks could replace the dispatcher later; the installed git
here is 2.43, so that is unverified.

### 4. Distribute the scanner

It is one stdlib-only Python file. Expose it as a console script
(`sensitive-scan`) in questkit's `pyproject.toml`, so `uv tool install questkit`
from the registry puts it on `PATH` for the dispatcher. That ties this to the
Gitea registry work.

### 5. One engine for credentials

A user-level gitleaks config (`GITLEAKS_CONFIG`, `[extend] useDefault = true`),
optionally generated from the same deny-list with one rule per term. gitleaks
does not report how many commits a history rewrite would touch, so the scanner's
`history` mode stays.

### 6. Community lists

They exist for credentials, not for your names. gitleaks' built-in rules and the
secrets-patterns-db regex collection cover credentials; Presidio covers generic
personal data but is heavy, so it suits a one-off audit rather than a hook. A
cheap optional `--builtin` mode for emails, phone numbers, IP addresses and
Swedish personal identity numbers is worth adding. Nothing public can know a name
or an employer.

### 7. Safety properties

- **Never echo a term.** The scanner prints each match's term label, which is the
  regex itself. In CI logs that would publish the list. Add `--redact`, printing
  `term #3`, and use it in CI.
- **Fail open** when no list is configured, so contributors are never blocked.
- **Agents:** a global hook does not stop `--no-verify`. Pair it with the
  git-guardrails skill, and keep an allow-listed push (a runner that pushes only
  `main` and release tags) as the only path to the public remote.

## Acceptance Criteria

- [ ] The deny-list exists only in 1Password and in the 0600 file it is written to; no repository contains it
- [ ] One command materialises it on a machine, atomically, without printing it, and degrades to a warning without `op`
- [ ] A fresh clone and a new agent worktree are scanned on commit and push with no per-repo setup
- [ ] The dispatcher chains to a repo's own hooks, and `pre-commit install` still works in a repo
- [ ] `sensitive-scan` is installable as a console script
- [ ] `--redact` makes the scanner safe to run in CI logs
- [ ] One gitleaks configuration is shared across repos

## Open Questions

- Secure Note or Document item, and which service account may read it?
- Where should a repo-specific allow-list live for known false positives?
- Run the sync on a timer, or only on `make apply-realm`?

## Related

- [[QST-x4zw2--publish-questkit-remote-package-registry-and-tagged-releases]] - public release; the history audit that motivated this

