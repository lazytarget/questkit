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


# --- criteria_done / criteria_total (QST-bo3xs) ------------------------------

_CRITERIA_BODY = """## Acceptance Criteria

- [x] one
- [x] two
- [ ] three
"""


def test_criteria_total_and_done_counted_from_the_checklist(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", status="todo", body=_CRITERIA_BODY)

    result = run(
        "list", "--in", str(log), "--where", "status:exists",
        "--select", "id,criteria_total,criteria_done", "--format", "json",
    )

    rows = json.loads(result.out)
    assert rows[0]["criteria_total"] == 3
    assert rows[0]["criteria_done"] == 2


def test_criteria_fields_are_zero_with_no_acceptance_criteria_section(
    isolated, make_log, write_quest, run
):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", status="todo", body="## Description\n\nno checklist here\n")

    result = run(
        "list", "--in", str(log), "--where", "status:exists",
        "--select", "id,criteria_total,criteria_done", "--format", "json",
    )

    rows = json.loads(result.out)
    assert rows[0]["criteria_total"] == 0
    assert rows[0]["criteria_done"] == 0


def test_criteria_fields_usable_in_where_and_sort(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", slug="a", status="done", body=_CRITERIA_BODY)
    write_quest(
        log, "QST-bbbbb", slug="b", status="done",
        body="## Acceptance Criteria\n\n- [x] only\n",
    )

    result = run(
        "list", "--in", str(log), "--where", "status=done",
        "--where", "criteria_done<criteria_total", "--where", "criteria_total>0",
        "--select", "id", "--format", "csv",
    )

    lines = [line for line in result.out.splitlines() if line.strip()]
    assert lines == ["id", "QST-aaaaa"]


def test_criteria_body_is_not_read_when_not_referenced(
    isolated, make_log, write_quest, run, monkeypatch
):
    import questkit.commands.list_cmd as list_cmd

    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", status="todo", body=_CRITERIA_BODY)

    calls = []
    real_load = list_cmd.Quest.load

    def _tracking_load(path):
        calls.append(path)
        return real_load(path)

    monkeypatch.setattr(list_cmd.Quest, "load", staticmethod(_tracking_load))

    result = run("list", "--in", str(log), "--where", "status:exists", "--select", "id")
    assert "QST-aaaaa" in result.out
    assert calls == []

    calls.clear()
    result = run(
        "list", "--in", str(log), "--where", "status:exists",
        "--select", "id,criteria_total",
    )
    assert calls != []


def test_set_on_criteria_fields_is_rejected(quest_log, run):
    result = run("new", "A quest", "--status", "todo")
    quest_id = result.lines[-1].split()[0].split("/")[-1].split("--")[0]

    for name in ("criteria_done", "criteria_total"):
        result = run("set", quest_id, f"{name}=1")
        assert result.code == 1, name


# --- overdue / due_in (QST-nij1y) --------------------------------------------


def test_due_in_is_days_until_due_and_can_be_negative(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", slug="a", status="todo", due=date.fromisoformat(_iso(-5)))
    write_quest(log, "QST-bbbbb", slug="b", status="todo", due=date.fromisoformat(_iso(3)))

    result = run(
        "list", "--in", str(log), "--where", "status:exists",
        "--select", "id,due_in", "--format", "json",
    )

    rows = {r["id"]: r["due_in"] for r in json.loads(result.out)}
    assert rows["QST-aaaaa"] == 5
    assert rows["QST-bbbbb"] == -3


def test_overdue_true_when_due_has_passed_and_status_is_non_terminal(
    isolated, make_log, write_quest, run
):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", slug="a", status="todo", due=date.fromisoformat(_iso(5)))

    result = run(
        "list", "--in", str(log), "--where", "status:exists",
        "--select", "id,overdue", "--format", "json",
    )

    rows = json.loads(result.out)
    assert rows[0]["overdue"] is True


def test_overdue_false_once_status_is_terminal(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", slug="a", status="done", due=date.fromisoformat(_iso(5)))

    result = run(
        "list", "--in", str(log), "--where", "status:exists",
        "--select", "id,overdue", "--format", "json",
    )

    rows = json.loads(result.out)
    assert rows[0]["overdue"] is False


def test_overdue_false_when_archived(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(
        log, "QST-aaaaa", slug="a", status="todo", due=date.fromisoformat(_iso(5)), archived=True
    )

    result = run(
        "list", "--in", str(log), "--where", "status:exists", "--archived", "only",
        "--select", "id,overdue", "--format", "json",
    )

    rows = json.loads(result.out)
    assert rows[0]["overdue"] is False


def test_due_in_and_overdue_absent_when_no_due_date(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", status="todo")

    result = run(
        "list", "--in", str(log), "--where", "status:exists",
        "--select", "id,overdue,due_in", "--format", "json",
    )

    rows = json.loads(result.out)
    assert rows[0]["overdue"] is False
    assert rows[0]["due_in"] is None


def test_views_due_surfaces_dated_quests_soonest_first(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", slug="a", status="todo", due=date.fromisoformat(_iso(-1)))
    write_quest(log, "QST-bbbbb", slug="b", status="todo", due=date.fromisoformat(_iso(5)))
    write_quest(log, "QST-ccccc", slug="c", status="todo")

    result = run(
        "list", "--in", str(log), "--view", "due", "--select", "id,due_in", "--format", "csv"
    )

    lines = [line for line in result.out.splitlines() if line.strip()]
    assert lines == ["id,due_in", "QST-bbbbb,-5", "QST-aaaaa,1"]


def test_set_on_due_derived_fields_is_rejected(quest_log, run):
    result = run("new", "A quest", "--status", "todo")
    quest_id = result.lines[-1].split()[0].split("/")[-1].split("--")[0]

    for name in ("overdue", "due_in"):
        result = run("set", quest_id, f"{name}=1")
        assert result.code == 1, name


# --- body as a lazily-loaded queryable field (QST-vy4vt) ---------------------


def test_where_body_contains_matches_case_insensitively(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", slug="a", status="todo", body="## Notes\n\nfixed the SyncThing bug.\n")
    write_quest(log, "QST-bbbbb", slug="b", status="todo", body="## Notes\n\nunrelated work.\n")

    result = run("list", "--in", str(log), "--where", "status:exists", "--where", "body~syncthing")

    assert "QST-aaaaa" in result.out
    assert "QST-bbbbb" not in result.out


def test_any_group_can_combine_body_with_other_fields(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", slug="a", status="todo", type="bug", body="## Repro\n\nnothing special.\n")
    write_quest(log, "QST-bbbbb", slug="b", status="todo", type="feature", body="## Repro\n\nsteps here.\n")
    write_quest(log, "QST-ccccc", slug="c", status="todo", type="feature", body="## Notes\n\nno repro section.\n")

    result = run(
        "list", "--in", str(log), "--where", "status:exists",
        "--any", "body~## Repro;type=bug",
    )

    assert "QST-aaaaa" in result.out
    assert "QST-bbbbb" in result.out
    assert "QST-ccccc" not in result.out


def test_body_search_composes_with_a_view(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(
        log, "QST-aaaaa", slug="a", status="todo",
        status_changed=date.fromisoformat(_iso(30)), body="## Notes\n\nTODO: fix this.\n",
    )
    write_quest(
        log, "QST-bbbbb", slug="b", status="todo",
        status_changed=date.fromisoformat(_iso(30)), body="## Notes\n\nall done.\n",
    )

    result = run("stale", "--in", str(log), "--where", "body~TODO")

    assert "QST-aaaaa" in result.out
    assert "QST-bbbbb" not in result.out


def test_select_body_is_included_for_json(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", status="todo", body="## Notes\n\nhello there.\n")

    result = run(
        "list", "--in", str(log), "--where", "status:exists",
        "--select", "id,body", "--format", "json",
    )

    rows = json.loads(result.out)
    assert "hello there." in rows[0]["body"]


def test_select_body_is_rejected_for_table_and_csv(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", status="todo")

    for fmt in ("table", "csv", "md"):
        result = run(
            "list", "--in", str(log), "--where", "status:exists",
            "--select", "id,body", "--format", fmt,
        )
        assert result.code == 1, fmt


def test_body_not_read_when_not_referenced(isolated, make_log, write_quest, run, monkeypatch):
    import questkit.commands.list_cmd as list_cmd

    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", status="todo", body="## Notes\n\nhello.\n")

    calls = []
    real_load = list_cmd.Quest.load

    def _tracking_load(path):
        calls.append(path)
        return real_load(path)

    monkeypatch.setattr(list_cmd.Quest, "load", staticmethod(_tracking_load))

    result = run("list", "--in", str(log), "--where", "status:exists", "--select", "id")
    assert "QST-aaaaa" in result.out
    assert calls == []

    result = run("list", "--in", str(log), "--where", "status:exists", "--where", "body~hello")
    assert calls != []
