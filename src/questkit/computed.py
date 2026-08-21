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
DERIVED_FIELD_NAMES = ("blocked", "blocks", "idle", "age")


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
