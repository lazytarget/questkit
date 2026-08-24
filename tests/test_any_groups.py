"""Tests for QST-00myv: `--any` groups and `;`-separated `--where` lists.

One rule: `;` separates a list of expressions; the **flag** names the
combinator. Comma stays OR within one field's values (unchanged).

- `--any "expr;expr"` (repeatable): the group matches when ANY of its
  expressions does; each group is ANDed with everything else.
- `--where "expr;expr"`: ALL must hold -- pure sugar for repeating
  `--where`, no new semantics.
"""

from __future__ import annotations

# --- `;` in --where is AND sugar -----------------------------------------------


def test_semicolon_in_where_is_and_sugar_for_repeated_where(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", slug="a", status="todo", tags=["frontend"])
    write_quest(log, "QST-bbbbb", slug="b", status="todo", tags=["frontend", "urgent"])

    result = run("list", "--in", str(log), "--where", "tags~frontend;tags~urgent")

    assert "QST-bbbbb" in result.out
    assert "QST-aaaaa" not in result.out


def test_semicolon_in_where_behaves_exactly_like_repeated_where_flags(
    isolated, make_log, write_quest, run
):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", slug="a", status="todo", priority="low")
    write_quest(log, "QST-bbbbb", slug="b", status="done", priority="low")

    semicolon = run("list", "--in", str(log), "--where", "status:exists;priority=low")
    repeated = run(
        "list", "--in", str(log), "--where", "status:exists", "--where", "priority=low"
    )

    assert semicolon.out == repeated.out


# --- --any: OR within a group, AND across groups and clauses -------------------


def test_any_matches_when_any_expression_in_the_group_holds(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", slug="a", status="parked")
    write_quest(log, "QST-bbbbb", slug="b", status="todo", blocked_by=["QST-aaaaa"])
    write_quest(log, "QST-ccccc", slug="c", status="todo")

    result = run(
        "list", "--in", str(log), "--where", "status:exists",
        "--any", "status=parked;blocked=true",
    )

    assert "QST-aaaaa" in result.out
    assert "QST-bbbbb" in result.out
    assert "QST-ccccc" not in result.out


def test_multiple_any_groups_are_anded_together(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", slug="a", type="bug", effort="s", status="parked")
    write_quest(log, "QST-bbbbb", slug="b", type="bug", effort="xl", status="parked")
    write_quest(log, "QST-ccccc", slug="c", type="chore", effort="s", status="parked")

    result = run(
        "list", "--in", str(log), "--where", "status:exists",
        "--any", "type=bug,feature",
        "--any", "effort=s,m",
    )

    assert "QST-aaaaa" in result.out
    assert "QST-bbbbb" not in result.out
    assert "QST-ccccc" not in result.out


def test_any_is_anded_with_plain_where_clauses(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", slug="a", type="bug", status="parked")
    write_quest(log, "QST-bbbbb", slug="b", type="chore", status="parked")

    result = run(
        "list", "--in", str(log), "--where", "status:exists",
        "--where", "type=bug,feature", "--any", "status=parked;status=todo",
    )

    assert "QST-aaaaa" in result.out
    assert "QST-bbbbb" not in result.out


def test_the_approved_example_resolves_as_documented(isolated, make_log, write_quest, run):
    """(type=bug OR feature) AND (effort=s OR m) AND (status=parked OR blocked=true)."""
    log = make_log(isolated)
    write_quest(
        log, "QST-aaaaa", slug="a", type="bug", effort="s", status="parked"
    )  # matches all three
    write_quest(
        log, "QST-bbbbb", slug="b", type="chore", effort="s", status="parked"
    )  # wrong type
    write_quest(
        log, "QST-ccccc", slug="c", type="feature", effort="xl", status="parked"
    )  # wrong effort
    write_quest(
        log, "QST-ddddd", slug="d", type="feature", effort="m", status="todo"
    )  # wrong status/blocked

    result = run(
        "list", "--in", str(log), "--where", "status:exists",
        "--any", "status=parked;blocked=true",
        "--any", "effort=s,m",
        "--where", "type=bug,feature",
    )

    ids = {line.split()[0] for line in result.out.splitlines()[1:] if line.startswith("QST-")}
    assert ids == {"QST-aaaaa"}


def test_any_works_with_a_computed_field(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", slug="a", status="todo")
    write_quest(log, "QST-bbbbb", slug="b", status="todo", blocked_by=["QST-aaaaa"])

    result = run("list", "--in", str(log), "--any", "blocked=true;status=done")

    assert "QST-bbbbb" in result.out
    assert "QST-aaaaa" not in result.out


def test_any_works_with_a_declared_custom_field(isolated, make_log, write_quest, run):
    log = make_log(isolated, schema={"fields": {"component": {"type": "string"}}})
    write_quest(log, "QST-aaaaa", slug="a", status="todo", component="api")
    write_quest(log, "QST-bbbbb", slug="b", status="todo", component="ui")

    result = run(
        "list", "--in", str(log), "--where", "status:exists", "--any", "component=api;component=db"
    )

    assert "QST-aaaaa" in result.out
    assert "QST-bbbbb" not in result.out


# --- summary discloses any-groups -----------------------------------------------


def test_summary_discloses_any_groups(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", slug="a", status="todo")

    result = run(
        "list", "--in", str(log), "--where", "status:exists",
        "--any", "status=parked;status=todo",
    )

    assert "status=parked;status=todo" in result.err
