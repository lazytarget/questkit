"""`quest list` — a dynamic, filterable, multi-log query/export engine."""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from functools import partial
from typing import Any

from .. import computed, query, schema
from ..config import ConfigVersionError, QuestLogConfig
from ..discovery import resolve_log_set
from ..quest import Quest, count_sync_conflicts, glob_quests, load_frontmatter_only

# `blocked` is gone: it left the status enum (a status value and a computed
# field cannot share a name), and derived-blocked quests stay visible through
# the `todo [blocked]` marking instead of a status nobody maintained by hand.
# The old hardcoded default-status list is gone too -- it's `schema.DEFAULT_VIEWS
# ["default"]` now, so a log overriding `statuses:` overrides its filter in
# the same file rather than a second config key that could disagree with it.
DEFAULT_COLUMNS = ("id", "status", "priority", "title")

# `--format md`'s default column set absent `--select` (QST-f6otu): "the
# changelog primitive" cares about what changed and how to bucket it, not
# workflow state -- `id`/`title` identify the row, `type`/`milestone` are
# what QST-cv23q's release script groups and filters by. `milestone` is a
# custom field in most schemas (this repo's own `development` schema among
# them, not a core one) -- a schema without it just renders a blank cell,
# dropped by `_md_bullet` the same way any other blank trailing value is.
MD_DEFAULT_COLUMNS = ("id", "title", "type", "milestone")

# Internal bookkeeping key carrying each row's resolved log, kept out of every
# user-visible surface (JSON keys, CSV/table columns, --group-by's equality
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
    view_name = getattr(args, "view", None) or "default"
    user_wheres = list(args.where or [])
    # `;` inside one --where value is AND sugar for repeating --where (QST-00myv):
    # "a=1;b=2" and two separate --where flags parse to the exact same clause list.
    wheres = [parsed for expr in user_wheres for parsed in query.parse_expression_list(expr)]
    user_any_exprs = list(getattr(args, "any", None) or [])
    # Each --any group is its own `;`-separated OR: the group matches a row if
    # ANY of its parsed expressions does, and every group is ANDed with
    # everything else (--where clauses, and every other --any group).
    any_groups = [query.parse_expression_list(expr) for expr in user_any_exprs]
    user_where_fields = {field_name for field_name, _, _ in wheres} | {
        field_name for group in any_groups for field_name, _, _ in group
    }

    # Every field this query could possibly need, gathered *before* rows are
    # read off disk -- this is what lets `_collect_rows` decide, per log, to
    # skip reading a quest's body entirely when nothing here references it
    # (QST-vy4vt/QST-bo3xs: `body`, `criteria_done`, `criteria_total` are the
    # only fields that cost an extra read). A view's own where/sort adds to
    # this per-log inside `_collect_rows`, once that log's schema is loaded.
    referenced_fields = set(user_where_fields)
    if getattr(args, "select", None):
        referenced_fields |= {f.strip() for f in args.select.split(",") if f.strip()}
    if getattr(args, "sort", None):
        referenced_fields |= {f for f, _ in _parse_sort(args.sort)}
    if getattr(args, "group_by", None):
        referenced_fields |= {f.strip() for f in args.group_by.split(",") if f.strip()}

    rows, sort_schema, valid_fields, logs_info, schemas_by_log = _collect_rows(
        args, referenced_fields
    )

    # `--archived` is its own axis, orthogonal to views/status: a finished
    # project's quests should vanish from every view (`next`, `stale`,
    # `blocked`) and the default listing alike, not just this one. Excluded
    # by default; `only` is what makes "just the dead project" expressible
    # without a second flag for the opposite of `include`.
    archived_mode = getattr(args, "archived", "exclude")
    if archived_mode == "exclude":
        rows = [row for row in rows if not row.get("archived")]
    elif archived_mode == "only":
        rows = [row for row in rows if row.get("archived")]

    # A view's own `where` is a *default*, applied per row against that row's
    # own log's view definition -- not the querying log's -- so a schema
    # overriding `statuses:` (and its own `views.default`) lists correctly
    # even under -A alongside logs that never touched the default vocabulary.
    # A field the caller already targeted explicitly drops out of every log's
    # view clause: "every field a view sets is a default, not a lock." Kept
    # as (raw expr, parsed tuple) pairs -- the raw string is what the summary
    # prints, unreconstructed.
    view_wheres_by_log: dict[str, list[tuple[str, tuple]]] = {}
    for info in logs_info:
        view = schemas_by_log[info.project].views.get(view_name) or schema.View()
        view_wheres_by_log[info.project] = [
            (expr, parsed)
            for expr, parsed in ((e, _parse_where(e)) for e in view.where)
            if parsed[0] not in user_where_fields
        ]
    rows = [
        row
        for row in rows
        if all(
            _matches(row, f, op, v)
            for _, (f, op, v) in view_wheres_by_log.get(row.get(_LOG_KEY) or "", [])
        )
        and all(_matches(row, f, op, v) for f, op, v in wheres)
        and all(any(_matches(row, f, op, v) for f, op, v in group) for group in any_groups)
    ]
    # For the stderr summary: the *first* resolved log's view stands in for
    # all of them, the same approximation `_apply_sort`'s ranking already
    # makes -- exact for the overwhelmingly common single-log case, and
    # merely a display nicety (not a correctness issue -- filtering above
    # already used each row's own log) when logs disagree.
    first_view_wheres = view_wheres_by_log.get(logs_info[0].project, []) if logs_info else []
    default_view_injected = view_name == "default" and bool(first_view_wheres)
    injected_where_parts = [expr for expr, _ in first_view_wheres]

    quiet = getattr(args, "quiet", False)
    select = getattr(args, "select", None)
    group_by = getattr(args, "group_by", None)
    count = getattr(args, "count", False)
    summary: list[str] = []

    if group_by:
        return _run_group_by(
            group_by=group_by,
            select=select,
            rows=rows,
            valid_fields=valid_fields,
            sort_schema=sort_schema,
            fmt=args.format,
            count=count,
            out=args.out,
            quiet=quiet,
            user_wheres=user_wheres,
            default_view_injected=default_view_injected,
            injected_where_parts=injected_where_parts,
            view_name=view_name,
            args=args,
            logs_info=logs_info,
            user_any_exprs=user_any_exprs,
        )

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
        # `body` is an unbounded, multi-line cell -- fine for json/prompt
        # (both already show full frontmatter/description text), but it
        # would blow up table's fixed-width columns and csv's one-line-per-row
        # shape (QST-vy4vt). json/prompt stay the escape hatch for a caller
        # who really wants the text back out.
        if "body" in select_fields and args.format in ("table", "csv", "md"):
            print(
                f"[quest list] error: --select body is not supported with --format {args.format} "
                "(unbounded text) -- use --format json or prompt",
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

    if count:
        # Honors --where/--select above; ignores --limit/--offset
        # below on purpose -- "how many are there" and "show me the first ten"
        # are different questions, and a --count that respected --limit could
        # only ever return min(n, limit).
        print(len(rows))
        return 0

    if args.sort:
        # An explicit --sort is a global override, ranked against the first
        # resolved log's vocabulary -- the same approximation `_collect_rows`
        # already documents for cross-log sorting.
        rows = _apply_sort(rows, args.sort, sort_schema)
    else:
        # No explicit --sort: each log's own view sort applies independently,
        # ranked against *that log's own* schema -- exact per log, not an
        # approximation, since the view and its vocabulary come from the same
        # file.
        rows = _apply_view_sort(rows, view_name, schemas_by_log, logs_info)

    if args.offset:
        rows = rows[args.offset :]
    if args.limit is not None:
        rows = rows[: args.limit]
    else:
        # No explicit --limit: each log's own view limit applies
        # independently ("next" defaults to 1 *per log*, not one overall).
        rows = _apply_view_limits(rows, view_name, schemas_by_log, logs_info)

    if select_fields is not None:
        columns = select_fields
    elif args.format == "md":
        columns = list(MD_DEFAULT_COLUMNS)
    else:
        columns = _resolve_columns(args)
    grouped = len(logs_info) > 1
    output = _render(rows, columns, args.format, logs_info if grouped else None)

    print(output)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(output)
            if not output.endswith("\n"):
                handle.write("\n")

    if not quiet:
        _print_summary(
            user_wheres,
            default_view_injected,
            injected_where_parts,
            view_name,
            args,
            logs_info,
            summary,
            user_any_exprs,
        )

    return 0


def _apply_view_sort(
    rows: list[dict], view_name: str, schemas_by_log: dict, logs_info: list[LogInfo]
) -> list[dict]:
    ordered: list[dict] = []
    for info in logs_info:
        view = schemas_by_log[info.project].views.get(view_name)
        group = [row for row in rows if row.get(_LOG_KEY) == info.project]
        if view and view.sort:
            group = _apply_sort(group, view.sort, schemas_by_log[info.project])
        ordered.extend(group)
    return ordered


def _apply_view_limits(
    rows: list[dict], view_name: str, schemas_by_log: dict, logs_info: list[LogInfo]
) -> list[dict]:
    limited: list[dict] = []
    for info in logs_info:
        view = schemas_by_log[info.project].views.get(view_name)
        group = [row for row in rows if row.get(_LOG_KEY) == info.project]
        limited.extend(group[: view.limit] if view and view.limit is not None else group)
    return limited


def _print_summary(
    user_wheres: list[str],
    default_view_injected: bool,
    injected_where_parts: list[str],
    view_name: str,
    args: argparse.Namespace,
    logs_info: list[LogInfo],
    notes: list[str],
    any_exprs: Sequence[str] = (),
) -> None:
    """The scope summary, always on stderr, silenced by `--quiet`/`-q`.

    Rows go to stdout so pipes and `--out` stay clean; the summary answers
    "what did this query actually mean", which a query whose answer depends
    on cwd or an implicit default filter must always be able to say.
    """
    where_parts = list(user_wheres) + injected_where_parts
    print(
        f"[quest list] where  {'  ·  '.join(where_parts) if where_parts else '(none)'}",
        file=sys.stderr,
    )
    if default_view_injected:
        print(
            "[quest list]        ('default' view filter is a default -- override with "
            "--where status:exists)",
            file=sys.stderr,
        )
    elif view_name != "default":
        print(f"[quest list]        (view '{view_name}')", file=sys.stderr)
    # Disclosed the same way --where is (QST-00myv): each --any group prints
    # its own raw, unreconstructed expression -- a query whose answer depends
    # on an OR-group must say so as plainly as it says so for an AND clause.
    for expr in any_exprs:
        print(f"[quest list] any    {expr}", file=sys.stderr)
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


def _run_group_by(
    *,
    group_by: str,
    select: str | None,
    rows: list[dict],
    valid_fields: frozenset,
    sort_schema: schema.SchemaConfig | None,
    fmt: str,
    count: bool,
    out: str | None,
    quiet: bool,
    user_wheres: list[str],
    default_view_injected: bool,
    injected_where_parts: list[str],
    view_name: str,
    args: argparse.Namespace,
    logs_info: list[LogInfo],
    user_any_exprs: list[str],
) -> int:
    """`--group-by field1[,field2]` -- vocabulary-ordered aggregate counts.

    Supersedes `--distinct` outright (QST-oguay): `--select f --distinct` is
    now `--group-by f` minus the count. Implies counting, so it is mutually
    exclusive with `--select` (which projects to *rows*, not aggregates) and
    with `--format prompt` (an aggregate is not a quest digest).
    """
    if select:
        print("[quest list] error: --group-by cannot be combined with --select", file=sys.stderr)
        return 1
    if fmt == "prompt":
        print("[quest list] error: --group-by has no --format prompt shape", file=sys.stderr)
        return 1

    group_fields = [f.strip() for f in group_by.split(",") if f.strip()]
    if not group_fields or len(group_fields) > 2:
        print(
            "[quest list] error: --group-by takes one or two comma-separated fields",
            file=sys.stderr,
        )
        return 1
    unknown = [f for f in group_fields if f not in valid_fields]
    if unknown:
        print(
            f"[quest list] error: --group-by names unknown field(s) {unknown}; "
            f"valid fields: {sorted(valid_fields)}",
            file=sys.stderr,
        )
        return 1

    grouped = _group_rows(rows, group_fields, sort_schema)

    if count:
        print(len(grouped))
        return 0

    columns = [*group_fields, "count"]
    output = _render(grouped, columns, fmt, None)
    print(output)
    if out:
        with open(out, "w", encoding="utf-8") as handle:
            handle.write(output)
            if not output.endswith("\n"):
                handle.write("\n")

    if not quiet:
        _print_summary(
            user_wheres,
            default_view_injected,
            injected_where_parts,
            view_name,
            args,
            logs_info,
            [f"group  {group_by}"],
            user_any_exprs,
        )

    return 0


def _group_value(value):
    """Normalize one field's value into a hashable, displayable group key.

    A list-valued field (`tags`) is joined the same way every other renderer
    (`_cell_str`) already displays it, rather than raising on an unhashable
    `list` -- group-by is mainly aimed at scalar fields, but nothing about it
    should crash on a list one.
    """
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return value


def _group_rows(rows: list[dict], fields: list[str], schema_config) -> list[dict]:
    """One row per unique combination of `fields`' values, plus a `count`.

    Sorted by each field's declared vocabulary order (via `_sort_key`,
    the same ranking `--sort` uses), primary field first -- "vocabulary-
    ordered" is the whole point of aggregation, not an afterthought.
    """
    counts: dict[tuple, int] = {}
    for row in rows:
        key = tuple(_group_value(row.get(f)) for f in fields)
        counts[key] = counts.get(key, 0) + 1

    groups = [dict(zip(fields, key, strict=True), count=n) for key, n in counts.items()]
    for field_name in reversed(fields):
        groups.sort(key=partial(_sort_key, field_name=field_name, schema_config=schema_config))
    return groups


def _collect_rows(
    args: argparse.Namespace,
    referenced_fields: frozenset | set = frozenset(),
) -> tuple[list[dict], schema.SchemaConfig | None, frozenset, list[LogInfo], dict[str, schema.SchemaConfig]]:
    """The rows in scope, the schema `--sort` should rank against, the union
    of field names `--select` may legally name, and per-log metadata.

    Log resolution goes through the one `resolve_log_set()` -- explicit
    `--in` (repeatable, names or paths), else `-A`/`--all-logs` sweeping
    `--root` (repeatable), else the default walk-up to a single log.

    The returned sort schema is the **first** resolved log's -- exact for a
    single log, an approximation across logs with *different* vocabularies
    (there is no correct way to interleave two independently declared
    orderings). `schemas_by_log` carries every log's own full `SchemaConfig`,
    which is what lets view filtering/sorting/limiting be exact per log
    rather than sharing that same approximation.
    """
    logs = resolve_log_set(in_dirs=args.in_dirs, all_logs=args.all_logs, root=args.root)
    multi = len(logs) > 1 or args.all_logs
    view_name = getattr(args, "view", None) or "default"
    lazy_fields = set(computed.LAZY_FIELD_NAMES)

    rows: list[dict] = []
    sort_schema: schema.SchemaConfig | None = None
    valid_fields: set[str] = set(schema.CORE_FIELDS) | set(computed.DERIVED_FIELD_NAMES)
    logs_info: list[LogInfo] = []
    terminal_by_log: dict[str, tuple] = {}
    schemas_by_log: dict[str, schema.SchemaConfig] = {}
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
        schemas_by_log[project] = config.schema
        logs_info.append(
            LogInfo(
                quests_dir=quests_dir,
                project=project,
                fields=frozenset(schema.CORE_FIELDS) | frozenset(config.schema.fields),
            )
        )
        # A view's own where/sort can reference a lazy field too (e.g. a
        # custom view sorting by `criteria_total`) -- checked per log, since
        # each log's schema (and hence its view definitions) can differ.
        view = config.schema.views.get(view_name)
        view_fields: set[str] = set()
        if view is not None:
            view_fields |= {_parse_where(w)[0] for w in view.where}
            if view.sort:
                view_fields |= {f for f, _ in _parse_sort(view.sort)}
        needs_body = bool((referenced_fields | view_fields) & lazy_fields)

        conflicts = count_sync_conflicts(quests_dir, config.pattern)
        if conflicts:
            print(
                f"[quest list] {conflicts} sync-conflict copies present in "
                f"{quests_dir} — resolve by hand",
                file=sys.stderr,
            )
        for path in glob_quests(quests_dir, config.pattern):
            if needs_body:
                quest = Quest.load(path)
                row = _to_plain(quest.frontmatter)
                row["body"] = quest.body
                row["criteria_total"], row["criteria_done"] = computed.criteria_counts(quest.body)
            else:
                frontmatter = load_frontmatter_only(path)
                row = _to_plain(frontmatter)
            row.setdefault("project", project)
            row[_LOG_KEY] = project
            rows.append(row)
    computed.annotate_rows(rows, terminal_by_log, _LOG_KEY)
    return rows, sort_schema, frozenset(valid_fields), logs_info, schemas_by_log


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
    if fmt == "md":
        if logs_info and len(logs_info) > 1:
            return _render_md_grouped(rows, columns, logs_info)
        return _render_md(rows, columns)
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


def _render_md(rows: list[dict], columns: list[str]) -> str:
    """`--format md` (QST-f6otu) -- the changelog primitive: one bullet per row.

    Line shape converged in-session against the spec's starting candidate:

        - **QST-bo3xs** Checklist-progress computed fields *(feature, 0.4.0)*

    The first column is always bold (identity -- `id` by default, or
    whatever `--select`'s first field is), the second renders plain right
    after it (title-shaped), and any further columns join into one italic
    parenthetical -- dropping blanks so a schema missing one of the default
    trailing fields (e.g. no `milestone`) never prints a dangling `*(feature,
    )*`. `--sort`/`--limit` need no special handling here: both already
    happened to `rows` before this ever runs, same as every other renderer.
    """
    if not rows:
        return "(no matching quests)"
    return "\n".join(_md_bullet(row, columns) for row in rows)


def _render_md_grouped(rows: list[dict], columns: list[str], logs_info: list[LogInfo]) -> str:
    """Per-log grouping for `--format md`: a `### <project>` heading per log.

    Mirrors `_render_table_grouped`'s per-log sectioning (and its "logs with
    zero matching rows are omitted" rule), in Markdown-heading shape instead
    of a plain-text separator -- this is the format a changelog gets pasted
    from, so its own section breaks should already be real Markdown.
    """
    sections: list[str] = []
    for info in logs_info:
        group_rows = [r for r in rows if r.get(_LOG_KEY) == info.project]
        if not group_rows:
            continue
        sections.append(f"### {info.project}\n\n{_render_md(group_rows, columns)}")
    return "\n\n".join(sections) if sections else "(no matching quests)"


def _md_bullet(row: dict, columns: list[str]) -> str:
    if not columns:
        return "-"
    values = [_cell_str(row.get(c)) for c in columns]
    bold, rest = values[0], values[1:]
    line = f"- **{bold}**"
    if not rest:
        return line
    second, tail = rest[0], [v for v in rest[1:] if v]
    if second:
        line += f" {second}"
    if tail:
        line += f" *({', '.join(tail)})*"
    return line


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
