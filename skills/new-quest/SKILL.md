---
name: new-quest
description: Create or alter a quest (ticket) with the questkit CLI. New quests go through a throwaway worktree, push and PR; alterations (`quest set`/`done`/`scrap`, frontmatter edits) run in place. Use for "create a quest", "new quest", "ticket this", "update/close/reprioritise QST-…", /new-quest. Never implements the quest.
compatibility: Needs git, the questkit `quest` CLI, and `tea` or `gh` for the PR step.
---

# /new-quest

Capture or change the ticket only; implement the quest only if the user also asks.

`S` = `scripts/new-quest.sh` beside this file. Always pass `--in <project>` explicitly, never rely on the working directory. Find the project from the `project:` value in the target log's `.questkit.yaml` (`quest logs` lists them); no project: `--in <dir>`. Ambiguous log: ask.

## Alter an existing quest

In place, no worktree: quest files are single files, so the checkout's other changes stay untouched.

```bash
quest set <id> field=value ... --in <project>   # also: quest done|scrap <id>
```

- `quest schema quest --in <project>` lists valid fields and enum values; body edits go through the file directly.
- `git: auto` logs commit the change themselves. Otherwise leave it uncommitted and say so.
- The user asks to ship it (commit, PR): run **New quest** with slug `<id>-<change>`, repeating the same edit in step 2.

## New quest

`--keep` ("keep the worktree") skips step 5.

### 1. Worktree

From inside the target repo: `S start <slug> [--remote R]`. `<slug>` is the title in kebab-case (lowercase, `[a-z0-9]` runs joined by `-`, at most 40 characters). It prints `WORKTREE`, `REMOTE`, `BASE`, `BRANCH`, `HOOKS`, and one `LOG project=… dir=… git=…` line per quest log.

- Several remotes: the script picks the newest. Pass `--remote` when `AGENTS.md`/docs name a primary.
- `cd $WORKTREE` for the remaining steps.

### 2. Quest

```bash
quest new "<title>" --in <project> --type task --status draft --priority low \
  --tag <tag> --description "<one line>" --body - <<'BODY'
...
BODY
```

- Body: description, questions to answer, suggested approach, related links, open questions. Label unverified claims as unverified.
- Refine with `quest set` as above.
- `HOOKS=inactive`: run `quest format --in <project> && quest validate --in <project>`. Done when validate reports 0 errors.

### 3. Commit

`git: auto` logs commit `quest new`/`quest set` themselves. After any direct file edit run `git status --porcelain` and commit what remains:

```bash
git add <log dir> && git commit -m "quest(<project>): <QST-id>, <title>"
```

Follow the repo's commit and attribution rules.

### 4. Push and PR

`S push`, then `tea pulls create --login <login> --repo <owner>/<repo> --base $BASE --head $BRANCH --title ... --description ...` (Gitea) or `gh pr create --base $BASE --head $BRANCH --title ... --body ...` (GitHub). No authenticated CLI: report the branch instead.

### 5. Purge

Push and PR succeeded, no `--keep`: `S purge <slug>`. The remote branch stays until the PR merges. Push failed: keep the worktree.

## Report

Quest id and path, what changed, and for new quests the branch, PR URL, and whether the worktree was purged or kept.
