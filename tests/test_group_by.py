"""Tests for `--group-by`, `quest list`'s aggregation mode (QST-oguay).

`--group-by field1[,field2]` switches `list` into vocabulary-ordered
aggregate counts across one or two fields, superseding the old (unused)
`--distinct` outright -- see test_select_and_count.py for its removal.
"""

from __future__ import annotations

import json


def test_group_by_one_field_counts_and_orders_by_declared_vocabulary(
    isolated, make_log, write_quest, run
):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", slug="a", priority="low")
    write_quest(log, "QST-bbbbb", slug="b", priority="critical")
    write_quest(log, "QST-ccccc", slug="c", priority="low")
    write_quest(log, "QST-ddddd", slug="d", priority="critical")
    write_quest(log, "QST-eeeee", slug="e", priority="high")

    result = run("list", "--in", str(log), "--where", "status:exists", "--group-by", "priority")

    lines = [line.rstrip() for line in result.out.splitlines() if line.strip()]
    # declared priority order: critical, high, medium, low, deferred
    assert lines == ["PRIORITY  COUNT", "critical  2", "high      1", "low       2"]


def test_group_by_two_fields_is_vocabulary_ordered_on_both_keys(
    isolated, make_log, write_quest, run
):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", slug="a", priority="low", status="todo")
    write_quest(log, "QST-bbbbb", slug="b", priority="critical", status="done")
    write_quest(log, "QST-ccccc", slug="c", priority="critical", status="todo")

    result = run(
        "list", "--in", str(log), "--where", "status:exists", "--group-by", "priority,status"
    )

    lines = [line.rstrip() for line in result.out.splitlines() if line.strip()]
    header, *rows = lines
    assert header == "PRIORITY  STATUS  COUNT"
    # critical before low (priority order); within critical, todo before done (status order)
    assert rows == ["critical  todo    1", "critical  done    1", "low       todo    1"]


def test_group_by_json_shape(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", slug="a", status="todo")
    write_quest(log, "QST-bbbbb", slug="b", status="todo")
    write_quest(log, "QST-ccccc", slug="c", status="done")

    result = run(
        "list", "--in", str(log), "--where", "status:exists",
        "--group-by", "status", "--format", "json",
    )

    rows = json.loads(result.out)
    assert {"status": "todo", "count": 2} in rows
    assert {"status": "done", "count": 1} in rows


def test_group_by_csv_shape(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", slug="a", status="todo")
    write_quest(log, "QST-bbbbb", slug="b", status="todo")

    result = run(
        "list", "--in", str(log), "--where", "status:exists",
        "--group-by", "status", "--format", "csv",
    )

    lines = [line.rstrip() for line in result.out.splitlines() if line.strip()]
    assert lines == ["status,count", "todo,2"]


def test_group_by_errors_cleanly_on_prompt_format(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", status="todo")

    result = run(
        "list", "--in", str(log), "--where", "status:exists",
        "--group-by", "status", "--format", "prompt",
    )

    assert result.code == 1
    assert "--group-by" in result.err


def test_group_by_with_select_is_an_error(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", status="todo")

    result = run(
        "list", "--in", str(log), "--group-by", "status", "--select", "id",
    )

    assert result.code == 1
    assert "--select" in result.err


def test_group_by_unknown_field_errors(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", status="todo")

    result = run("list", "--in", str(log), "--group-by", "nonsense")

    assert result.code == 1
    assert "nonsense" in result.err


def test_group_by_honors_where_filter_before_grouping(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", slug="a", status="todo", priority="low")
    write_quest(log, "QST-bbbbb", slug="b", status="done", priority="low")

    result = run("list", "--in", str(log), "--where", "status=todo", "--group-by", "priority")

    lines = [line.rstrip() for line in result.out.splitlines() if line.strip()]
    assert lines == ["PRIORITY  COUNT", "low       1"]


def test_group_by_honors_archived_exclusion(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", slug="a", status="todo", priority="low", archived=True)
    write_quest(log, "QST-bbbbb", slug="b", status="todo", priority="low")

    result = run(
        "list", "--in", str(log), "--where", "status:exists", "--group-by", "priority"
    )

    lines = [line.rstrip() for line in result.out.splitlines() if line.strip()]
    assert lines == ["PRIORITY  COUNT", "low       1"]


def test_group_by_honors_a_across_logs(isolated, make_log, write_quest, run, monkeypatch):
    alpha = make_log(isolated / "alpha", "alpha", project="alpha")
    beta = make_log(isolated / "beta", "beta", project="beta")
    write_quest(alpha, "QST-aaaaa", status="todo", priority="low")
    write_quest(beta, "QST-bbbbb", status="todo", priority="low")
    monkeypatch.setenv("QST_ROOT", str(isolated))

    result = run("list", "-A", "--where", "status:exists", "--group-by", "priority")

    lines = [line.rstrip() for line in result.out.splitlines() if line.strip()]
    assert lines == ["PRIORITY  COUNT", "low       2"]
