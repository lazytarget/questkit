"""`quest list` — a dynamic, filterable, multi-log query/export engine."""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from functools import partial
from typing import Any

from .. import schema
from ..config import ConfigVersionError, QuestLogConfig
from ..discovery import find_all_logs, resolve_log, resolve_sweep_root
from ..quest import Quest

# `blocked` is gone: it left the status enum (a status value and a computed
# field cannot share a name), and derived-blocked quests stay visible through
# the `todo [blocked]` marking instead of a status nobody maintained by hand.
# QST-37n0t moves this into `views.default`, removing the last hardcoded
# status list rather than replacing it with a config key.
DEFAULT_STATUSES = ("todo", "in-progress")
DEFAULT_COLUMNS = ("id", "status", "priority", "title")

# Checked in this order, and the order is the whole point: the compound
# operators must be tried before their single-character prefixes, or `>=` is
# shredded into `>` plus a value that silently gains a leading `=`.
_OPERATORS = (
    ("!=", "ne"),
    (">=", "gte"),
    ("<=", "lte"),
    ("~", "contains"),
    (">", "gt"),
    ("<", "lt"),
    ("=", "eq"),
)


def run(args: argparse.Namespace) -> int:
    wheres = [_parse_where(expr) for expr in (args.where or [])]
    if not any(field == "status" for field, _, _ in wheres):
        wheres.append(("status", "eq", ",".join(DEFAULT_STATUSES)))

    rows, sort_schema = _collect_rows(args)
    rows = [row for row in rows if all(_matches(row, f, op, v) for f, op, v in wheres)]

    if args.sort:
        rows = _apply_sort(rows, args.sort, sort_schema)

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


def _collect_rows(args: argparse.Namespace) -> tuple[list[dict], schema.SchemaConfig | None]:
    """The rows in scope, plus the schema `--sort` should rank against.

    The returned schema is the **first** resolved log's. For a single log --
    the overwhelmingly common case -- that is exactly right. Across `-A` with
    logs that declare *different* vocabularies it is an approximation, and the
    honest fix is per-log grouping (QST-iqwjm), where each log sorts under its
    own definition and the results concatenate. Deliberately not "merge the
    vocabularies": there is no correct way to interleave two independently
    declared orderings, and inventing one would be a wrong answer delivered
    confidently.
    """
    if args.all_logs:
        root = resolve_sweep_root(explicit=args.root)
        logs = find_all_logs(root)
    else:
        logs = [resolve_log(explicit=args.in_dir)]

    rows: list[dict] = []
    sort_schema: schema.SchemaConfig | None = None
    for quests_dir in logs:
        try:
            config = QuestLogConfig.load(quests_dir)
        except (ConfigVersionError, schema.SchemaExtendsError, schema.SchemaConfigError) as exc:
            if not args.all_logs:
                raise
            print(f"[quest list] skipping {quests_dir}: {exc}", file=sys.stderr)
            continue
        if sort_schema is None:
            sort_schema = config.schema
        project = config.project or quests_dir.name
        for path in sorted(quests_dir.glob(config.pattern)):
            quest = Quest.load(path)
            row = _to_plain(quest.frontmatter)
            row.setdefault("project", project)
            rows.append(row)
    return rows, sort_schema


def _to_plain(frontmatter) -> dict:
    """CommentedMap/CommentedSeq -> plain dict/list, safe for json/csv rendering."""
    return {key: (list(value) if isinstance(value, list) else value) for key, value in frontmatter.items()}


def _parse_where(expr: str) -> tuple[str, str, str | None]:
    if expr.endswith(":exists"):
        return expr[: -len(":exists")].strip(), "exists", None
    for token, op in _OPERATORS:
        if token in expr:
            field_name, _, value = expr.partition(token)
            return field_name.strip(), op, value.strip()
    raise ValueError(
        f"malformed --where expression '{expr}' (expected field<op>value with op in "
        f"{', '.join(token for token, _ in _OPERATORS)}, or field:exists)"
    )


def _split_candidates(value: str) -> list[str]:
    """`"a,b"` -> `["a", "b"]` -- the comma-list-is-OR convention shared by
    every --where operator: `field=a,b` and `field~a,b` both mean "a or b"."""
    return [c.strip().lower() for c in value.split(",") if c.strip()]


def _matches(row: dict, field_name: str, op: str, value: str | None) -> bool:
    actual = row.get(field_name)
    if op == "exists":
        return not _is_blank(actual)
    if op == "contains":
        candidates = _split_candidates(value or "")
        if isinstance(actual, list):
            actual_values = [str(v).lower() for v in actual]
            return any(c in actual_values for c in candidates)
        actual_str = str(actual or "").lower()
        return any(c in actual_str for c in candidates)
    if op == "eq":
        wanted = set(_split_candidates(value or ""))
        if isinstance(actual, list):
            return bool({str(v).lower() for v in actual} & wanted)
        return str(actual).lower() in wanted
    if op == "ne":
        wanted = set(_split_candidates(value or ""))
        if isinstance(actual, list):
            return not ({str(v).lower() for v in actual} & wanted)
        # An absent field genuinely *is* `!= afk`, so this must not be false.
        return str(actual).lower() not in wanted if actual is not None else True
    if op in _COMPARISONS:
        return _compare(actual, value or "", op)
    return False


_COMPARISONS = {
    "gt": lambda a, b: a > b,
    "gte": lambda a, b: a >= b,
    "lt": lambda a, b: a < b,
    "lte": lambda a, b: a <= b,
}


def _compare(actual, value: str, op: str) -> bool:
    """Numeric where both sides look numeric, string otherwise.

    Frontmatter is untyped, so a count can arrive as `20` or `"20"` depending
    on who wrote the file -- and the computed fields (`idle`, `blocks`) are
    real ints. ISO dates need no special case at all: they compare correctly
    as plain strings, which is why `--where status_changed<2026-08-05` works
    with no date parsing anywhere.
    """
    if _is_blank(actual):
        return False
    left, right = str(actual), value
    if _looks_numeric(left) and _looks_numeric(right):
        return _COMPARISONS[op](float(left), float(right))
    return _COMPARISONS[op](left.lower(), right.lower())


def _looks_numeric(value: str) -> bool:
    try:
        float(value)
    except ValueError:
        return False
    return True


def _is_blank(value) -> bool:
    return value is None or value == "" or value == []


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
    """Declared rank when the field has a vocabulary, lowercased string otherwise."""
    value = row.get(field_name)
    if schema_config is not None:
        rank = schema_config.rank_of(field_name, value)
        if rank is not None:
            return rank
    if _is_blank(value):
        # Only reachable for a secondary key; the primary already partitioned
        # blanks out. Sorts before any real value, which keeps the pass stable.
        return ""
    return str(value).lower()


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
        # default=str: date fields (created/modified/due) normalize to real
        # `date` objects on save (see quest._normalize_date_fields), which
        # json.dumps can't serialize on its own -- str(date) is its ISO form.
        return json.dumps(rows, indent=2, ensure_ascii=False, default=str)
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
