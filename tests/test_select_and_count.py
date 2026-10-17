"""Tests for `--select`, `--count`, and the retirement of `--columns`.

`--select` is a **widened contract**, not a rename of `--columns`: it applies
to every `--format` (table, csv, json, prompt), not just the fixed-width
renderers. Rows are projected to the selected fields exactly once, up front,
so every renderer downstream sees the same restricted shape rather than each
one needing its own "did the caller select?" branch.

`--distinct` is gone outright (QST-oguay): unused in practice, and
`--group-by` (see test_group_by.py) supersedes it -- `--select f --distinct`
is `--group-by f` minus the count.
"""

from __future__ import annotations

import json


def test_columns_is_gone(isolated, make_log, run):
    """argparse itself rejects the retired flag -- SystemExit(2), not a Result."""
    import pytest

    from questkit.cli import main

    log = make_log(isolated)

    with pytest.raises(SystemExit):
        main(["list", "--columns", "id,title", "--in", str(log)])


def test_select_restricts_json_output_too(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", status="todo")

    result = run("list", "--in", str(log), "--select", "id,title", "--format", "json")

    rows = json.loads(result.out)
    assert set(rows[0]) == {"id", "title"}


def test_select_preserves_the_given_order(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", status="todo")

    result = run("list", "--in", str(log), "--select", "title,id", "--format", "csv")

    header = result.out.splitlines()[0]
    assert header == "title,id"


def test_select_restricts_csv(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", status="todo")

    result = run("list", "--in", str(log), "--select", "id", "--format", "csv")

    assert result.out.splitlines()[0] == "id"


def test_select_restricts_table(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", status="todo")

    result = run("list", "--in", str(log), "--select", "id")

    assert "STATUS" not in result.out
    assert "ID" in result.out


def test_select_applies_to_prompt_format_too(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", status="todo", description="Some description")

    result = run("list", "--in", str(log), "--select", "id", "--format", "prompt")

    assert "Some description" not in result.out


def test_select_an_unknown_field_errors_listing_valid_fields(isolated, make_log, run):
    log = make_log(isolated, schema={"fields": {"component": {"type": "string"}}})

    result = run("list", "--in", str(log), "--select", "nonsense")

    assert result.code == 1
    assert "nonsense" in result.err
    assert "component" in result.err


def test_select_a_declared_custom_field_works(isolated, make_log, write_quest, run):
    log = make_log(isolated, schema={"fields": {"component": {"type": "string"}}})
    write_quest(log, "QST-aaaaa", component="api")

    result = run("list", "--in", str(log), "--select", "id,component", "--format", "csv")

    assert "api" in result.out


def test_select_project_works_even_without_a_declared_project(isolated, make_log, write_quest, run):
    log = make_log(isolated, "alpha")
    write_quest(log, "QST-aaaaa", status="todo")

    result = run("list", "--in", str(log), "--select", "id,project", "--format", "csv")

    assert "alpha" in result.out


def test_distinct_is_gone(isolated, make_log, run):
    """argparse itself rejects the retired flag -- SystemExit(2), not a Result."""
    import pytest

    from questkit.cli import main

    log = make_log(isolated)

    with pytest.raises(SystemExit):
        main(["list", "--distinct", "--in", str(log)])


# --- --count --------------------------------------------------------------------


def test_count_prints_a_bare_integer(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", slug="a", status="todo")
    write_quest(log, "QST-bbbbb", slug="b", status="todo")
    write_quest(log, "QST-ccccc", slug="c", status="done")

    result = run("list", "--in", str(log), "--where", "status=todo", "--count")

    assert result.out.strip() == "2"


def test_count_honors_select(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", slug="a", priority="low")
    write_quest(log, "QST-bbbbb", slug="b", priority="low")
    write_quest(log, "QST-ccccc", slug="c", priority="high")

    result = run(
        "list", "--in", str(log), "--where", "status:exists",
        "--select", "priority", "--count",
    )

    assert result.out.strip() == "3"


def test_count_ignores_limit_and_offset(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    for i in range(5):
        write_quest(log, f"QST-{i}aaaa", slug=f"q{i}", status="todo")

    result = run("list", "--in", str(log), "--where", "status:exists", "--limit", "2", "--count")

    assert result.out.strip() == "5"


def test_count_is_a_bare_integer_usable_in_a_shell_substitution(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", status="todo")

    result = run("list", "--in", str(log), "--where", "status:exists", "--count")

    assert int(result.out.strip()) == 1
