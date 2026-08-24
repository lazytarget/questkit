"""Computed fields: blocked, blocks, idle, age -- derived once per query.

`blocked`/`blocks` need the whole active row set to resolve `blocked_by`
edges, so they are derived here in one pass over the rows a command already
collected, rather than per quest in isolation. One computation, many
consumers: `--where`, `--select`, `--sort`, and the `todo [blocked]` table
marking all read the same annotated rows.

Bare `blocked_by` entries are today always intra-log (`QST-yiep7` adds
qualified `project/QST-xxxxx` refs); `_local_id` already strips a qualifier so
this module needs no changes when that ships.
"""

from __future__ import annotations

from datetime import date

# Read-only: `quest set`/`quest new --set` reject any assignment to one of
# these outright. Distinct from `schema.COMPUTED_FIELD_NAMES`, which also
# reserves `archived` -- a *stored* core field that merely happens to be
# read by the computation here, not derived by it.
#
# `body` is not itself "computed" (it's the file's own Markdown body, not
# derived from the corpus), but it is read-only the same way: there is no
# legitimate `quest set <id> body=...` -- a quest's body is edited by editing
# the file's Markdown, not by writing a `body:` key into its frontmatter.
# Blocking it here keeps a typo'd `quest set` from ever creating that key.
DERIVED_FIELD_NAMES = (
    "blocked",
    "blocks",
    "idle",
    "age",
    "criteria_done",
    "criteria_total",
    "overdue",
    "due_in",
    "body",
)

# The subset of DERIVED_FIELD_NAMES that needs a quest's *body text* on disk
# to compute -- `list_cmd._collect_rows` only pays for `Quest.load`'s full
# read (frontmatter + body) when a query actually references one of these;
# every other field comes from the frontmatter-only fast path
# (`quest.load_frontmatter`). See QST-vy4vt / QST-bo3xs.
LAZY_FIELD_NAMES = ("body", "criteria_done", "criteria_total")


def annotate_rows(
    rows: list[dict], terminal_by_log: dict[str, tuple], log_key: str, *, today: date | None = None
) -> None:
    """Mutate every row in place, adding blocked/blocks/idle/age.

    `terminal_by_log` maps each row's `log_key` value (the project/log
    identity already carried for table grouping) to that log's own
    `terminal_statuses` -- a quest is only "in the way" or "resolved" by its
    *own* log's vocabulary, not the querying log's.
    """
    today = today or date.today()
    by_id = {row["id"]: row for row in rows if row.get("id")}

    blocks_count: dict[str, int] = {}
    for row in rows:
        if row.get("archived"):
            continue
        if row.get("status") in terminal_by_log.get(row.get(log_key) or "", ()):
            continue
        for ref in row.get("blocked_by") or []:
            target_id = _local_id(ref)
            blocks_count[target_id] = blocks_count.get(target_id, 0) + 1

    for row in rows:
        row["blocked"] = _is_blocked(row, by_id, terminal_by_log, log_key)
        row["blocks"] = blocks_count.get(row.get("id") or "", 0)
        row["idle"] = _days_since(row.get("status_changed") or row.get("created"), today)
        row["age"] = _days_since(row.get("created"), today)
        row["overdue"], row["due_in"] = _due_fields(row, terminal_by_log, log_key, today)


def criteria_counts(body: str) -> tuple[int, int]:
    """(total, done) `- [ ]`/`- [x]` items under `## Acceptance Criteria`.

    Deliberately its own pass rather than a shared call into
    `schema._count_checklist_items` (which only needs a total, for
    `readiness:`): this one needs the checked/unchecked split, and importing
    a schema-private helper here would be the wrong direction for the
    dependency to point anyway -- `schema.py` already reaches into `query.py`
    for the `--where` grammar; `computed.py` has no business reaching into
    `schema.py` in turn. Same heading-match/stop-at-next-`## ` rule as that
    other parser, so the two never quietly disagree about what counts.
    """
    heading = "## acceptance criteria"
    counting = False
    total = 0
    done = 0
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.lower() == heading:
            counting = True
            continue
        if not counting:
            continue
        if stripped.startswith("## "):
            break
        marker = stripped[:5].lower()
        if marker == "- [ ]":
            total += 1
        elif marker == "- [x]":
            total += 1
            done += 1
    return total, done


def _due_fields(row: dict, terminal_by_log: dict, log_key: str, today: date) -> tuple[bool, int | None]:
    """`(overdue, due_in)` from `due:` -- `due_in` is a plain day count (can be
    negative), `overdue` additionally honors terminal statuses and `archived`
    the same way `blocked`/`blocks` do: a `due` date in the past on a `done`
    or archived quest is not something still in front of you.
    """
    due = row.get("due")
    if is_blank(due):
        return False, None
    due_date = date.fromisoformat(due) if isinstance(due, str) else due
    if due_date is None:
        return False, None
    due_in = (due_date - today).days
    terminal = terminal_by_log.get(row.get(log_key) or "", ())
    overdue = due_in < 0 and not row.get("archived") and row.get("status") not in terminal
    return overdue, due_in


def is_blank(value) -> bool:
    return value is None or value == ""


def _is_blocked(row: dict, by_id: dict, terminal_by_log: dict, log_key: str) -> bool:
    for ref in row.get("blocked_by") or []:
        target = by_id.get(_local_id(ref))
        if target is None or target.get("archived"):
            continue
        target_terminal = terminal_by_log.get(target.get(log_key) or "", ())
        if target.get("status") not in target_terminal:
            return True
    return False


def _local_id(ref: str) -> str:
    return ref.rsplit("/", 1)[-1]


def _days_since(value, today: date) -> int:
    if value is None:
        return 0
    if isinstance(value, str):
        value = date.fromisoformat(value)
    return (today - value).days
