---
id: QST-lxwag
title: Termux widget capture on Android
project: questkit
type: feature
status: draft
priority: low
tags:
  - questkit
  - mobile
  - capture
created: 2026-08-22
modified: 2026-08-22
agentic: hitl
aliases:
  - QST-lxwag
blocked_by: []
component:
milestone:
related_adrs:
---

## Notes (draft)

Termux:Widget capture: executable scripts in `~/.shortcuts/` appear as
a home-screen widget (`~/.shortcuts/tasks/` variants run without
opening a terminal); with Termux:API, `termux-dialog text` gives a
native input prompt.

    #!/data/data/com.termux/files/usr/bin/bash
    title=$(termux-dialog text -t "New quest" | jq -r '.text')
    [ -n "$title" ] && quest new "$title" --in <log>

Prereqs per device: Termux + Termux:Widget + Termux:API from F-Droid
(Play Store builds have a different signature and cannot mix),
`pkg install termux-api jq python`, questkit installed, Syncthing
Android syncing the target log. A power-user surface, not the family's.

From R&D catalog MOB-4.

## Log

- 2026-08-22: captured from R&D catalog MOB-4 (draft, hitl, priority low)
