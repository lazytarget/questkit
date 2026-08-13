"""`quest list` — a dynamic, filterable, multi-log query/export engine."""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys

from .. import schema
from ..config import ConfigVersionError, QuestLogConfig
from ..discovery import find_all_logs, resolve_log, resolve_sweep_root
from ..quest import Quest

DEFAULT_STATUSES = ("todo", "in-progress", "blocked")
DEFAULT_COLUMNS = ("id", "status", "priority", "title")


def run(args: argparse.Namespace) -> int:
    wheres = [_parse_where(expr) for expr in (args.where or [])]
    if not any(field == "status" for field, _, _ in wheres):
        wheres.append(("status", "eq", ",".join(DEFAULT_STATUSES)))

    rows = _collect_rows(args)
    rows = [row for row in rows if all(_matches(row, f, op, v) for f, op, v in wheres)]

    if args.sort:
        rows = _apply_sort(rows, args.sort)

    if args.offset:
        rows = rows[args.offset :]
    if args.limit is not None:
        rows = rows[: args.limit]

    columns = _resolve_columns(args)
    output = _render(rows, columns, args.format)

    print(output)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(output)
            if not output.endswith("\n"):
                handle.write("\n")

    return 0


def _collect_rows(args: argparse.Namespace) -> list[dict]:
    if args.all_logs:
        root = resolve_sweep_root(explicit=args.root)
        logs = find_all_logs(root)
    else:
        logs = [resolve_log(explicit=args.in_dir)]

    rows: list[dict] = []
    for quests_dir in logs:
        try:
            config = QuestLogConfig.load(quests_dir)
        except (ConfigVersionError, schema.SchemaExtendsError) as exc:
            if not args.all_logs:
                raise
            print(f"[quest list] skipping {quests_dir}: {exc}", file=sys.stderr)
            continue
        project = config.project or quests_dir.name
        for path in sorted(quests_dir.glob(config.pattern)):
            quest = Quest.load(path)
            row = _to_plain(quest.frontmatter)
            row.setdefault("project", project)
            rows.append(row)
    return rows


def _to_plain(frontmatter) -> dict:
    """CommentedMap/CommentedSeq -> plain dict/list, safe for json/csv rendering."""
    return {key: (list(value) if isinstance(value, list) else value) for key, value in frontmatter.items()}


def _parse_where(expr: str) -> tuple[str, str, str | None]:
    if expr.endswith(":exists"):
        return expr[: -len(":exists")].strip(), "exists", None
    if "~" in expr:
        field, _, value = expr.partition("~")
        return field.strip(), "contains", value.strip()
    if "=" in expr:
        field, _, value = expr.partition("=")
        return field.strip(), "eq", value.strip()
    raise ValueError(
        f"malformed --where expression '{expr}' (expected field=value, field~value, or field:exists)"
    )


def _matches(row: dict, field_name: str, op: str, value: str | None) -> bool:
    actual = row.get(field_name)
    if op == "exists":
        return not _is_blank(actual)
    if op == "contains":
        if isinstance(actual, list):
            return value.lower() in [str(v).lower() for v in actual]
        return value.lower() in str(actual or "").lower()
    if op == "eq":
        candidates = {c.strip().lower() for c in value.split(",") if c.strip()}
        if isinstance(actual, list):
            return bool({str(v).lower() for v in actual} & candidates)
        return str(actual).lower() in candidates
    return False


def _is_blank(value) -> bool:
    return value is None or value == "" or value == []


def _apply_sort(rows: list[dict], sort_expr: str) -> list[dict]:
    field_name, _, direction = sort_expr.partition(":")
    field_name = field_name.strip()
    reverse = direction.strip().lower() == "desc"
    present = [r for r in rows if not _is_blank(r.get(field_name))]
    missing = [r for r in rows if _is_blank(r.get(field_name))]
    present.sort(key=lambda r: str(r.get(field_name)), reverse=reverse)
    return present + missing


def _resolve_columns(args: argparse.Namespace) -> list[str]:
    if args.columns:
        return [c.strip() for c in args.columns.split(",") if c.strip()]
    columns = list(DEFAULT_COLUMNS)
    if args.all_logs:
        columns.append("project")
    return columns


def _render(rows: list[dict], columns: list[str], fmt: str) -> str:
    # json/prompt always show the full frontmatter -- --columns only curates
    # the fixed-width renderers (table, csv) that need a rectangular shape.
    if fmt == "json":
        return json.dumps(rows, indent=2, ensure_ascii=False)
    if fmt == "csv":
        return _render_csv(rows, columns)
    if fmt == "prompt":
        return _render_prompt(rows)
    return _render_table(rows, columns)


def _render_table(rows: list[dict], columns: list[str]) -> str:
    if not rows:
        return "(no matching quests)"
    widths = {c: max([len(c)] + [len(_cell_str(r.get(c))) for r in rows]) for c in columns}
    header = "  ".join(c.upper().ljust(widths[c]) for c in columns)
    lines = [header]
    for r in rows:
        lines.append("  ".join(_cell_str(r.get(c)).ljust(widths[c]) for c in columns))
    return "\n".join(lines)


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
