---
id: QST-fmk0p
title: Resolve a quest log by project name via --in
description: Let --in accept a log's project name, not just a path, so targeting the right log stops depending on remembering a deep nested path.
project: questkit
type: feature
status: todo
priority: high
tags:
  - questkit
  - cli
  - dx
  - multi-log
created: 2026-08-16
status_changed: 2026-08-19
modified: 2026-08-20
agentic: afk
aliases:
  - QST-fmk0p
blocked_by: []
effort: s
milestone: 0.3.0
tier: brief
---

## Description

`--in` accepts a directory path only. In a seven-log vault the paths are long and
nested — `02-projects/lazytarget/pensieve/quests`,
`02-projects/peter/2026-career-transition/quests` — and they move whenever
`02-projects` is reorganized. **The friction is that log identity is currently a
path**, and paths are the thing humans and agents get wrong.

This is the highest-leverage small change on the v3 board: [[QST-iqwjm--multi-log-query-ux-all-logs-repeatable-in-and-root-per-log-grouping-summary-block]] (repeatable
`--in`) and [[QST-yiep7--qualified-cross-log-references-in-blocked-by]] (qualified cross-log references) both need the same
project-name→log resolver. One resolver, three consumers.

## Spec

### Scope

**In:** name resolution for a single `--in` value, uniqueness enforcement, and the
error messages.
**Out:** repeatable `--in` ([[QST-iqwjm--multi-log-query-ux-all-logs-repeatable-in-and-root-per-log-grouping-summary-block]]), reference qualification ([[QST-yiep7--qualified-cross-log-references-in-blocked-by]]).

### Approach

**One rule:** a value containing a `/` or `\`, or naming a directory that exists
on disk, is a **path**. Anything else is a **project name**, matched against each
discovered log's `project:` under the sweep root.

```
quest new "..." --in family                        # by name
quest new "..." --in grocy-ecosystem               # by name
quest list --in 99-system/quests                   # by path, unchanged
quest list --in ./quests                           # by path, unchanged
```

**`project:` becomes identity, not a label.** Unique per log, enforced by
[[QST-3ehhu--quest-logs-inventory-every-quest-log-under-a-root]] and by `quest validate`. A duplicate `project:` across two logs is an
error. The seven existing logs already satisfy this. The alternative — treating
`project:` as a free label and prompting to disambiguate — would build an
interactive path into a tool that pipes into agents.

**A path that is not itself a log expands to the logs beneath it.** Resolution
order for a path value:

1. The path **is** a log (`.questkit.yaml` present) → that log. Unchanged.
2. Otherwise, sweep downward for logs under it:
   - **read commands** (`list`, views, `deps`, `logs`) → **all** logs found;
   - **write commands** (`new`, `init`) → exactly one, else the existing
     `AmbiguousDestinationError` naming the candidates.

So `--in 02-projects/grocy-ecosystem` resolves the same as
`--in 02-projects/grocy-ecosystem/quests`, `--in ./quests` and `--in .` both work
from a repo root, and `--in .` from the Realm root is honestly equivalent to
`-A`. The read/write asymmetry is not new — it is exactly the guard
`resolve_log_for_new` already implements, applied one level up.

Note this sweeps **downward** only, while a bare command with no `--in` walks
**up**. Different directions for different things: explicit beats implicit, and
an explicit path means "here and below".

Resolution is scoped to logs discovered under the sweep root
(`resolve_sweep_root()`: explicit `--root`, then `QST_ROOT`, then the git root,
then cwd), reusing `find_all_logs()` and its `DEFAULT_IGNORE_DIRS` pruning.

**Errors must be actionable**, because a name that fails to resolve is the common
mistake:

- unknown name → list the known project names and their paths
- name resolving to two logs → error naming both paths (should be impossible once
  uniqueness is enforced, but the check is cheap and the failure is confusing)
- a path that is not a log → the existing message, unchanged

Note the resolution set is **device-dependent** — `work-a` and `work-b` do not
sync to the phone, so `--in work-a` cannot resolve there. The error should say
"no log named 'work-a' under /home/gitops/realm" rather than implying the name is
wrong.

### Alternatives

| Option | Verdict | Reason |
|--------|---------|--------|
| Path-or-name, disambiguated by `/` and disk check | ✅ Chosen | No new flag, no ambiguity, backward compatible |
| A separate `--project` flag | ❌ | Two flags for one concept; every call site would have to choose |
| Names only, drop path support | ❌ | Breaks `--in ./quests` and every existing script and doc |
| Prompt on ambiguity | ❌ | Interactive prompts in a tool that is piped into agents |

## Acceptance Criteria

- [ ] `--in family` resolves to `02-projects/family/quests`
- [ ] `--in ./quests` and `--in 99-system/quests` still resolve as paths
- [ ] `--in 02-projects/grocy-ecosystem` resolves to its single child log
- [ ] `--in .` from a repo root resolves to that repo's log
- [ ] A directory containing several logs expands to all of them for reads
- [ ] The same directory errors for `quest new`, naming the candidate logs
- [ ] An existing directory name that is also a project name resolves as the path
- [ ] An unknown name errors, listing known project names with their paths
- [ ] A name matching two logs errors, naming both
- [ ] `quest validate` flags a duplicate `project:` across logs
- [ ] Name resolution respects `--root` / `QST_ROOT`
- [ ] Works on every command that takes `--in`, including mutations
- [ ] Docs describe the path-vs-name rule in one sentence

## Log

- 2026-08-16: captured
- 2026-08-19: groomed as part of [[QST-bmzl2--questkit-v3-loop-closure-multi-log-ux-and-agent-handoff]]. Retitled from "Resolving `Single()` Questkit Log in specified path via `--in`"; the filename slug is intentionally left alone (filenames are immutable by design) — see [[QST-ombky--quest-validate-reports-informational-slug-drift-as-a-hard-error]] for why the resulting drift should not be an error.
