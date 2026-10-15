---
name: new-quest
description: >
  Capture a new quest (ticket) with the questkit CLI in a fresh git worktree and
  branch, push it, open a PR, then clean up the local worktree. Use when the user
  says "create a quest", "new quest", "capture a ticket for ...", or invokes
  /new-quest. Capture only: never implements the quest unless also asked.
---

# /new-quest

Capture a quest without disturbing the default checkout. All work happens in a
throwaway worktree, so uncommitted changes in the main checkout stay untouched.

**Scope:** "create a quest" means write the ticket. Do not implement it unless
the user also asks.

**Opt-out:** if the user says "keep the worktree" / "keep local" (or passes
`--keep`), skip step 6 and leave the worktree and branch in place.

## Workflow

Run everything from inside the target repo (the one whose `quests/` log should
hold the quest). Never edit another checkout.

### 1. Fresh worktree + branch from the primary remote

1. Pick the remote: `git remote -v`. If there is one, use it. If there are
   several (e.g. `origin`, `gitea`), prefer the one the repo's docs or
   `AGENTS.md` name as primary (in the Realm: `gitea`). Otherwise run
   `git fetch --all` and pick the remote whose default branch has the newest
   commit (`git log -1 --format=%ct <remote>/<branch>`).
2. Find its default branch: `git ls-remote --symref <remote> HEAD` (usually
   `main` or `master`), then `git fetch <remote> <branch>`.
3. Create the worktree on a branch named `quest/<short-slug>`:

   ```bash
   git worktree add -b quest/<slug> .claude/worktrees/<slug> <remote>/<branch>
   cd .claude/worktrees/<slug>
   ```

   Use the repo's own worktree convention if it documents one.

### 2. Create the quest

```bash
quest new "<title>" --project <project> --type task --status draft \
  --priority low --tag <tag> --description "<one line>" --body - <<'BODY'
## Description
...
BODY
```

- Run `quest schema quest` if unsure which values are valid; never guess enums.
- Write a real body: description, questions to answer, suggested approach,
  related links, open questions. Mark unverified user ideas as such.
- Adjust metadata afterwards with `quest set <id> field=value`, or edit the
  YAML frontmatter directly.

### 3. Format and validate (only if hooks are not enabled)

Check `.git/hooks/pre-commit` and `.pre-commit-config.yaml` for the questkit
hooks (`quest-format`, `quest-validate`). If they are not active, run manually:

```bash
quest format
quest validate
```

Fix any errors before committing.

### 4. Commit and push

```bash
git add quests
git commit -m "quest(<project>): <QST-id>, <short title>"
git push -u <remote> quest/<slug>
```

Follow the repo's commit conventions and attribution rules. Push only to the
primary remote, never to sibling mirrors.

### 5. Open a PR

Use whichever CLI matches the remote host:

```bash
tea pulls create --login <login> --repo <owner>/<repo> \
  --base <branch> --head quest/<slug> --title "<title>" --description "<body>"
# GitHub remotes:
gh pr create --base <branch> --head quest/<slug> --title "<title>" --body "<body>"
```

If no CLI is authenticated for the host, say so and give the user the branch
name instead of improvising.

### 6. Purge local state (default)

Only after the push succeeded (and the PR, if one was opened):

```bash
cd <original repo root>
git worktree remove .claude/worktrees/<slug>
git branch -D quest/<slug>   # -D: not merged locally; the branch lives on the remote
```

Skip this if the user opted out. The remote branch stays; the server removes it
after the PR is merged. If the push failed, keep the worktree so nothing is lost.

## Report

Reply with the quest id and file path, the branch, the PR URL, and whether the
local worktree was purged or kept.
