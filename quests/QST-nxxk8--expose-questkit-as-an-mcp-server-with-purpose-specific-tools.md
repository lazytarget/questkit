---
id: QST-nxxk8
title: Expose questkit as an MCP server with purpose-specific tools
project: questkit
type: task
status: draft
priority: medium
tags:
  - mcp
  - cli
  - integration
created: 2026-09-21
modified: 2026-09-21
agentic:
aliases:
  - QST-nxxk8
blocked_by: []
component: cli
milestone:
related_adrs:
---

## Description

Expose a subset of questkit's CLI surface as MCP tools, so agents can create and query quests
through a defined tool interface rather than by shelling out to `quest` and parsing stdout.

Captured while studying for CCAR-F: §6 · TS 2.1 of the exam blueprint is about designing tool
interfaces whose descriptions are unambiguous enough for a model to select correctly, and questkit
is a natural subject. The exam objective and a plausible questkit feature are the same work.

## Spec

**Scope.** Lean core, consistent with questkit's existing philosophy — a small number of
purpose-specific tools, not one generic `quest` tool carrying a verb argument. A generic tool would
reproduce exactly the misrouting problem TS 2.1 describes.

Candidate tools, to be narrowed during design:

- `create_quest` — new quest in the nearest opted-in log, or a named log.
- `search_quests` — query by status, tag, project, or text.
- `get_quest` — fetch one quest by ID, with body.
- `update_quest_status` — the single mutation worth exposing; everything else stays CLI-only.

**Tool description requirements** (this is the point of the exercise). Each description must state
purpose, input formats, at least one example invocation, edge cases, and explicitly when to use it
rather than the neighbouring tool. `search_quests` versus `get_quest` is the pair most at risk of
ambiguity.

**Error contract.** Structured errors per TS 2.2, not bare strings: an `errorCategory`
(transient / validation / business / permission), an `isRetryable` boolean, and a human-readable
description. Critically, a search that legitimately matches nothing must be distinguishable from a
log that could not be read — a valid empty result is not an access failure.

**Open questions.**

- Transport and packaging: does this ship inside questkit, or as a sibling `questkit-mcp`?
- Does `update_quest_status` need a gate, given questkit's git-auto behaviour in some logs?
- Scoping: project-level `.mcp.json` for the Realm, or user-level?

## Acceptance Criteria

- [ ] Tool set agreed and deliberately minimal; rationale recorded
- [ ] Each tool description carries purpose, input formats, an example, edge cases, and a
      when-to-use-instead-of note
- [ ] Structured error responses with category and retryable flag
- [ ] Valid empty results distinguishable from access failures
- [ ] Server registered and exercised from a real Claude Code session
- [ ] Decision recorded on packaging (in-repo vs sibling repo)

## Log

- 2026-09-21: captured while studying CCAR-F Domain 2 (TS 2.1 tool interfaces, TS 2.2 structured
  error responses); spec drafted from those objectives
