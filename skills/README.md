# questkit skills

Agent skills (Claude Code format: one directory per skill with a `SKILL.md`)
that wrap common questkit workflows. Copy or symlink a skill directory into
`~/.claude/skills/` (user-wide) or a repo's `.claude/skills/` to use it.

| Skill | Invoke | What it does |
| --- | --- | --- |
| [new-quest](new-quest/SKILL.md) | `/new-quest` | Capture a quest in a fresh worktree + branch, push, open a PR, and purge the local worktree (opt out to keep it). |

## Adding a skill

1. Create `skills/<name>/SKILL.md` with `name` and `description` frontmatter.
2. Add a row to the table above.
3. Mention it in the main [README](../README.md) if it is user-facing.
