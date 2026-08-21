"""Tests for QST-b9lqo's computed fields: blocked, blocks, idle, age.

Derived once per query over the active row set (not per quest in isolation) --
`blocks` needs to see every quest's `blocked_by` to count reverse edges, and
`blocked` needs to resolve a referenced quest's *own* status. Comparison
operators (`!=`, `>`, `<`, `>=`, `<=`) shipped earlier with QST-j68u5 rule 19;
this quest just gives them something interesting to compare against.
"""

from __future__ import annotations

import json
from datetime import date, timedelta


def _iso(days_ago: int) -> str:
    return (date.today() - timedelta(days=days_ago)).isoformat()


# --- blocked --------------------------------------------------------------


def test_blocked_true_when_a_dependency_is_non_terminal(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", slug="a", status="todo")
    write_quest(log, "QST-bbbbb", slug="b", status="todo", blocked_by=["QST-aaaaa"])

    result = run("list", "--in", str(log), "--where", "status:exists", "--select", "id,blocked", "--format", "json")

    rows = {r["id"]: r["blocked"] for r in json.loads(result.out)}
    assert rows["QST-bbbbb"] is True
    assert rows["QST-aaaaa"] is False


def test_blocked_false_once_the_dependency_is_terminal(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", slug="a", status="done")
    write_quest(log, "QST-bbbbb", slug="b", status="todo", blocked_by=["QST-aaaaa"])

    result = run("list", "--in", str(log), "--where", "status:exists", "--select", "id,blocked", "--format", "json")

    rows = {r["id"]: r["blocked"] for r in json.loads(result.out)}
    assert rows["QST-bbbbb"] is False


def test_blocked_resolves_against_the_logs_own_terminal_statuses(isolated, make_log, write_quest, run):
    log = make_log(
        isolated,
        schema={
            "statuses": ["todo", "in-review", "shipped", "cancelled"],
            "terminal_statuses": ["shipped", "cancelled"],
        },
    )
    write_quest(log, "QST-aaaaa", slug="a", status="shipped")
    write_quest(log, "QST-bbbbb", slug="b", status="todo", blocked_by=["QST-aaaaa"])

    result = run("list", "--in", str(log), "--where", "status:exists", "--select", "id,blocked", "--format", "json")

    rows = {r["id"]: r["blocked"] for r in json.loads(result.out)}
    assert rows["QST-bbbbb"] is False


def test_default_list_marks_a_blocked_row_in_the_status_cell(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", slug="a", status="todo")
    write_quest(log, "QST-bbbbb", slug="b", status="todo", blocked_by=["QST-aaaaa"])

    result = run("list", "--in", str(log))

    lines = [line for line in result.out.splitlines() if "QST-bbbbb" in line]
    assert lines and "[blocked]" in lines[0]
    unblocked_lines = [line for line in result.out.splitlines() if "QST-aaaaa" in line]
    assert unblocked_lines and "[blocked]" not in unblocked_lines[0]


def test_blocked_and_blocks_honor_the_stored_archived_field(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", slug="a", status="todo", archived=True)
    write_quest(log, "QST-bbbbb", slug="b", status="todo", blocked_by=["QST-aaaaa"])
    write_quest(log, "QST-ccccc", slug="c", status="todo", archived=True, blocked_by=["QST-bbbbb"])

    result = run("list", "--in", str(log), "--where", "status:exists", "--select", "id,blocked,blocks", "--format", "json")

    rows = {r["id"]: r for r in json.loads(result.out)}
    # An archived dependency is no longer "in the way" -- blocked reads false.
    assert rows["QST-bbbbb"]["blocked"] is False
    # An archived quest's own dependency edge does not count toward what it
    # points at -- archived work is not "in the way" of anything either.
    assert rows["QST-bbbbb"]["blocks"] == 0


# --- blocks -----------------------------------------------------------------


def test_blocks_counts_non_terminal_non_archived_dependents(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", slug="a", status="todo")
    write_quest(log, "QST-bbbbb", slug="b", status="todo", blocked_by=["QST-aaaaa"])
    write_quest(log, "QST-ccccc", slug="c", status="done", blocked_by=["QST-aaaaa"])
    write_quest(log, "QST-ddddd", slug="d", status="todo", archived=True, blocked_by=["QST-aaaaa"])

    result = run("list", "--in", str(log), "--where", "status:exists", "--select", "id,blocks", "--format", "json")

    rows = {r["id"]: r["blocks"] for r in json.loads(result.out)}
    assert rows["QST-aaaaa"] == 1


def test_a_quest_with_no_dependents_has_zero_blocks(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", slug="a", status="todo")

    result = run("list", "--in", str(log), "--where", "status:exists", "--select", "id,blocks", "--format", "json")

    rows = {r["id"]: r["blocks"] for r in json.loads(result.out)}
    assert rows["QST-aaaaa"] == 0


# --- idle / age --------------------------------------------------------------


def test_idle_falls_back_to_created_when_status_changed_is_absent(
    isolated, make_log, write_quest, run, absent
):
    log = make_log(isolated)
    write_quest(
        log, "QST-aaaaa", status="todo", created=date.fromisoformat(_iso(20)),
        status_changed=absent,
    )

    result = run("list", "--in", str(log), "--where", "status:exists", "--select", "id,idle", "--format", "json")

    rows = json.loads(result.out)
    assert rows[0]["idle"] == 20


def test_idle_uses_status_changed_when_present(isolated, make_log, write_quest, run):
    log = make_log(
        isolated,
    )
    write_quest(
        log,
        "QST-aaaaa",
        status="todo",
        created=date.fromisoformat(_iso(30)),
        status_changed=date.fromisoformat(_iso(5)),
    )

    result = run("list", "--in", str(log), "--where", "status:exists", "--select", "id,idle", "--format", "json")

    rows = json.loads(result.out)
    assert rows[0]["idle"] == 5


def test_age_is_days_since_created(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", status="todo", created=date.fromisoformat(_iso(42)))

    result = run("list", "--in", str(log), "--where", "status:exists", "--select", "id,age", "--format", "json")

    rows = json.loads(result.out)
    assert rows[0]["age"] == 42


# --- comparison operators against computed fields ----------------------------


def test_where_idle_greater_than_filters_numerically(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", slug="a", status="todo", created=date.fromisoformat(_iso(20)))
    write_quest(log, "QST-bbbbb", slug="b", status="todo", created=date.fromisoformat(_iso(2)))

    result = run("list", "--in", str(log), "--where", "status:exists", "--where", "idle>14")

    assert "QST-aaaaa" in result.out
    assert "QST-bbbbb" not in result.out


def test_where_and_select_and_sort_all_see_computed_fields(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", slug="a", status="todo", created=date.fromisoformat(_iso(1)))
    write_quest(log, "QST-bbbbb", slug="b", status="todo", created=date.fromisoformat(_iso(9)))

    result = run(
        "list", "--in", str(log), "--where", "status:exists",
        "--select", "id,age", "--sort", "age:desc", "--format", "csv",
    )

    lines = [line for line in result.out.splitlines() if line.strip()]
    assert lines == ["id,age", "QST-bbbbb,9", "QST-aaaaa,1"]


# --- read-only enforcement ---------------------------------------------------


def test_set_on_a_computed_field_is_an_error(quest_log, run):
    result = run("new", "A quest", "--status", "todo")
    quest_id = result.lines[-1].split()[0].split("/")[-1].split("--")[0]

    result = run("set", quest_id, "blocked=true")

    assert result.code == 1


def test_set_on_each_computed_field_name_is_rejected(quest_log, run):
    result = run("new", "A quest", "--status", "todo")
    quest_id = result.lines[-1].split()[0].split("/")[-1].split("--")[0]

    for name in ("blocked", "blocks", "idle", "age"):
        result = run("set", quest_id, f"{name}=1")
        assert result.code == 1, name
