---
id: QST-xlvml
title: Generate an AGENTS md section from the merged schema
project: questkit
type: feature
status: draft
priority: medium
tags:
  - questkit
  - agentic
  - dx
created: 2026-08-22
modified: 2026-10-16
agentic: hitl
aliases:
  - QST-xlvml
blocked_by: []
component:
milestone:
related_adrs:
---

## Notes (draft)

`quest init --agents`: generate/refresh a managed block in the repo's
AGENTS.md from the merged schema. Sentinel comments
(`<!-- questkit:begin -->` / `<!-- questkit:end -->`): replace only
between them, append the block when absent, create the file when
missing — hand-written content outside the markers is never touched.
Content: vocabulary, custom fields, views, commit convention,
report-back commands. `--check` mode for drift detection (doctor/CI).

Open: target the repo-root AGENTS.md (walk up, like `--hooks`) or a
file beside the log — leaning repo root.

To be revisited together with other Omnigent/Realm workflow
improvements, in a separate AI session (per review 2026-08-22).

From R&D catalog AX-5.

## Log

- 2026-08-22: captured from R&D catalog AX-5 (draft, hitl — revisit with Realm workflow improvements)

