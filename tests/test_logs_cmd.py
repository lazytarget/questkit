"""Tests for `quest logs` — inventory every quest log under a root.

Read-only: never writes, never creates, never migrates. `project:` uniqueness
is enforced here because `--in`'s name resolution (QST-fmk0p) depends on it
being true.
"""

from __future__ import annotations

import json


def test_lists_all_logs_with_correct_counts(isolated, make_log, write_quest, run):
    alpha = make_log(isolated, "alpha", project="alpha")
    write_quest(alpha, "QST-aaaaa", status="todo")
    write_quest(alpha, "QST-bbbbb", status="done")

    result = run("logs", "--root", str(isolated))

    assert result.code == 0
    assert "alpha" in result.out
    lines = [line for line in result.out.splitlines() if "alpha" in line and "QUESTS" not in line]
    assert lines
    assert "2" in lines[0]


def test_a_log_with_no_project_renders_a_dash(isolated, make_log, write_quest, run):
    log = make_log(isolated, project=None)
    write_quest(log, "QST-aaaaa", status="todo")

    result = run("logs", "--root", str(isolated))

    data_lines = [
        line for line in result.out.splitlines() if line.strip() and "QUESTS" not in line
    ]
    assert any(line.strip().startswith("-") for line in data_lines)


def test_open_counts_non_terminal_quests(isolated, make_log, write_quest, run):
    log = make_log(isolated, "alpha", project="alpha")
    write_quest(log, "QST-aaaaa", slug="a", status="todo")
    write_quest(log, "QST-bbbbb", slug="b", status="done")
    write_quest(log, "QST-ccccc", slug="c", status="scrapped")

    result = run("logs", "--root", str(isolated), "--format", "json")

    data = json.loads(result.out)
    entry = next(d for d in data if d["project"] == "alpha")
    assert entry["quests"] == 3
    assert entry["open"] == 1


def test_open_uses_the_logs_own_terminal_statuses(isolated, make_log, write_quest, run):
    log = make_log(
        isolated,
        "alpha",
        project="alpha",
        schema={
            "statuses": ["todo", "in-review", "shipped", "cancelled"],
            "terminal_statuses": ["shipped", "cancelled"],
        },
    )
    write_quest(log, "QST-aaaaa", slug="a", status="todo")
    write_quest(log, "QST-bbbbb", slug="b", status="shipped")

    result = run("logs", "--root", str(isolated), "--format", "json")

    entry = json.loads(result.out)[0]
    assert entry["open"] == 1


def test_format_json_emits_one_object_per_log(isolated, make_log, write_quest, run):
    alpha = make_log(isolated, "alpha", project="alpha")
    beta = make_log(isolated, "beta", project="beta")
    write_quest(alpha, "QST-aaaaa")
    write_quest(beta, "QST-bbbbb")

    result = run("logs", "--root", str(isolated), "--format", "json")

    data = json.loads(result.out)
    assert isinstance(data, list)
    assert {d["project"] for d in data} == {"alpha", "beta"}
    assert all("path" in d and "git" in d and "quests" in d for d in data)


def test_json_includes_declared_custom_fields(isolated, make_log, write_quest, run):
    log = make_log(isolated, "alpha", project="alpha", schema={"fields": {"component": {"type": "string"}}})
    write_quest(log, "QST-aaaaa")

    result = run("logs", "--root", str(isolated), "--format", "json")

    entry = json.loads(result.out)[0]
    assert "component" in entry["fields"]


def test_verbose_shows_schema_overrides_and_strict_mode(isolated, make_log, write_quest, run):
    log = make_log(
        isolated, "alpha", project="alpha", schema={"strict": False, "fields": {"component": {"type": "string"}}}
    )
    write_quest(log, "QST-aaaaa")

    result = run("logs", "--root", str(isolated), "--verbose")

    assert "component" in result.out
    assert "strict" in result.out.lower()


def test_non_verbose_omits_the_schema_detail_line(isolated, make_log, write_quest, run):
    log = make_log(isolated, "alpha", project="alpha", schema={"fields": {"component": {"type": "string"}}})
    write_quest(log, "QST-aaaaa")

    result = run("logs", "--root", str(isolated))

    assert "component" not in result.out


def test_footer_names_the_sweep_root_and_totals(isolated, make_log, write_quest, run):
    alpha = make_log(isolated, "alpha", project="alpha")
    beta = make_log(isolated, "beta", project="beta")
    write_quest(alpha, "QST-aaaaa")
    write_quest(beta, "QST-bbbbb")

    result = run("logs", "--root", str(isolated))

    assert "2" in result.out
    assert str(isolated) in result.out


def test_zero_logs_under_root(isolated, run):
    result = run("logs", "--root", str(isolated))

    assert result.code == 0
    assert "0" in result.out


def test_one_log(isolated, make_log, write_quest, run):
    log = make_log(isolated, "alpha", project="alpha")
    write_quest(log, "QST-aaaaa")

    result = run("logs", "--root", str(isolated))

    assert result.code == 0
    assert "alpha" in result.out


def test_nested_logs(isolated, make_log, write_quest, run):
    outer = make_log(isolated, project="outer")
    inner = make_log(isolated / "sub", "inner", project="inner")
    write_quest(outer, "QST-aaaaa")
    write_quest(inner, "QST-bbbbb")

    result = run("logs", "--root", str(isolated))

    assert "outer" in result.out
    assert "inner" in result.out


def test_a_broken_schema_extends_still_appears_as_a_row_with_a_warning(
    isolated, make_log, write_quest, run
):
    log = make_log(isolated, "alpha", project="alpha", schema={"extends": "nonexistent.yaml"})
    write_quest(log, "QST-aaaaa")

    result = run("logs", "--root", str(isolated))

    assert "alpha" in result.out
    assert "warning" in result.out.lower() or "warning" in result.err.lower()


def test_duplicate_project_across_two_logs_warns_and_lists_both(isolated, make_log, run):
    a = make_log(isolated / "one", "dup", project="dup")
    b = make_log(isolated / "two", "dup", project="dup")

    result = run("logs", "--root", str(isolated))

    assert result.code == 0
    assert str(a) in result.err and str(b) in result.err
    assert result.out.count("dup") >= 2


def test_logs_is_read_only(isolated, make_log, write_quest, run):
    log = make_log(isolated, "alpha", project="alpha")
    path = write_quest(log, "QST-aaaaa")
    before = path.read_text()
    mtime_before = path.stat().st_mtime_ns

    run("logs", "--root", str(isolated))

    assert path.read_text() == before
    assert path.stat().st_mtime_ns == mtime_before


def test_sorted_by_project_name(isolated, make_log, write_quest, run):
    make_log(isolated, "zulu", project="zulu")
    make_log(isolated, "alpha", project="alpha")

    result = run("logs", "--root", str(isolated), "--format", "json")

    data = json.loads(result.out)
    assert [d["project"] for d in data] == sorted(d["project"] for d in data)


def test_archived_counts_are_derived(isolated, make_log, write_quest, run):
    log = make_log(isolated, "alpha", project="alpha")
    write_quest(log, "QST-aaaaa", slug="a", archived=True)
    write_quest(log, "QST-bbbbb", slug="b")

    result = run("logs", "--root", str(isolated), "--format", "json")

    entry = json.loads(result.out)[0]
    assert entry["archived"] == 1


def test_a_fully_archived_log_is_excluded_from_footer_totals(isolated, make_log, write_quest, run):
    alpha = make_log(isolated, "alpha", project="alpha")
    beta = make_log(isolated, "beta", project="beta")
    write_quest(alpha, "QST-aaaaa", archived=True)
    write_quest(beta, "QST-bbbbb")

    result = run("logs", "--root", str(isolated))

    # total quests reported in the footer should reflect only the
    # non-fully-archived log's count (1), not both (2)
    footer = result.out.strip().splitlines()[-1]
    assert "1" in footer
