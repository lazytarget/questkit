"""`quest list` — a dynamic, filterable, multi-log query/export engine."""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from dataclasses import dataclass
from functools import partial
from typing import Any

from .. import computed, query, schema
from ..config import ConfigVersionError, QuestLogConfig
from ..discovery import resolve_log_set
from ..quest import Quest

# `blocked` is gone: it left the status enum (a status value and a computed
# field cannot share a name), and derived-blocked quests stay visible through
# the `todo [blocked]` marking instead of a status nobody maintained by hand.
# QST-37n0t moves this into `views.default`, removing the last hardcoded
# status list rather than replacing it with a config key.
DEFAULT_STATUSES = ("todo", "in-progress")
DEFAULT_COLUMNS = ("id", "status", "priority", "title")

# Internal bookkeeping key carrying each row's resolved log, kept out of every
# user-visible surface (JSON keys, CSV/table columns, --distinct's equality
# key) but read by table grouping. Never a legal --select name -- it isn't in
# CORE_FIELDS or any schema's declared fields.
_LOG_KEY = "__log__"

# The --where grammar itself lives in `query.py` now, so `schema.py`'s
# readiness engine can reuse it without a circular import back onto
# `commands.*`. Re-exported under the historical private names so existing
# call sites (and their tests) are unaffected.
_parse_where = query.parse_where
_matches = query.matches
_is_blank = query.is_blank


@dataclass
class LogInfo:
    """One resolved log's identity and declared field vocabulary."""

    quests_dir: Any
    project: str
    fields: frozenset


def run(args: argparse.Namespace) -> int:
    user_wheres = list(args.where or [])
    wheres = [_parse_where(expr) for expr in user_wheres]
    default_status_injected = not any(field == "status" for field, _, _ in wheres)
    if default_status_injected:
        wheres.append(("status", "eq", ",".join(DEFAULT_STATUSES)))

    rows, sort_schema, valid_fields, logs_info = _collect_rows(args)
    rows = [row for row in rows if all(_matches(row, f, op, v) for f, op, v in wheres)]

    quiet = getattr(args, "quiet", False)
    select = getattr(args, "select", None)
    distinct = getattr(args, "distinct", False)
    count = getattr(args, "count", False)
    summary: list[str] = []

    if distinct and not select:
        print("[quest list] error: --distinct requires --select", file=sys.stderr)
        return 1

    select_fields: list[str] | None = None
    if select:
        select_fields = [f.strip() for f in select.split(",") if f.strip()]
        unknown = [f for f in select_fields if f not in valid_fields]
        if unknown:
            print(
                f"[quest list] error: --select names unknown field(s) {unknown}; "
                f"valid fields: {sorted(valid_fields)}",
                file=sys.stderr,
            )
            return 1
        if len(logs_info) > 1:
            for info in logs_info:
                lacking = [f for f in select_fields if f not in info.fields]
                if lacking:
                    summary.append(f"note   {info.project}: no {lacking} -- blank in output")
        # Projected exactly once, up front -- every renderer downstream (table,
        # csv, json, prompt) then sees the same restricted shape, rather than
        # each one needing its own "did the caller select?" branch. This is
        # what makes --select a widened contract rather than a --columns rename.
        rows = [_project(row, select_fields) for row in rows]

    if distinct:
        rows = _dedupe_rows(rows)

    if count:
        # Honors --where/--select/--distinct above; ignores --limit/--offset
        # below on purpose -- "how many are there" and "show me the first ten"
        # are different questions, and a --count that respected --limit could
        # only ever return min(n, limit).
        print(len(rows))
        return 0

    if args.sort:
        rows = _apply_sort(rows, args.sort, sort_schema)

    if args.offset:
        rows = rows[args.offset :]
    if args.limit is not None:
        rows = rows[: args.limit]

    columns = select_fields if select_fields is not None else _resolve_columns(args)
    grouped = len(logs_info) > 1
    output = _render(rows, columns, args.format, logs_info if grouped else None)

    print(output)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(output)
            if not output.endswith("\n"):
                handle.write("\n")

    if not quiet:
        _print_summary(user_wheres, default_status_injected, args, logs_info, summary)

    return 0


def _print_summary(
    user_wheres: list[str],
    default_status_injected: bool,
    args: argparse.Namespace,
    logs_info: list[LogInfo],
    notes: list[str],
) -> None:
    """The scope summary, always on stderr, silenced by `--quiet`/`-q`.

    Rows go to stdout so pipes and `--out` stay clean; the summary answers
    "what did this query actually mean", which a query whose answer depends
    on cwd or an implicit default filter must always be able to say.
    """
    where_parts = list(user_wheres)
    if default_status_injected:
        where_parts.append(f"status={','.join(DEFAULT_STATUSES)}")
    print(
        f"[quest list] where  {'  ·  '.join(where_parts) if where_parts else '(none)'}",
        file=sys.stderr,
    )
    if default_status_injected:
        print(
            "[quest list]        (status filter is a default -- override with "
            "--where status:exists)",
            file=sys.stderr,
        )
    for note in notes:
        print(f"[quest list] {note}", file=sys.stderr)
    if args.sort:
        print(f"[quest list] sort   {args.sort}", file=sys.stderr)
    plural = "" if len(logs_info) == 1 else "s"
    print(f"[quest list] logs   {len(logs_info)} log{plural} swept", file=sys.stderr)


def _project(row: dict, fields: list[str]) -> dict:
    projected = {f: row.get(f) for f in fields}
    projected[_LOG_KEY] = row.get(_LOG_KEY)
    return projected


def _dedupe_rows(rows: list[dict]) -> list[dict]:
    """Collapse rows identical across their (already-projected) *visible* fields.

    Preserves first-seen order -- a stable dedupe reads as "which values
    occur", not "which values sorted". `_LOG_KEY` is excluded from the
    equality check: it is bookkeeping for table grouping, not part of what
    the caller asked to compare, and including it would make two logs'
    otherwise-identical rows spuriously distinct.
    """
    seen: set[tuple] = set()
    unique: list[dict] = []
    for row in rows:
        key = tuple(
            tuple(v) if isinstance(v, list) else v for k, v in row.items() if k != _LOG_KEY
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def _collect_rows(
    args: argparse.Namespace,
) -> tuple[list[dict], schema.SchemaConfig | None, frozenset, list[LogInfo]]:
    """The rows in scope, the schema `--sort` should rank against, the union
    of field names `--select` may legally name, and per-log metadata.

    Log resolution goes through the one `resolve_log_set()` -- explicit
    `--in` (repeatable, names or paths), else `-A`/`--all-logs` sweeping
    `--root` (repeatable), else the default walk-up to a single log.

    The returned schema is the **first** resolved log's. For a single log --
    the overwhelmingly common case -- that is exactly right. Across multiple
    logs with *different* vocabularies it is an approximation; the honest fix
    is each log evaluating its own view definition (QST-37n0t), not
    attempted here. Deliberately not "merge the vocabularies": there is no
    correct way to interleave two independently declared orderings, and
    inventing one would be a wrong answer delivered confidently.
    """
    logs = resolve_log_set(in_dirs=args.in_dirs, all_logs=args.all_logs, root=args.root)
    multi = len(logs) > 1 or args.all_logs

    rows: list[dict] = []
    sort_schema: schema.SchemaConfig | None = None
    valid_fields: set[str] = set(schema.CORE_FIELDS) | set(computed.DERIVED_FIELD_NAMES)
    logs_info: list[LogInfo] = []
    terminal_by_log: dict[str, tuple] = {}
    for quests_dir in logs:
        try:
            config = QuestLogConfig.load(quests_dir)
        except (ConfigVersionError, schema.SchemaExtendsError, schema.SchemaConfigError) as exc:
            if not multi:
                raise
            print(f"[quest list] skipping {quests_dir}: {exc}", file=sys.stderr)
            continue
        if sort_schema is None:
            sort_schema = config.schema
        valid_fields |= set(config.schema.fields)
        project = config.project or quests_dir.name
        terminal_by_log[project] = config.schema.terminal_statuses
        logs_info.append(
            LogInfo(
                quests_dir=quests_dir,
                project=project,
                fields=frozenset(schema.CORE_FIELDS) | frozenset(config.schema.fields),
            )
        )
        for path in sorted(quests_dir.glob(config.pattern)):
            quest = Quest.load(path)
            row = _to_plain(quest.frontmatter)
            row.setdefault("project", project)
            row[_LOG_KEY] = project
            rows.append(row)
    computed.annotate_rows(rows, terminal_by_log, _LOG_KEY)
    return rows, sort_schema, frozenset(valid_fields), logs_info


def _to_plain(frontmatter) -> dict:
    """CommentedMap/CommentedSeq -> plain dict/list, safe for json/csv rendering."""
    return {key: (list(value) if isinstance(value, list) else value) for key, value in frontmatter.items()}


def _parse_sort(sort_expr: str) -> list[tuple[str, bool]]:
    """`"priority:asc,effort:desc"` -> `[("priority", False), ("effort", True)]`.

    The old implementation was `sort_expr.partition(":")`, which on that input
    gave field=`priority` and direction=`"asc,effort:desc"` -- so every key
    after the first was silently dropped and `desc` never matched anything.
    """
    keys: list[tuple[str, bool]] = []
    for part in sort_expr.split(","):
        field_name, _, direction = part.strip().partition(":")
        field_name = field_name.strip()
        if field_name:
            keys.append((field_name, direction.strip().lower() == "desc"))
    return keys


def _apply_sort(rows: list[dict], sort_expr: str, schema_config=None) -> list[dict]:
    """Sort by every key given, honoring each field's *declared* vocabulary order.

    `schema_config` is optional so the existing unit tests (and any caller
    sorting a free-text field) keep working -- without it every key is a
    string sort, which is the old behavior.

    Rows missing the *first* sort key go last regardless of direction: with a
    `desc` sort they would otherwise lead the table, and "no effort recorded"
    is not the largest effort.

    Sorts the full result globally, across every log in scope -- table
    rendering then *groups* this already-sorted order by log for display
    (see `_render_table_grouped`); it does not re-sort within each group.
    Per-log independent ranking is a `views` concept (QST-37n0t), not this.
    """
    keys = _parse_sort(sort_expr)
    if not keys:
        return rows

    primary = keys[0][0]
    present = [r for r in rows if not _is_blank(r.get(primary))]
    missing = [r for r in rows if _is_blank(r.get(primary))]

    # Sorted right-to-left through Python's stable sort: one pass per key,
    # least significant first. Cheaper to read than a composite key that has
    # to reverse only some of its components.
    for field_name, reverse in reversed(keys):
        present.sort(key=partial(_sort_key, field_name=field_name, schema_config=schema_config), reverse=reverse)
    return present + missing


def _sort_key(row: dict, field_name: str, schema_config) -> Any:
    """Declared rank when the field has a vocabulary, numeric or lowercased-string otherwise."""
    value = row.get(field_name)
    if schema_config is not None:
        rank = schema_config.rank_of(field_name, value)
        if rank is not None:
            return rank
    if _is_blank(value):
        # Only reachable for a secondary key; the primary already partitioned
        # blanks out. Sorts before any real value, which keeps the pass stable.
        return ""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        # `idle`/`blocks`/`age` are real ints -- a string sort would rank "9"
        # after "10", which is wrong for exactly the fields --where's numeric
        # comparison already treats specially.
        return value
    return str(value).lower()


def _resolve_columns(args: argparse.Namespace) -> list[str]:
    """The table/csv column set when `--select` was not given.

    `--columns` is gone outright (not aliased) -- `--select` is the one
    projection mechanism now, and it is a widened contract (every format, not
    just the fixed-width renderers), not a rename.
    """
    columns = list(DEFAULT_COLUMNS)
    if args.all_logs:
        columns.append("project")
    return columns


def _render(rows: list[dict], columns: list[str], fmt: str, logs_info: list[LogInfo] | None) -> str:
    # json/prompt show the full (possibly --select'd) frontmatter -- columns
    # only curates the fixed-width renderers (table, csv) that need a
    # rectangular shape. `_LOG_KEY` is internal bookkeeping and never a
    # user-visible field, so it is stripped before JSON serialization.
    if fmt == "json":
        # default=str: date fields (created/modified/due) normalize to real
        # `date` objects on save (see quest._normalize_date_fields), which
        # json.dumps can't serialize on its own -- str(date) is its ISO form.
        public = [{k: v for k, v in r.items() if k != _LOG_KEY} for r in rows]
        return json.dumps(public, indent=2, ensure_ascii=False, default=str)
    if fmt == "csv":
        return _render_csv(rows, columns)
    if fmt == "prompt":
        return _render_prompt(rows)
    if logs_info and len(logs_info) > 1:
        return _render_table_grouped(rows, columns, logs_info)
    return _render_table(rows, columns)


def _render_table_grouped(rows: list[dict], columns: list[str], logs_info: list[LogInfo]) -> str:
    """Per-log sections: a separator naming the log and its row count, then a
    full header + rows for that log. The header repeats under every
    separator -- a single header 60 rows away from the group you're reading
    would make each group non-copy-pasteable on its own.

    Logs with zero matching rows are omitted here (they still count toward
    the `logs` line in the stderr summary).
    """
    sections: list[str] = []
    for info in logs_info:
        group_rows = [r for r in rows if r.get(_LOG_KEY) == info.project]
        if not group_rows:
            continue
        noun = "quest" if len(group_rows) == 1 else "quests"
        separator = f"── {info.project} " + "─" * 3 + f"  {len(group_rows)} {noun}"
        sections.append(f"{separator}\n{_render_table(group_rows, columns)}")
    return "\n".join(sections) if sections else "(no matching quests)"


def _render_table(rows: list[dict], columns: list[str]) -> str:
    if not rows:
        return "(no matching quests)"
    widths = {c: max([len(c)] + [len(_cell_value(r, c)) for r in rows]) for c in columns}
    header = "  ".join(c.upper().ljust(widths[c]) for c in columns)
    lines = [header]
    for r in rows:
        lines.append("  ".join(_cell_value(r, c).ljust(widths[c]) for c in columns))
    return "\n".join(lines)


def _cell_value(row: dict, column: str) -> str:
    """The table's rendered cell -- like `_cell_str`, plus the `[blocked]` marker.

    Table-only: JSON/CSV already expose `blocked` as its own field, so
    stamping it into `status` there would duplicate the fact in a shape
    downstream tools have to unpick.
    """
    value = _cell_str(row.get(column))
    if column == "status" and row.get("blocked"):
        value = f"{value} [blocked]"
    return value


def _render_csv(rows: list[dict], columns: list[str]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        writer.writerow({c: _cell_str(r.get(c)) for c in columns})
    return buf.getvalue().rstrip("\n")


def _render_prompt(rows: list[dict]) -> str:
    if not rows:
        return "(no matching quests)"
    blocks = []
    for r in rows:
        header = f"{r.get('id', '')} [{r.get('status', '')}/{r.get('priority', '')}] {r.get('title', '')}"
        tags = ", ".join(r.get("tags") or [])
        meta = f"  type: {r.get('type', '')}  tags: {tags}"
        block = [header, meta]
        description = r.get("description")
        if description:
            block.append(f"  {description}")
        blocks.append("\n".join(block))
    return "\n\n".join(blocks)


def _cell_str(value) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value)
