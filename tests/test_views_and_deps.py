"""Tests for QST-37n0t's built-in views (next/stale/blocked) and quest deps.

Views are schema-defined prefills over `quest list`, exposed as bare
subcommands and overridable per log; `quest deps` is the one exception, a
real graph walk rather than a filter.
"""

from __future__ import annotations

from datetime import date, timedelta


def _iso_days_ago(n: int) -> date:
    return date.today() - timedelta(days=n)


# --- views.default drives the implicit filter --------------------------------


def test_a_log_overriding_statuses_lists_correctly_with_its_own_default_view(
    isolated, make_log, write_quest, run
):
    log = make_log(
        isolated,
        schema={
            "statuses": ["backlog", "doing", "shipped"],
            "terminal_statuses": ["shipped"],
            "views": {"default": {"where": ["status=doing"]}},
        },
    )
    write_quest(log, "QST-aaaaa", slug="a", status="doing")
    write_quest(log, "QST-bbbbb", slug="b", status="backlog")

    result = run("list", "--in", str(log))

    assert "QST-aaaaa" in result.out
    assert "QST-bbbbb" not in result.out


# --- quest next ----------------------------------------------------------------


def test_next_ranks_by_declared_priority_and_effort_order(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", slug="a", status="todo", priority="deferred", effort="s")
    write_quest(log, "QST-bbbbb", slug="b", status="todo", priority="critical", effort="xl")

    result = run("next", "--in", str(log))

    assert "QST-bbbbb" in result.out
    assert "QST-aaaaa" not in result.out


def test_next_honors_every_key_in_the_multi_key_sort(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", slug="a", status="todo", priority="high", effort="xl")
    write_quest(log, "QST-bbbbb", slug="b", status="todo", priority="high", effort="xs")

    result = run("next", "--in", str(log))

    assert "QST-bbbbb" in result.out
    assert "QST-aaaaa" not in result.out


def test_next_never_returns_a_blocked_quest(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", slug="a", status="todo", priority="critical", blocked_by=["QST-bbbbb"])
    write_quest(log, "QST-bbbbb", slug="b", status="todo", priority="deferred")

    result = run("next", "--in", str(log))

    assert "QST-bbbbb" in result.out
    assert "QST-aaaaa" not in result.out


def test_next_accepts_where_sort_and_limit_on_top_of_the_view(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", slug="a", status="todo", priority="critical", tags=["urgent"])
    write_quest(log, "QST-bbbbb", slug="b", status="todo", priority="high", tags=["chore"])

    result = run("next", "--in", str(log), "--where", "tags~chore")

    assert "QST-bbbbb" in result.out
    assert "QST-aaaaa" not in result.out


def test_next_under_a_logs_own_views_override_changes_definition_not_name(
    isolated, make_log, write_quest, run
):
    log = make_log(isolated, schema={"views": {"next": {"where": ["status=todo"], "limit": 2}}})
    write_quest(log, "QST-aaaaa", slug="a", status="todo")
    write_quest(log, "QST-bbbbb", slug="b", status="todo")

    result = run("next", "--in", str(log))

    assert "QST-aaaaa" in result.out
    assert "QST-bbbbb" in result.out


# --- quest stale -----------------------------------------------------------------


def test_stale_ranks_by_idle_descending(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", slug="a", status="todo", created=_iso_days_ago(40))
    write_quest(log, "QST-bbbbb", slug="b", status="todo", created=_iso_days_ago(15))

    result = run("stale", "--in", str(log), "--format", "csv", "--select", "id")

    lines = [line for line in result.out.splitlines() if line.strip()]
    assert lines == ["id", "QST-aaaaa", "QST-bbbbb"]


def test_stale_threshold_is_configurable_per_log(isolated, make_log, write_quest, run):
    log = make_log(isolated, schema={"views": {"stale": {"where": ["idle>100"], "sort": "idle:desc"}}})
    write_quest(log, "QST-aaaaa", slug="a", status="todo", created=_iso_days_ago(20))

    result = run("stale", "--in", str(log))

    assert "QST-aaaaa" not in result.out


# --- quest blocked -----------------------------------------------------------------


def test_blocked_view_lists_only_blocked_quests_ranked_by_blocks(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", slug="a", status="todo")
    write_quest(log, "QST-bbbbb", slug="b", status="todo", blocked_by=["QST-aaaaa"])
    write_quest(log, "QST-ccccc", slug="c", status="todo")

    result = run("blocked", "--in", str(log))

    assert "QST-bbbbb" in result.out
    assert "QST-aaaaa" not in result.out
    assert "QST-ccccc" not in result.out


# --- --view NAME for a user-defined, non-built-in view -----------------------------


def test_a_user_defined_view_is_reachable_via_list_dash_dash_view(
    isolated, make_log, write_quest, run
):
    log = make_log(isolated, schema={"views": {**{
        "default": {"where": ["status=todo,in-progress"]},
    }, "urgent": {"where": ["priority=critical"]}}})
    write_quest(log, "QST-aaaaa", slug="a", status="todo", priority="critical")
    write_quest(log, "QST-bbbbb", slug="b", status="todo", priority="low")

    result = run("list", "--in", str(log), "--view", "urgent")

    assert "QST-aaaaa" in result.out
    assert "QST-bbbbb" not in result.out


# --- under -A, views group and evaluate per log --------------------------------


def test_under_a_multi_log_sweep_each_log_uses_its_own_next_definition(
    isolated, make_log, write_quest, run, monkeypatch
):
    alpha = make_log(isolated, "alpha", project="alpha")
    beta = make_log(
        isolated, "beta", project="beta", schema={"views": {"next": {"where": ["status=todo"], "limit": 2}}}
    )
    write_quest(alpha, "QST-a1aaa", slug="a1", status="todo", priority="high")
    write_quest(alpha, "QST-a2aaa", slug="a2", status="todo", priority="deferred")
    write_quest(beta, "QST-b1bbb", slug="b1", status="todo")
    write_quest(beta, "QST-b2bbb", slug="b2", status="todo")
    monkeypatch.setenv("QST_ROOT", str(isolated))

    result = run("next", "-A")

    # alpha's default `next` (limit 1) yields exactly its top-priority quest;
    # beta's overridden `next` (limit 2) yields both of its quests.
    assert "QST-a1aaa" in result.out
    assert "QST-a2aaa" not in result.out
    assert "QST-b1bbb" in result.out
    assert "QST-b2bbb" in result.out


# --- quest deps ----------------------------------------------------------------


def test_deps_renders_a_direct_dependency(isolated, make_log, write_quest, run):
    log = make_log(isolated, project="proj")
    write_quest(log, "QST-aaaaa", slug="a", status="todo")
    write_quest(log, "QST-bbbbb", slug="b", status="todo", blocked_by=["QST-aaaaa"])

    result = run("deps", "QST-bbbbb", "--in", str(log))

    assert result.code == 0
    lines = result.out.splitlines()
    assert lines[0].startswith("QST-bbbbb")
    assert any(line.strip().startswith("QST-aaaaa") for line in lines[1:])


def test_deps_blocks_walks_the_reverse_direction(isolated, make_log, write_quest, run):
    log = make_log(isolated, project="proj")
    write_quest(log, "QST-aaaaa", slug="a", status="todo")
    write_quest(log, "QST-bbbbb", slug="b", status="todo", blocked_by=["QST-aaaaa"])

    result = run("deps", "QST-aaaaa", "--blocks", "--in", str(log))

    assert "QST-bbbbb" in result.out


def test_deps_marks_a_diamond_dependency_revisit_without_looping(
    isolated, make_log, write_quest, run
):
    log = make_log(isolated, project="proj")
    write_quest(log, "QST-aaaaa", slug="a", status="todo")
    write_quest(log, "QST-bbbbb", slug="b", status="todo", blocked_by=["QST-aaaaa"])
    write_quest(log, "QST-ccccc", slug="c", status="todo", blocked_by=["QST-aaaaa"])
    write_quest(log, "QST-ddddd", slug="d", status="todo", blocked_by=["QST-bbbbb", "QST-ccccc"])

    result = run("deps", "QST-ddddd", "--in", str(log))

    assert result.code == 0
    assert result.out.count("QST-aaaaa") == 2
    assert "(see above)" in result.out


def test_deps_traverses_a_qualified_ref_and_labels_the_log(
    isolated, make_log, write_quest, run, monkeypatch
):
    alpha = make_log(isolated, "alpha", project="alpha")
    beta = make_log(isolated, "beta", project="beta")
    write_quest(alpha, "QST-aaaaa", slug="a", status="todo")
    write_quest(beta, "QST-bbbbb", slug="b", status="todo", blocked_by=["alpha/QST-aaaaa"])
    monkeypatch.setenv("QST_ROOT", str(isolated))

    result = run("deps", "QST-bbbbb")

    assert "[alpha]" in result.out
    assert "[beta]" in result.out


def test_deps_unknown_id_is_an_error(isolated, make_log, run):
    make_log(isolated, project="proj")

    result = run("deps", "QST-zzzzz", "--in", str(isolated / "quests"))

    assert result.code == 1
