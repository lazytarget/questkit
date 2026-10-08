---
id: QST-kxo5m
title: designated-committer timer, and git:auto unification
description: designated-committer timer, and git:auto unification
project: questkit
type: feature
status: todo
priority: medium
tags:
  - questkit
  - cli
  - git
  - automation
created: 2026-08-22
modified: 2026-08-22
agentic: afk
aliases:
  - QST-kxo5m
blocked_by:
  - QST-e6g6t
effort: m
milestone: 0.5.0
tier: brief
---

## Description

Split out of [[QST-e6g6t--quest-commit-and-the-designated-committer]], whose Log flagged both
pieces as deliberately left open rather than marked done by assumption: neither is
testable or deployable from within this repository, and `git: auto` unification is a
real refactor with real regression surface, not a drive-by rename. `quest commit`
itself, `tracked:`, `quest validate --report`, and the `.gitignore` handling all
shipped in v0.3 (QST-e6g6t) — this quest is the remaining two items, deferred to
give `quest commit` a release of real-world use before anything is built on top of
it.

## Spec

### Scope

**In:** reimplementing `git: auto` on top of `quest commit`, and deploying the
realm-prod-01 systemd timer.
**Out:** Pensieve integration (a `TimedSummons` Niffler once Pensieve is deployed;
systemd until then) — unchanged from QST-e6g6t's own scope.

### `git: auto` → `quest commit`

Reroute `new_cmd`/`set_cmd`/`mv_cmd`/`migrate_cmd`'s existing `gitutil.auto_commit`
call sites onto `commands.commit_cmd.commit_one`, so there is one commit path instead
of two. **The catch, and the reason this is its own quest**: every prior batch's
tests assert on the exact message format `gitutil.auto_commit` produces today
(`quest(<log-dir-name>): new <id> <title>`, `quest(<log-dir-name>): update <id>`,
...), which is a different shape from `quest commit`'s frontmatter-diff-derived
message (`quest(<project>): add 1` / `~ <id>  status: a → b`). Unifying the two
means either changing `quest commit`'s message format to match single-file semantics,
or updating every one of those assertions to the new format — a real audit, not a
rename.

### The realm-prod-01 timer

The full snippet and quiescence rationale are already written in
[[QST-e6g6t--quest-commit-and-the-designated-committer]]'s Spec (a systemd
unit, `*/15`, whole-log quiescence via `find ... -mmin -10`, `quest format` →
`quest validate --report ... || true` → `quest commit --no-verify`). This quest is
the deployment: provisioning `realm-prod-01` itself (a new VM/LXC syncing the whole Realm),
installing the timer unit, and flipping the quest-only logs (`family`,
`realm-common`, `grocy-ecosystem`) to `git: manual` so realm-prod-01 becomes the genuine
sole git writer.

## Acceptance Criteria

- [ ] `git: auto` is implemented via `quest commit`, and every prior batch's
      auto-commit message assertion is updated to match (or `quest commit`'s message
      format is adjusted to preserve them — pick one, don't leave both shapes live)
- [ ] The realm-prod-01 timer runs unattended and skips a log edited in the last N minutes
- [ ] `family`, `realm-common`, `grocy-ecosystem` are flipped to `git: manual`

## Log

- 2026-08-22: captured. Split out of [[QST-e6g6t--quest-commit-and-the-designated-committer]] and retargeted to `milestone: 0.5.0`, so v0.3 isn't blocked on infrastructure outside this repository.
- 2026-09-02: the host this quest waits on now exists. `realm-prod-01`
  (Proxmox VM, VMID 310, `192.168.50.100`, 2 vCPU / 4 GB / 8 GB) was
  provisioned by Terraform and converged by Ansible from
  `02-projects/lazytarget/home-lab` (stack `prod/realm`, group `realm_hosts`,
  deploy group `realm-host`). Syncthing 2.1.3 is running against
  `/home/gitops/realm`; the box is on the tailnet as
  `realm-prod-01.moose-viper.ts.net`. The naming is locked as
  **`realm-prod-01`** — the earlier working name `realm-01` broke home-lab's
  `<role>-<environment>-<index>` convention, and this quest's slug deliberately
  carries no hostname at all so a future rename cannot invalidate it. Design
  record: home-lab `docs/architecture/realm-domain.md`; Realm-side decision
  D13 in `99-system/docs/syncthing-git-strategy.md`.
  Still outstanding before the timer itself can be built: the host has no
  Gitea-authorized SSH identity (so it cannot yet clone or push), and `tea` is
  not logged in there — both are what this quest's committer role depends on.
