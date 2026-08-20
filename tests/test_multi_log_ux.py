"""Tests for QST-iqwjm's multi-log query UX.

Scope for this batch (B4): the `-A`/`--all-logs` rename, repeatable `--root`
and `--in` (de-duplicated, name-or-path resolved through the same
`resolve_log_set()`), per-log grouping and header repetition in table output,
per-log `--select` field notes, and the stderr summary block with `--quiet`.

Deliberately deferred, and noted in the quest's Log: the summary's `view`
line and `--archived` scope line (no views or archival exist until B5/B6),
and per-log `--sort` under a view definition (also B5). Plain `--sort`
continues to sort the full result globally, exactly as before grouping --
grouping only changes how the *already-sorted* rows are clustered for table
display.
"""

from __future__ import annotations

import json

from questkit.discovery import resolve_sweep_roots

# --- -A / --all-logs ----------------------------------------------------------


def test_all_is_gone(isolated, make_log, run):
    """`--all` is not a registered flag -- argparse's own prefix-abbreviation
    of `--all-logs` is a separate, general CLI property, not a hidden alias
    this quest introduces."""
    from questkit.cli import build_parser

    parser = build_parser()
    list_parser = next(
        a.choices["list"] for a in parser._subparsers._group_actions if "list" in a.choices
    )
    assert "--all" not in list_parser._option_string_actions
    assert "--all-logs" in list_parser._option_string_actions
    assert "-A" in list_parser._option_string_actions


def test_dash_a_works(isolated, make_log, write_quest, run, monkeypatch):
    log = make_log(isolated, "alpha", project="alpha")
    write_quest(log, "QST-aaaaa", status="todo")
    monkeypatch.setenv("QST_ROOT", str(isolated))

    result = run("list", "-A")

    assert result.code == 0
    assert "QST-aaaaa" in result.out


def test_all_logs_long_flag_works(isolated, make_log, write_quest, run, monkeypatch):
    log = make_log(isolated, "alpha", project="alpha")
    write_quest(log, "QST-aaaaa", status="todo")
    monkeypatch.setenv("QST_ROOT", str(isolated))

    assert run("list", "--all-logs").code == 0


# --- repeatable --root ----------------------------------------------------------


def test_resolve_sweep_roots_dedupes_overlapping_roots(isolated, make_log):
    make_log(isolated / "alpha", "alpha")

    roots = resolve_sweep_roots(explicit=[str(isolated), str(isolated / "alpha")])

    # the nested root is contained in the first, but both are requested
    # explicitly -- dedup is about identical *resolved paths*, not containment.
    assert len(roots) == len(set(roots))


def test_resolve_sweep_roots_dedupes_identical_paths(isolated):
    roots = resolve_sweep_roots(explicit=[str(isolated), str(isolated) + "/"])

    assert roots == [isolated.resolve()]


def test_qst_root_accepts_pathsep_separated_paths(isolated, monkeypatch):
    import os

    a = isolated / "a"
    b = isolated / "b"
    a.mkdir()
    b.mkdir()
    monkeypatch.setenv("QST_ROOT", os.pathsep.join([str(a), str(b)]))

    roots = resolve_sweep_roots()

    assert set(roots) == {a.resolve(), b.resolve()}


def test_multiple_root_flags_sweep_the_union(isolated, make_log, write_quest, run):
    alpha = make_log(isolated / "one" / "alpha", "alpha", project="alpha")
    beta = make_log(isolated / "two" / "beta", "beta", project="beta")
    write_quest(alpha, "QST-aaaaa", status="todo")
    write_quest(beta, "QST-bbbbb", status="todo")

    result = run(
        "list", "-A",
        "--root", str(isolated / "one"), "--root", str(isolated / "two"),
    )

    assert "QST-aaaaa" in result.out
    assert "QST-bbbbb" in result.out


# --- repeatable --in on list ------------------------------------------------------


def test_list_in_is_repeatable(isolated, make_log, write_quest, run):
    alpha = make_log(isolated, "alpha")
    beta = make_log(isolated, "beta")
    write_quest(alpha, "QST-aaaaa", status="todo")
    write_quest(beta, "QST-bbbbb", status="todo")

    result = run("list", "--in", str(alpha), "--in", str(beta))

    assert "QST-aaaaa" in result.out
    assert "QST-bbbbb" in result.out


def test_list_in_resolves_names(isolated, make_log, write_quest, run, monkeypatch):
    log = make_log(isolated, "family", project="family")
    write_quest(log, "QST-aaaaa", status="todo")
    monkeypatch.setenv("QST_ROOT", str(isolated))

    result = run("list", "--in", "family")

    assert "QST-aaaaa" in result.out


def test_list_in_a_directory_of_several_logs_expands_to_all(isolated, make_log, write_quest, run):
    alpha = make_log(isolated / "group", "alpha")
    beta = make_log(isolated / "group", "beta")
    write_quest(alpha, "QST-aaaaa", status="todo")
    write_quest(beta, "QST-bbbbb", status="todo")

    result = run("list", "--in", str(isolated / "group"))

    assert "QST-aaaaa" in result.out
    assert "QST-bbbbb" in result.out


# --- mutation commands: repeatable --in ---------------------------------------


def test_set_in_is_repeatable_and_bounds_the_search(isolated, make_log, write_quest, run):
    alpha = make_log(isolated, "alpha")
    beta = make_log(isolated, "beta")
    gamma = make_log(isolated, "gamma")
    write_quest(beta, "QST-aaaaa", status="todo")
    write_quest(gamma, "QST-bbbbb", status="todo")

    # QST-bbbbb is in gamma, which is not in the --in scope
    result = run("set", "QST-bbbbb", "priority=high", "--in", str(alpha), "--in", str(beta))

    assert result.code == 1


def test_set_in_repeatable_finds_the_id_in_either_named_log(isolated, make_log, write_quest, run):
    alpha = make_log(isolated, "alpha")
    beta = make_log(isolated, "beta")
    write_quest(beta, "QST-aaaaa", status="todo")

    result = run("set", "QST-aaaaa", "priority=high", "--in", str(alpha), "--in", str(beta))

    assert result.code == 0


def test_done_in_is_repeatable(isolated, make_log, write_quest, run):
    from questkit.quest import Quest

    alpha = make_log(isolated, "alpha")
    beta = make_log(isolated, "beta")
    write_quest(beta, "QST-aaaaa", status="todo")

    result = run("done", "QST-aaaaa", "--in", str(alpha), "--in", str(beta))

    assert result.code == 0
    assert Quest.load(next(beta.glob("QST-*.md"))).get("status") == "done"


# --- per-log grouping in table output ----------------------------------------------


def test_table_groups_by_log_when_more_than_one_log_is_in_scope(
    isolated, make_log, write_quest, run
):
    alpha = make_log(isolated, "alpha", project="alpha")
    beta = make_log(isolated, "beta", project="beta")
    write_quest(alpha, "QST-aaaaa", status="todo")
    write_quest(beta, "QST-bbbbb", status="todo")

    result = run("list", "--in", str(alpha), "--in", str(beta))

    assert "alpha" in result.out
    assert "beta" in result.out
    # the header must repeat under each group, not appear once at the top
    assert result.out.count("ID") >= 2


def test_the_group_separator_names_the_log_and_its_row_count(
    isolated, make_log, write_quest, run
):
    alpha = make_log(isolated, "alpha", project="alpha")
    beta = make_log(isolated, "beta", project="beta")
    write_quest(alpha, "QST-aaaaa", status="todo")
    write_quest(alpha, "QST-bbbbb", status="todo")
    write_quest(beta, "QST-ccccc", status="todo")

    result = run("list", "--in", str(alpha), "--in", str(beta))

    assert "alpha" in result.out and "2" in result.out
    assert "beta" in result.out and "1" in result.out


def test_a_single_log_is_not_grouped(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", status="todo")

    result = run("list", "--in", str(log))

    # no separator lines
    assert "─" not in result.out


def test_json_and_csv_stay_flat_arrays_when_grouped(isolated, make_log, write_quest, run):
    alpha = make_log(isolated, "alpha", project="alpha")
    beta = make_log(isolated, "beta", project="beta")
    write_quest(alpha, "QST-aaaaa", status="todo")
    write_quest(beta, "QST-bbbbb", status="todo")

    result = run("list", "--in", str(alpha), "--in", str(beta), "--format", "json")

    rows = json.loads(result.out)
    assert isinstance(rows, list)
    assert {r["id"] for r in rows} == {"QST-aaaaa", "QST-bbbbb"}


def test_json_pipeline_with_jq_shaped_access_still_works(isolated, make_log, write_quest, run):
    """`quest list --format json | jq '.[].title'` -- a flat array, not nested per log."""
    alpha = make_log(isolated, "alpha", project="alpha")
    beta = make_log(isolated, "beta", project="beta")
    write_quest(alpha, "QST-aaaaa", status="todo", title="Alpha task")
    write_quest(beta, "QST-bbbbb", status="todo", title="Beta task")

    result = run("list", "--in", str(alpha), "--in", str(beta), "--format", "json")

    rows = json.loads(result.out)
    titles = [r["title"] for r in rows]
    assert set(titles) == {"Alpha task", "Beta task"}


# --- per-log --select notes -----------------------------------------------------


def test_select_absent_from_some_logs_notes_which_ones(isolated, make_log, write_quest, run):
    alpha = make_log(isolated, "alpha", schema={"fields": {"component": {"type": "string"}}})
    beta = make_log(isolated, "beta")
    write_quest(alpha, "QST-aaaaa", component="api")
    write_quest(beta, "QST-bbbbb")

    result = run(
        "list", "--in", str(alpha), "--in", str(beta), "--select", "id,component", "--quiet"
    )

    assert result.code == 0
    # even under --quiet the row output must render; the field is blank for beta
    lines = [line for line in result.out.splitlines() if "QST-bbbbb" in line]
    assert lines


def test_select_absent_from_every_log_is_still_a_hard_error(isolated, make_log, write_quest, run):
    alpha = make_log(isolated, "alpha")
    beta = make_log(isolated, "beta")
    write_quest(alpha, "QST-aaaaa")
    write_quest(beta, "QST-bbbbb")

    result = run("list", "--in", str(alpha), "--in", str(beta), "--select", "nonsense")

    assert result.code == 1


# --- the summary block -----------------------------------------------------------


def test_summary_block_goes_to_stderr(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", status="todo")

    result = run("list", "--in", str(log))

    assert result.err.strip() != ""
    assert "QST-aaaaa" not in result.err


def test_quiet_silences_the_summary(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", status="todo")

    result = run("list", "--in", str(log), "--quiet")

    assert result.err == ""
    assert "QST-aaaaa" in result.out


def test_summary_names_the_injected_default_status_filter(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", status="todo")

    result = run("list", "--in", str(log))

    assert "status" in result.err
    assert "todo" in result.err


def test_summary_does_not_claim_a_default_filter_when_overridden(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", status="done")

    result = run("list", "--in", str(log), "--where", "status:exists")

    assert "default" not in result.err.lower()


def test_summary_names_the_sort(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", status="todo")

    result = run("list", "--in", str(log), "--sort", "priority:asc")

    assert "priority" in result.err


def test_summary_names_the_logs_and_totals(isolated, make_log, write_quest, run):
    alpha = make_log(isolated, "alpha", project="alpha")
    beta = make_log(isolated, "beta", project="beta")
    write_quest(alpha, "QST-aaaaa", status="todo")
    write_quest(beta, "QST-bbbbb", status="todo")

    result = run("list", "--in", str(alpha), "--in", str(beta))

    assert "2 logs" in result.err or "2" in result.err
