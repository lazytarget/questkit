---
id: QST-nxxk8
title: Expose questkit as an MCP server with purpose-specific tools
project: questkit
type: task
status: todo
priority: medium
tags:
  - mcp
  - cli
  - integration
created: 2026-09-21
status_changed: 2026-10-01
modified: 2026-10-02
agentic: afk
aliases:
  - QST-nxxk8
blocked_by: []
component: cli
milestone:
related_adrs:
description: MCP server (quest mcp) exposing purpose-specific quest tools with an explicit log parameter and structured errors, so agents stop shelling out to quest
---

## Description

Expose a subset of questkit's CLI surface as MCP tools, so agents can flexibly discover, create, query, and mutate quests through a defined tool interface rather than by shelling out to `quest` and parsing stdout.

Captured while studying for CCAR-F: §6 · TS 2.1 of the exam blueprint is about designing tool
interfaces whose descriptions are unambiguous enough for a model to select correctly, and questkit
is a natural subject. The exam objective and a plausible questkit feature are the same work.

## Spec

**Architecture & Packaging:** 
- The server will ship in-repo as a subcommand: `quest mcp`.
- Built in Python (using `FastMCP` or equivalent standard SDK) to natively invoke `questkit` libraries without shelling out.
- Transport: `stdio` only for now (local clients like Claude Code/Cursor). A network transport is deferred; if added later it should be Streamable HTTP (SSE is deprecated in MCP), with authentication or bound to localhost.
- Least-Privilege: Implement a `--read-only` flag for `quest mcp` that explicitly disables all mutation tools.

**Scope.** Lean core, consistent with questkit's existing philosophy — a small number of
purpose-specific tools, not one generic `quest` tool carrying a verb argument. A generic tool would
reproduce exactly the misrouting problem TS 2.1 describes.

Defined Tools. Every tool except `list_quest_logs` takes a required `log` parameter (a name or path from `list_quest_logs`). There is no implicit "nearest log": a stdio server's working directory is wherever the client launched it, not where the agent is working.

- `list_quest_logs` — Discovers all opted-in quest logs across the workspace (starting from `QST_ROOT`). Returns an array of logs containing the Project name, full absolute path, total number of quests, and the number of active quests matched by the default `quest list` view.
- `get_quest_schema` — Retrieves the dynamically merged `.questkit.yaml` schema for a specific quest log. Crucial for agents to introspect required fields and valid enums *before* creating or mutating quests.
- `create_quest` — Creates a new quest in the log named by `log`. The tool description must explicitly outline Markdown formatting rules (e.g., requiring a `## Acceptance Criteria` section with `- [ ]` checkboxes).
- `search_quests` — Query by status, tag, project, or text. Includes `draft` quests by default, consistent with `quest list` including drafts, and echoes the filters it applied so an empty result can't be mistaken for "no such quest". Must return a clear `"Results: 0 found"` string on valid empty results rather than throwing an exception.
- `read_quest_by_id` — Fetch one quest by ID, with its full markdown body. The description MUST explicitly enforce: *"If you do not have the exact QST-xxxxx ID, you MUST use `search_quests` first."*
- `update_quest_frontmatter` — Accepts a quest ID and a JSON object of key-value pairs. Validates the provided fields against the active `.questkit.yaml` dynamic schema before saving.
- `update_quest_body` — Accepts a quest ID and a full markdown string to replace the quest's body. 
- `append_quest_log` — Atomically appends a time-stamped entry to the `## Log` section of a quest's markdown body. Prevents full-document rewrites for simple status updates.
- `validate_quest` — Runs `questkit`'s strict validation pipeline against a specific quest ID and returns a list of errors and warnings. Ideal for agents verifying their AFK formatting before finishing a turn.

**Git Auto-Commit Behavior:**
If `questkit` triggers an automatic background commit due to a log's `git: auto` config during an MCP mutation, the commit message must include the Git trailer `Auto-Commit: Questkit v{version}` to ensure auditability of autonomous actions.

**Error contract.** 
Always use structured errors per TS 2.2, not bare strings. The tool handler must wrap exceptions and return a JSON payload within the text content containing:
- `errorCategory` (transient / validation / business / permission)
- `isRetryable` (boolean)
- A human-readable description.
Critically, a search that legitimately matches nothing must be distinguishable from a log that could not be read — a valid empty result is not an access failure.

## Acceptance Criteria

- [ ] Tool set implemented as specified: `list_quest_logs`, `get_quest_schema`, `create_quest`, `search_quests`, `read_quest_by_id`, `update_quest_frontmatter`, `update_quest_body`, `append_quest_log`, `validate_quest`.
- [ ] Each tool description carries purpose, input formats, an example, edge cases, and a when-to-use-instead-of note.
- [ ] Always return structured error responses with category and retryable flag on failures.
- [ ] Valid empty search results return gracefully without triggering error routines.
- [ ] Implemented as an in-repo subcommand (`quest mcp`) with `stdio` transport.
- [ ] `--read-only` flag implemented, successfully blocking all creation and update tools.
- [ ] Git trailer `Auto-Commit: Questkit v{version}` appended on autonomous `git: auto` commits.
- [ ] Server registered and exercised from a real Claude Code or Cursor session.

## Log

- 2026-09-21: captured while studying CCAR-F Domain 2 (TS 2.1 tool interfaces, TS 2.2 structured
  error responses); spec drafted from those objectives.
- 2026-10-01: promoted draft → todo; overrides the AX-6 "defer" disposition in
  `docs/planning/rd_ideas_2026-08-21.md`
- 2026-10-02: finalized architectural decisions (Python FastMCP, `--read-only` flag, explicit tool naming to prevent LLM misrouting, Git trailer adoption). Expanded mutation surface to include full frontmatter dictionary and body updates. Added tools for workspace discovery, schema introspection, log appending, and discrete validation to enable complete agent autonomy.
- 2026-10-02: merged a Syncthing conflict with the 2026-10-01 promotion. Decided: a required
  `log` parameter on every log-scoped tool (no nearest-log resolution), and `search_quests`
  includes `draft` like `quest list` should.
- 2026-10-02: decided `stdio` only for the first implementation; SSE dropped.
- 2026-10-02: decided against content hashes (optimistic locking) on the update tools. They
  would not catch cross-device conflicts like today's Syncthing one, and Git takes over that job.
