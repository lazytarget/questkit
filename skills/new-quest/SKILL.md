---
name: new-quest
description: Capture a quest (ticket) with the questkit CLI in a throwaway worktree, then push and open a PR. Use for "create a quest", "new quest", "ticket this", /new-quest. Capture only; never implements.
---

# /new-quest

Write the ticket in a fresh worktree so the main checkout's uncommitted work stays untouched. Implement the quest only if the user also asks.

`--keep` ("keep the worktree") skips step 6.

Run from the repo whose `quests/` log should hold the quest.

## 1. Worktree

- Remote: the only one, else the one `AGENTS.md`/docs name primary, else after `git fetch --all` the one whose default branch has the newest `git log -1 --format=%ct`.
- Default branch: `git ls-remote --symref <remote> HEAD`, then `git fetch <remote> <branch>`.
- `git worktree add -b quest/<slug> .claude/worktrees/<slug> <remote>/<branch>` (or the repo's documented convention), then `cd` in.

## 2. Quest

```bash
quest new "<title>" --type task --status draft --priority low --tag <tag> \
  --description "<one line>" --body - <<'BODY'
...
BODY
```

- `quest schema quest` lists valid enum values.
- Body: description, questions to answer, suggested approach, related links, open questions. Label unverified claims as unverified.
- Refine with `quest set <id> field=value` or edit the frontmatter.

## 3. Hooks

Questkit hooks (`quest-format`, `quest-validate`) absent from `.pre-commit-config.yaml` or `.git/hooks`: run `quest format && quest validate`. Done when validate reports 0 errors.

## 4. Push

```bash
git add quests && git commit -m "quest(<project>): <QST-id>, <title>"
git push -u <remote> quest/<slug>
```

Follow the repo's commit and attribution rules. Push to the primary remote only.

## 5. PR

`tea pulls create --login <login> --repo <owner>/<repo> --base <branch> --head quest/<slug> --title ... --description ...` (Gitea), or `gh pr create --base ... --head ... --title ... --body ...` (GitHub). No authenticated CLI: report the branch instead.

## 6. Purge

Push and PR succeeded, no `--keep`:

```bash
cd <repo root> && git worktree remove .claude/worktrees/<slug> && git branch -D quest/<slug>
```

The remote branch stays until the PR merges. Push failed: keep the worktree.

## Report

Quest id and path, branch, PR URL, worktree purged or kept.
