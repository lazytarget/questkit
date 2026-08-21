"""`quest brief <id>` — a self-contained, agent-agnostic Markdown work order.

Plain Markdown on stdout: no vendor keys, no JSON envelope, no system-prompt
framing. It describes the work, never the worker.

Two separate verdicts, because they fail for different reasons and have
different fixes: READY (is this document executable as written -- entirely
schema-driven, from the log's own `readiness:` rules, no rule hardcoded
here) and STATE (should anyone pick it up right now -- computed: blocked,
terminal, archived). Only a READY failure collapses the brief to grooming
input; a STATE failure is a warning, never a refusal, because the most
common reason to brief a blocked quest is to hand an agent the thing that
unblocks it.
"""

from __future__ import annotations

import argparse
import sys

from .. import computed, schema
from ..config import ConfigVersionError, QuestLogConfig
from ..discovery import resolve_log_set, resolve_mutation_target, resolve_sweep_roots
from ..gitutil import find_git_root, repo_status
from ..quest import Quest

_LOG_KEY = "__log__"

_SPEC_HEADINGS = ("## Spec", "## Design")
_ACCEPTANCE_HEADING = "## Acceptance Criteria"


def run(args: argparse.Namespace) -> int:
    found = resolve_mutation_target(args.id, explicit_in=args.in_dirs)
    if found is None:
        print(f"[quest] no quest matching id '{args.id}' found")
        return 1
    quests_dir, path = found
    config = QuestLogConfig.load(quests_dir)
    quest = Quest.load(path)

    corpus, terminal_by_log = _sweep_corpus(args)
    computed.annotate_rows(corpus, terminal_by_log, _LOG_KEY)
    own_id = quest.get("id")
    own_row = next((row for row in corpus if row.get("id") == own_id), None)
    by_id = {row["id"]: row for row in corpus if row.get("id")}

    lines: list[str] = []
    lines.extend(_header(quest, config))
    lines.append("")
    lines.extend(_location(quests_dir, path, config))

    ready_failures = schema.evaluate_readiness(quest, config.schema)

    if ready_failures:
        lines.append("")
        lines.append("READY")
        for message in ready_failures:
            lines.append(f"  ⚠️  {message}")
        lines.append("  NOT implementation-ready. This is grooming input.")
        print("\n".join(lines))
        _print_scope(args)
        return 0

    lines.append("")
    if quest.get("description"):
        lines.append(quest.get("description"))
        lines.append("")

    if _uses_non_default_schema(config.schema):
        lines.extend(_schema_block(config.schema))
        lines.append("")

    spec_text = _extract_section(quest.body, _SPEC_HEADINGS)
    if spec_text:
        lines.append("SPEC")
        lines.extend(f"  {line}" for line in spec_text.splitlines())
        lines.append("")

    acceptance_text = _extract_section(quest.body, (_ACCEPTANCE_HEADING,))
    if acceptance_text:
        lines.append("ACCEPTANCE")
        lines.extend(f"  {line}" for line in acceptance_text.splitlines())
        lines.append("")

    lines.extend(_dependencies(own_row, by_id, corpus))
    lines.append("")
    lines.extend(_report_back(quest, quests_dir, config))
    lines.append("")
    lines.append("READY  ✅ all readiness rules satisfied")
    lines.extend(_state_line(quest, own_row, by_id, config))

    print("\n".join(lines))
    _print_scope(args)
    return 0


def _header(quest: Quest, config: QuestLogConfig) -> list[str]:
    meta = [str(quest.get("type") or ""), str(quest.get("status") or ""), str(quest.get("priority") or "")]
    for field_name in ("effort", "tier", "agentic", "owner"):
        value = quest.get(field_name)
        if value:
            meta.append(f"{field_name}={value}")
    tags = quest.get("tags") or []
    if tags:
        meta.append(",".join(str(t) for t in tags))
    return [
        f"{quest.get('id')} — {quest.get('title')}",
        " · ".join(meta),
    ]


def _location(quests_dir, path, config: QuestLogConfig) -> list[str]:
    lines = ["LOCATION"]
    git_root = find_git_root(quests_dir)
    try:
        quest_rel = path.relative_to(git_root) if git_root else path
    except ValueError:
        quest_rel = path
    lines.append(f"  quest  {quest_rel}")
    lines.append(f"  log    {quests_dir}   project={config.project or '(none)'}  git={config.git}")
    if git_root:
        branch, dirty = repo_status(git_root)
        state = "dirty" if dirty else "clean"
        lines.append(f"  repo   {git_root}   {branch or '(detached)'}, {state}")
    return lines


def _uses_non_default_schema(schema_config: schema.SchemaConfig) -> bool:
    """Whether this log's schema is worth printing -- precisely when a
    reader cannot guess it from the built-in vocabulary alone."""
    if schema_config.fields:
        return True
    for name in ("types", "statuses", "tiers", "priorities", "efforts", "terminal_statuses"):
        if getattr(schema_config, name) != getattr(schema.SchemaConfig.default(), name):
            return True
    return False


def _schema_block(schema_config: schema.SchemaConfig) -> list[str]:
    lines = ["SCHEMA"]
    lines.append(f"  statuses   {list(schema_config.statuses)}")
    lines.append(f"  priorities {list(schema_config.priorities)}")
    for name, spec in sorted(schema_config.fields.items()):
        values = f" {list(spec.values)}" if spec.values else ""
        required = " (required)" if spec.required else ""
        lines.append(f"  {name}: {spec.type}{values}{required}")
    return lines


def _extract_section(body: str, headings: tuple) -> str | None:
    lines = body.splitlines()
    heading_lower = [h.lower() for h in headings]
    start = None
    for index, line in enumerate(lines):
        if line.strip().lower() in heading_lower:
            start = index + 1
            break
    if start is None:
        return None
    collected = []
    for line in lines[start:]:
        if line.strip().startswith("## "):
            break
        collected.append(line)
    text = "\n".join(collected).strip("\n")
    return text or None


def _dependencies(own_row: dict | None, by_id: dict, corpus: list[dict]) -> list[str]:
    lines = ["DEPENDENCIES"]
    refs = (own_row or {}).get("blocked_by") or []
    if not refs:
        lines.append("  blocked_by  (none)")
    else:
        lines.append("  blocked_by")
        for ref in refs:
            target_id = str(ref).rsplit("/", 1)[-1]
            target = by_id.get(target_id)
            if target is None:
                lines.append(f"    {ref}  (not found in the current sweep)")
            else:
                lines.append(f"    {target_id}  {target.get('status')}  {target.get('__path__')}")

    own_id = (own_row or {}).get("id")
    dependents = [
        row
        for row in corpus
        if own_id and any(str(ref).rsplit("/", 1)[-1] == own_id for ref in (row.get("blocked_by") or []))
    ]
    lines.append(f"  blocks      {len(dependents)} quest{'' if len(dependents) == 1 else 's'}")
    for row in dependents:
        lines.append(f"    {row.get('id')}  {row.get('status')}  {row.get('__path__')}")
    return lines


def _report_back(quest: Quest, quests_dir, config: QuestLogConfig) -> list[str]:
    """`quest done` is always safe -- it reads the schema's own terminal_statuses
    ([[QST-lcsza]] etc. already rely on this). The "start work" line has no
    such schema-driven equivalent: a renamed vocabulary (household.yaml's
    waiting/doing in place of todo/in-progress) has no declared concept of
    which status means "actively being worked". Rather than guess wrong --
    "-progress" not existing in that log's statuses would tell someone to run
    a command that fails -- the line is only ever emitted when the literal
    value is actually one of this schema's own declared statuses.
    """
    quest_id = quest.get("id")
    terminal = config.schema.terminal_statuses
    project = config.project or quests_dir.name
    lines = ["REPORT BACK"]
    if "in-progress" in config.schema.statuses:
        lines.append(f"  quest set {quest_id} status=in-progress")
    lines.append(f"  quest done {quest_id}   # writes status={terminal[0]}")
    lines.append(f"  Notable decisions → the quest's ## Log. Commit prefix: quest({project}):")
    return lines


def _state_line(quest: Quest, own_row: dict | None, by_id: dict, config: QuestLogConfig) -> list[str]:
    status = quest.get("status")
    terminal = config.schema.terminal_statuses
    if status in terminal:
        return [f"STATE  ⚠️  already {status} — briefing it is probably a mistake"]
    if quest.get("archived"):
        return ["STATE  ⚠️  archived — should this still be in front of you?"]
    if own_row and own_row.get("blocked"):
        blocker_id = None
        for ref in own_row.get("blocked_by") or []:
            target_id = str(ref).rsplit("/", 1)[-1]
            target = by_id.get(target_id)
            if target is not None and target.get("status") not in terminal:
                blocker_id = target_id
                break
        blocker = by_id.get(blocker_id) if blocker_id else None
        if blocker:
            return [
                f"STATE  ⚠️  blocked by {blocker_id} ({blocker.get('status')}) "
                "— that quest is the actionable work"
            ]
        return ["STATE  ⚠️  blocked"]
    blocks = own_row.get("blocks", 0) if own_row else 0
    return [f"STATE  ✅ unblocked · blocks {blocks}"]


def _sweep_corpus(args: argparse.Namespace) -> tuple[list[dict], dict[str, tuple]]:
    """Every quest in scope, as plain rows carrying `_LOG_KEY` and their own
    file path -- `brief` needs the whole corpus to resolve `blocked_by` and
    reverse `blocks`, exactly like `quest deps`."""
    logs = resolve_log_set(in_dirs=args.in_dirs, all_logs=not args.in_dirs, root=args.root)
    rows: list[dict] = []
    terminal_by_log: dict[str, tuple] = {}
    for quests_dir in logs:
        try:
            config = QuestLogConfig.load(quests_dir)
        except (ConfigVersionError, schema.SchemaExtendsError, schema.SchemaConfigError):
            continue
        project = config.project or quests_dir.name
        terminal_by_log[project] = config.schema.terminal_statuses
        for path in sorted(quests_dir.glob(config.pattern)):
            fm = Quest.load(path).frontmatter
            row = {key: (list(value) if isinstance(value, list) else value) for key, value in fm.items()}
            row.setdefault("project", project)
            row[_LOG_KEY] = project
            row["__path__"] = str(path)
            rows.append(row)
    return rows, terminal_by_log


def _print_scope(args: argparse.Namespace) -> None:
    roots = resolve_sweep_roots(explicit=args.root)
    print(f"[quest brief] scope: swept from {', '.join(str(r) for r in roots)}", file=sys.stderr)
