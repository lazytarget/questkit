---
id: QST-z9og3
title: ICS feed for due-dated quests
project: questkit
type: feature
status: draft
priority: low
tags:
  - questkit
  - integrations
  - calendar
created: 2026-08-22
modified: 2026-10-16
agentic:
aliases:
  - QST-z9og3
blocked_by: []
component:
milestone:
related_adrs:
---

## Notes (draft)

`quest ics [--out FILE]`: emit an iCalendar feed of due-dated quests.
**No hosting required** — an .ics is a file: Syncthing carries it;
ICSx5 (Android, F-Droid) subscribes to a local file into the system
calendar; Thunderbird/GNOME Calendar subscribe to a file path; Home
Assistant's local-calendar/ICS integrations can read it — which
quietly provides the R&D MOB-3 due-notification path without questkit
knowing HA exists.

Worth building only after the due-derived fields (QST-nij1y) make
`due:` actually used — captured as a draft so it is not forgotten.

From R&D catalog INT-2.

## Log

- 2026-08-22: captured from R&D catalog INT-2 (draft, priority low, no milestone)

