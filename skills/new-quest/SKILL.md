---
name: new-quest
description: Capture a quest (ticket) with the questkit CLI in a throwaway worktree, then push and open a PR. Use for "create a quest", "new quest", "ticket this", /new-quest. Capture only; never implements.
compatibility: Needs git, the questkit `quest` CLI, and `tea` or `gh` for the PR step.
---

# /new-quest

Write the ticket in a fresh worktree so the main checkout's uncommitted work stays untouched. Implement the quest only if the user also asks. `--keep` ("keep the worktree") skips step 6.

`S` = `scripts/new-quest.sh` beside this file.

## 1. Worktree

Run from inside the target repo: `S start <slug> [--remote R]`. It prints `WORKTREE`, `REMOTE`, `BASE`, `BRANCH`, `HOOKS`, and one `LOG project=… dir=… git=…` line per quest log.

- Several remotes: the script picks the newest. Pass `--remote` when `AGENTS.md`/docs name a primary.
- `cd $WORKTREE` for the remaining steps.

## 2. Quest

Pick the log: the `LOG` line whose `project` matches the quest's subject (one log: that one; ambiguous: ask). Always pass it explicitly, never rely on the working directory: `--in <project>`, or `--in <dir>` when `project` is empty.

```bash
quest new "<title>" --in <project> --type task --status draft --priority low \
  --tag <tag> --description "<one line>" --body - <<'BODY'
...
BODY
```

- `quest schema quest --in <project>` lists valid enum values.
- Body: description, questions to answer, suggested approach, related links, open questions. Label unverified claims as unverified.
- Refine with `quest set <id> field=value --in <project>` or edit the frontmatter.

## 3. Hooks

`HOOKS=inactive`: run `quest format --in <project> && quest validate --in <project>`. Done when validate reports 0 errors.

## 4. Commit

`git: auto` logs commit `quest new`/`quest set` themselves. After any direct file edit run `git status --porcelain`, and commit what remains:

```bash
git add <log dir> && git commit -m "quest(<project>): <QST-id>, <title>"
```

Follow the repo's commit and attribution rules.

## 5. Push and PR

`S push`, then `tea pulls create --login <login> --repo <owner>/<repo> --base $BASE --head $BRANCH --title ... --description ...` (Gitea) or `gh pr create --base $BASE --head $BRANCH --title ... --body ...` (GitHub). No authenticated CLI: report the branch instead.

## 6. Purge

Push and PR succeeded, no `--keep`: `S purge <slug>`. The remote branch stays until the PR merges. Push failed: keep the worktree.

## Report

Quest id and path, branch, PR URL, worktree purged or kept.
