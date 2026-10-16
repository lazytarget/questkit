# questkit skills

Harness-neutral [Agent Skills](https://agentskills.io) (one directory per
skill: `SKILL.md`, optional `scripts/`) that wrap common questkit workflows.
Copy or symlink a skill directory into your harness's skills directory (for
example `~/.claude/skills/`, `~/.agents/skills/`) to use it.

| Skill | Invoke | What it does |
| --- | --- | --- |
| [new-quest](new-quest/SKILL.md) | `/new-quest` | Capture a quest in a fresh worktree + branch, push, open a PR, and purge the local worktree (opt out to keep it). |

## Adding a skill

1. Create `skills/<name>/SKILL.md` with `name` (matching the directory) and `description` frontmatter; put helper scripts in `skills/<name>/scripts/`.
2. Add a row to the table above.
3. Mention it in the main [README](../README.md) if it is user-facing.
