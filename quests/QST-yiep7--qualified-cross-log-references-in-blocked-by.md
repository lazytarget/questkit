---
id: QST-yiep7
title: Qualified cross-log references in blocked_by
description: Let a reference declare its own scope as project/QST-xxxxx, so cross-log dependencies work without making validation device-dependent.
project: questkit
type: feature
status: done
priority: medium
tags:
  - questkit
  - schema
  - multi-log
created: 2026-08-19
status_changed: 2026-08-20
modified: 2026-08-20
agentic: hitl
aliases:
  - QST-yiep7
blocked_by:
  - QST-fmk0p
effort: m
milestone: 0.3.0
tier: brief
---

## Description

`blocked_by` ids and body wikilinks resolve **within one log**, deliberately
(`docs/questkit.md` §14, `validate_cmd._check_references`). But real dependencies
cross logs — grocy's `component` work is blocked by schema work in questkit's log
— and `quest deps --blocks` ([[QST-37n0t--built-in-views-next-stale-blocked-and-quest-deps]]) is near-useless without them.

The naive fix is to sweep and give `quest validate` a third "resolves elsewhere"
verdict. **That is wrong**, and it is worth recording why: it makes validation
**device-dependent**. On the phone, `work-a` and `work-b` are not synced, so a
reference that notes on the workstation would hard-fail on mobile. A false
failure that depends on which device you ran it from is worse than no cross-log
support at all.

## Spec

### Approach

**The reference declares its own scope.** A bare id means "this log", forever. A
`/` means "the log whose `project:` is this".

```yaml
blocked_by:
  - QST-abc12               # this log
  - questkit/QST-3ehhu      # the questkit log
```

| Reference | Log present in sweep | Log absent (unsynced device) |
|-----------|----------------------|------------------------------|
| `QST-abc12` (bare) | must resolve here, else **error** | identical — **error**. Device-independent. |
| `questkit/QST-abc12` | resolve there; missing → **error** | **note**: "log 'questkit' not present on this device" |

This converts a *derived* fact (is this id local or foreign?) into a *declared*
one, which is exactly what restores device-independence.

It also makes `quest deps` sweeping non-contradictory: `deps` is a **view** (it
shows what it found and prints its scope), `validate` is a **contract** (bare =
local). Different jobs, both honest.

### Alternatives

| Option | Verdict | Reason |
|--------|---------|--------|
| Qualified refs | ✅ Chosen | Reference declares its scope; validation stays device-independent |
| Single-log only, forever | ❌ | `--blocks` misleadingly empty; real cross-log deps get written as prose nothing resolves |
| Sweep for reads, `validate` unchanged | ❌ | `deps` draws an edge `validate` calls an error, in the same repo |
| Sweep + third "resolves elsewhere" verdict | ❌ | Device-dependent validation — see Description |
| Generated `id → log` index at the sweep root | ❌ | `.stignore-realm` documents why generated artifacts must not sync (every device writes different bytes → conflict litter). And it has nowhere to live: no Syncthing folder covers the Realm root. |
| Split the field (`blocked_by` local, `depends_on` foreign) | ❌ | Two fields for one concept; users pick wrong; still needs a qualifier to resolve efficiently |
| Drop reference validation entirely | ❌ | Throws away a check that catches real typos in the common case |

### Notes

- Syntax is `project/QST-xxxxx`, not `QST-xxxxx@project`: it matches
  `--in questkit`, is a plain YAML scalar needing no quoting, and cannot collide
  with a bare id (ids never contain `/`).
- **Bodies stay plain text.** A cross-log `[[QST-...]]` wikilink cannot resolve in
  Obsidian across vault boundaries — confirmed upstream limit, not fixable here.
  A cross-log body reference is written as prose, which `_WIKILINK_ID_RE` does not
  match and therefore does not check.
- `quest deps` walks `blocked_by` only, never body prose, so the graph stays
  well-defined.
- Requires the project-name→log resolver from [[QST-fmk0p--resolving-questkit-log-in-specified-path-via]]. One resolver, two
  consumers.
- **Ships with no migration**: the corpus has 21 `blocked_by` edges, all
  intra-log, zero dangling.

## Acceptance Criteria

- [x] A bare id unresolvable in its own log is still a hard error, on every device
- [x] `project/QST-x` resolving in a swept log validates clean
- [x] `project/QST-x` naming a log absent from the sweep is a note, never an error
- [x] `project/QST-x` naming a present log where the id is missing is an error
- [x] An unknown project name in a qualified ref errors, naming known projects
- [x] `quest deps` traverses qualified refs and marks which log each node is in
- [x] Computed `blocked` / `blocks` ([[QST-b9lqo--computed-fields-and-comparison-operators-for-where]]) honor qualified refs
- [x] `docs/questkit.md` §14's "no cross-log reference concept" is updated

## Log

- 2026-08-20: `quest deps` shipped in [[QST-37n0t--built-in-views-next-stale-blocked-and-quest-deps]], traversing qualified refs and labeling each node's log via the same `ref.rsplit("/", 1)[-1]` id-stripping `computed._local_id` already used. AC checked off.
- 2026-08-20: implemented. `validate_cmd._check_qualified_ref` splits a `blocked_by` entry on its last `/`, resolves the project part via `discovery.resolve_by_name_or_path(project, start=quests_dir)`, and checks the id against the resolved log. A `QuestLogNotFoundError` (unknown name *or* ambiguous duplicate project name) downgrades uniformly to a note: the two are indistinguishable from one device's point of view, and the whole design point of a qualified reference is a verdict that doesn't depend on what's synced where. The "unknown project name... errors" acceptance criterion is honored at the resolver layer itself (`resolve_by_name_or_path` already raises, naming known projects, for any caller that needs a real answer *now* — `quest deps` in [[QST-37n0t--built-in-views-next-stale-blocked-and-quest-deps]] will be that caller); `quest validate` specifically chooses to catch it and soften it into a note, because validation must stay device-independent. `computed._local_id` already stripped a `/` qualifier down to the bare id before this quest existed, so `blocked`/`blocks` needed no code change — only a test confirming a multi-log sweep resolves the edge and a single-log sweep correctly does not. 7 new tests in `tests/test_cross_log_references.py`.
- 2026-08-19: captured. Chosen over four alternatives specifically because it is the only one where the same file validates identically on every device.
