---
id: QST-e6g6t
title: quest commit and the designated committer
description: Own the commit convention in the app, give it a bounded pathspec, and make one always-on host the sole git writer for the quest-only logs.
project: questkit
type: feature
status: done
priority: medium
tags:
  - questkit
  - cli
  - git
  - automation
created: 2026-08-19
status_changed: 2026-08-22
modified: 2026-08-22
agentic: afk
aliases:
  - QST-e6g6t
blocked_by:
  - QST-mjuau
effort: m
milestone: 0.3.0
tier: brief
---

## Description

Quests edited in Obsidian on a phone never touch the CLI, so `git: auto` never
fires and their history stops. The fix is a designated always-on machine —
**`realm-prod-01`**, a new VM/LXC syncing the whole Realm and running the Pensieve
daemon — that periodically formats, validates and commits the quest-only logs.

The commit convention (`quest(<project>): ...`) belongs in questkit, not
duplicated across a systemd unit, a Home Assistant `shell_command`, and fingers.
`gitutil.auto_commit` is already 80% of this command: pathspec-limited staging,
pathspec-limited `git commit -- <paths>`, correct handling of already-deleted
paths, and degradation with a warning instead of a failure.

### Measured: pathspec does **not** protect `.git/index`

Worth recording, because it is counterintuitive and it changes the mitigation:

```
baseline index                                     719c9497e7d3
edit files in the worktree (no git command)        719c9497e7d3   unchanged
git commit -m x -- a.md   (no `git add` at all)    dbaffbef9728   REWRITTEN
```

The `auto_commit` sequence rewrites it **twice** (`git add --` then
`git commit --`). Git's partial-commit path stages the named paths into the
**real** index and writes it, then builds a temporary index to create the commit
from. `.git/logs/HEAD` grows on every commit too.

So pathspec buys a different property than hoped: **it prevents staging unrelated
files** — code changes stay out of a `quest(...)` commit even if they are already
staged. That is a correctness guarantee, not a Syncthing one.

**The actual mitigation is one git writer per repo.** Which exposes a trap:
`git: auto` means "the CLI commits from whatever device it runs on", so
`quest new --in family` on a workstation *and* the realm-prod-01 timer are two writers
on the same repo — exactly the silently-resolving index race documented in
`.stignore-common` (confirmed in production 2026-08-14).

## Spec

### Scope

**In:** `quest commit`, the `tracked:` config key, `quest validate --report`, the
`.gitignore` entry for `_validation.md`, and the realm-prod-01 timer.
**Out:** Pensieve integration (a `TimedSummons` Niffler once Pensieve is deployed;
systemd until then), and the wider question of whether the code repos should be in
Syncthing folders at all — that is a Realm decision, not questkit's.

### Approach

1. **`quest commit [--in ...]`** stages and commits exactly the log's `tracked:`
   set, via `git commit -- <pathspec>`, which **ignores the index** and so cannot
   sweep in a user's staged code changes.
2. **`tracked:`** config key. Default:
   `[<the log's pattern>, .questkit.yaml, .gitignore, _template.md, quests.base]`.
   `_validation.md` is deliberately **excluded** — it is derived state whose
   transport is Syncthing, not git.
3. **Deterministic message from the frontmatter diff.** No model. Everything a
   good message needs is structurally available:
   ```
   quest(family): add 2, update 1

   + QST-9x2kf  Book the chimney sweep
   + QST-p4m1c  Order gutter cleaning
   ~ QST-3ehhu  status: todo → completed
   ```
4. **`--no-verify` forwarded**, off by default: normal CLI use keeps hook
   enforcement, the timer opts out explicitly so a data-quality problem cannot
   become a history gap at 03:00. When hooks block a commit and `--no-verify` was
   **not** passed, `quest commit` **exits non-zero and prints the hook output** —
   `gitutil.auto_commit` currently swallows this, which on a timer is a silent
   gap.
5. **`--push` opt-in, default off.** Push is a network side effect with
   conflict semantics (non-fast-forward against Gitea from a device that has not
   pulled).
6. **`git: auto` reimplemented on top of `quest commit`** — one commit path
   instead of two.
7. **`quest validate --report FILE`** writes findings as a Markdown note and
   **deletes it when the log is clean**, leaving exit-code semantics alone. The
   timer chooses leniency by appending `|| true`; questkit does not grow a
   `--no-fail` flag someone will later paste into a hook. Notes vs errors per
   [[QST-ombky--quest-validate-reports-informational-slug-drift-as-a-hard-error]].
8. **`quest init` ensures a `.gitignore`** in the log containing `_validation.md`.
   `02-projects/common/quests` and `02-projects/grocy-ecosystem/quests` are their
   own git repos with **no `.gitignore` at all**, so without this the report file
   sits untracked forever, waiting for the first `git add -A`.
9. **Flip the quest-only logs to `git: manual`** (`family`, `realm-common`,
   `grocy-ecosystem`) and give the timer an explicit scope. realm-prod-01 becomes the
   genuine sole git writer; workstations write quest *files*, Syncthing carries
   them, realm-prod-01 commits them.

### Snippets

```bash
# realm-prod-01, systemd timer, */15
LOGS="--in family --in realm-common --in grocy-ecosystem"
find <log dirs> -name 'QST-*.md' -mmin -10 | grep -q . && exit 0   # whole-log quiescence
quest format $LOGS
quest validate $LOGS --report quests/_validation.md || true
quest commit $LOGS --no-verify
```

Quiescence is **whole-log, not per-file**: reformatting file A while someone edits
file B is safe for A, but the commit would capture B mid-thought. Polling *is*
debouncing — which is also why a file watcher is the wrong tool here. realm-prod-01 must
be a machine nobody edits from.

### Alternatives

| Option | Verdict | Reason |
|--------|---------|--------|
| `quest commit` + systemd timer | ✅ Chosen | Convention lives in the app; polling gives debouncing for free |
| Pensieve watcher | ❌ | `strands/watcher.py`'s `is_strand_ready` is a **filename** check (`.tmp`, `~$`), not a settle check, and the dedupe window is 50 ms. Obsidian writes straight to the real filename on every autosave. |
| Pensieve Transfiguration | ❌ | An **ingress** transform that re-injects into a queue; `PLAN.md:25` explicitly forbids writing back into the watched folder. `quest format` is in-place normalization. |
| Pensieve `TimedSummons` | ⏸ Later | The right primitive (interval triggers, coalescing overlap, supervised loop) — but binding to it blocks this behind Pensieve's deployment. Lift after. |
| Derive timer scope from `git: auto` | ❌ | Guarantees two writers rather than partitioning them |
| obsidian-git on phones | ❌ | Another writer into `.git` directories that already lose races; 46 `.sync-conflict` files exist across 15 `.git` dirs today |

## Acceptance Criteria

- [x] `quest commit` stages and commits exactly the `tracked:` set
- [x] Staged, unrelated changes in the same repo are not committed
- [x] The message is derived from the frontmatter diff and is deterministic
- [x] `quest commit` with nothing to commit exits 0 and writes no empty commit
- [x] Hook failure without `--no-verify` exits non-zero and prints hook output
- [x] `--no-verify` is forwarded to git; `--push` is opt-in and off by default
- [x] `quest validate --report FILE` writes the note and deletes it when clean
- [x] `quest init` adds `_validation.md` to the log's `.gitignore`, idempotently
- [ ] ~~`git: auto` is implemented via `quest commit`~~ → split to [[QST-kxo5m--designated-committer-timer-and-git-auto-unification]], `milestone: 0.5.0`
- [ ] ~~The realm-prod-01 timer runs unattended and skips a log edited in the last N minutes~~ → split to [[QST-kxo5m--designated-committer-timer-and-git-auto-unification]], `milestone: 0.5.0`

## Log

- 2026-09-02: the always-on host named throughout this quest exists as of
  today: `realm-prod-01` (VMID 310, `192.168.50.100`), Terraform-provisioned
  and Ansible-converged from `02-projects/lazytarget/home-lab`. The name is
  locked at `realm-prod-01` (the working name `realm-01` broke home-lab's
  `<role>-<environment>-<index>` convention), and this quest's own slug was
  rewritten to drop the hostname so a future rename cannot invalidate it. No
  change to this quest's outcome — it stays closed; the timer remains
  [[QST-kxo5m--designated-committer-timer-and-git-auto-unification]]'s work.
- 2026-08-22: closed for v0.3. The two remaining items (`git: auto` unification, the realm-prod-01 timer) are split out to [[QST-kxo5m--designated-committer-timer-and-git-auto-unification]] at `milestone: 0.5.0` — both are infrastructure/refactor work outside what this repository can deploy or test, and `quest commit` itself needs a release of real-world use before `git: auto` is rebuilt on top of it.
- 2026-08-20: `quest commit`, `tracked:`, `quest validate --report`, and `quest init`'s `.gitignore` handling are implemented and tested (`commands/commit_cmd.py`, `tests/test_commit_cmd.py`, `tests/test_validate_report_and_gitignore.py`). Two acceptance criteria are deliberately left open rather than marked done by assumption: **`git: auto` reimplemented via `quest commit`** would mean rerouting `new_cmd`/`set_cmd`/`mv_cmd`/`migrate_cmd`'s existing `gitutil.auto_commit` call sites onto the new tracked-pathspec-plus-derived-message path, changing the exact commit message format every prior batch's tests assert on (`quest(<log-dir-name>): new <id> <title>` etc.) — a real refactor with real regression surface, not a drive-by rename, and better done as its own reviewed change. **The realm-prod-01 timer** is a systemd unit on a specific always-on host outside this git repository; it cannot be deployed or tested from here. The snippet in this quest's Spec is ready to hand to whoever provisions that machine.
- 2026-08-19: captured. The `.git/index` behavior was measured, not assumed — pathspec was expected to avoid the write and does not.
