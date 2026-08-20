"""Tests for multi-key sort by declared order, and the --where comparison operators.

Both were measured broken before this change. `--sort priority:asc` returned
`critical, deferred, high, low, medium` (alphabetical), and
`--sort "a:asc,b:asc"` silently dropped every key after the first because
`partition(":")` put the rest in the *direction*.

The operators land here rather than with the computed fields because
`readiness:` rules are written in `!=`, which is three build-order items
earlier.
"""

from __future__ import annotations

import pytest

from questkit.commands import list_cmd

# --- --where parsing ---------------------------------------------------------------
#
# Check order matters: the compound operators must be tested before `=`, or
# `>=` is shredded into `>` plus a value that gains a leading `=`.


def test_parse_where_not_equal():
    assert list_cmd._parse_where("status!=draft") == ("status", "ne", "draft")


def test_parse_where_greater_or_equal_is_not_shredded():
    assert list_cmd._parse_where("idle>=14") == ("idle", "gte", "14")


def test_parse_where_less_or_equal_is_not_shredded():
    assert list_cmd._parse_where("idle<=14") == ("idle", "lte", "14")


def test_parse_where_greater_than():
    assert list_cmd._parse_where("idle>14") == ("idle", "gt", "14")


def test_parse_where_less_than():
    assert list_cmd._parse_where("idle<14") == ("idle", "lt", "14")


def test_parse_where_equal_still_works():
    assert list_cmd._parse_where("status=todo") == ("status", "eq", "todo")


def test_parse_where_exists_wins_over_the_operators():
    assert list_cmd._parse_where("owner:exists") == ("owner", "exists", None)


def test_parse_where_contains_still_works():
    assert list_cmd._parse_where("tags~cli") == ("tags", "contains", "cli")


# --- --where matching --------------------------------------------------------------


def test_matches_ne():
    assert list_cmd._matches({"status": "todo"}, "status", "ne", "draft")
    assert not list_cmd._matches({"status": "draft"}, "status", "ne", "draft")


def test_matches_ne_on_an_absent_field_is_true():
    """A quest with no `agentic` is genuinely `agentic != afk`."""
    assert list_cmd._matches({}, "agentic", "ne", "afk")


def test_matches_numeric_comparison():
    assert list_cmd._matches({"idle": 20}, "idle", "gt", "14")
    assert not list_cmd._matches({"idle": 10}, "idle", "gt", "14")
    assert list_cmd._matches({"idle": 14}, "idle", "gte", "14")
    assert not list_cmd._matches({"idle": 14}, "idle", "gt", "14")


def test_matches_numeric_comparison_on_a_string_number():
    """Frontmatter is untyped, so a count may arrive as a string."""
    assert list_cmd._matches({"idle": "20"}, "idle", "gt", "14")


def test_matches_iso_dates_compare_lexically():
    """ISO dates sort correctly as plain strings, so no date parsing is needed."""
    row = {"status_changed": "2026-08-01"}

    assert list_cmd._matches(row, "status_changed", "lt", "2026-08-05")
    assert not list_cmd._matches(row, "status_changed", "gt", "2026-08-05")


def test_matches_comparison_against_an_absent_field_is_false():
    assert not list_cmd._matches({}, "idle", "gt", "14")


def test_matches_comparison_of_non_numeric_strings_falls_back_to_string_order():
    assert list_cmd._matches({"tier": "spark"}, "tier", "gt", "blueprint")


# --- sorting -----------------------------------------------------------------------


@pytest.fixture
def sortable(isolated, make_log, write_quest, monkeypatch):
    log = make_log(isolated)
    write_quest(log, "QST-crit1", title="Crit", priority="critical", effort="xl")
    write_quest(log, "QST-defer", title="Defer", priority="deferred", effort="xs")
    write_quest(log, "QST-high1", title="High", priority="high", effort="m")
    write_quest(log, "QST-med01", title="Med", priority="medium", effort="s")
    write_quest(log, "QST-low01", title="Low", priority="low", effort="l")
    monkeypatch.chdir(isolated)
    return log


def _ids(result) -> list[str]:
    return [line.split()[0] for line in result.out.splitlines()[1:] if line.startswith("QST-")]


def test_sort_priority_uses_declared_order_not_alphabetical(sortable, run):
    """Before: critical, deferred, high, low, medium."""
    result = run("list", "--sort", "priority:asc", "--where", "status:exists")

    assert _ids(result) == ["QST-crit1", "QST-high1", "QST-med01", "QST-low01", "QST-defer"]


def test_sort_effort_uses_declared_order(sortable, run):
    """Before: l, m, s, xl, xs."""
    result = run("list", "--sort", "effort:asc", "--where", "status:exists")

    assert _ids(result) == ["QST-defer", "QST-med01", "QST-high1", "QST-low01", "QST-crit1"]


def test_sort_desc_reverses_declared_order(sortable, run):
    result = run("list", "--sort", "priority:desc", "--where", "status:exists")

    assert _ids(result)[0] == "QST-defer"


def test_multi_key_sort_consults_every_key(isolated, make_log, write_quest, run, monkeypatch):
    """Before: `partition(":")` dropped every key after the first."""
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", title="A", priority="high", effort="l")
    write_quest(log, "QST-bbbbb", title="B", priority="high", effort="xs")
    write_quest(log, "QST-ccccc", title="C", priority="critical", effort="m")
    monkeypatch.chdir(isolated)

    result = run("list", "--sort", "priority:asc,effort:asc", "--where", "status:exists")

    assert _ids(result) == ["QST-ccccc", "QST-bbbbb", "QST-aaaaa"]


def test_multi_key_sort_honors_a_per_key_direction(isolated, make_log, write_quest, run, monkeypatch):
    """`desc` on the second key never matched before, because it was never parsed."""
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", title="A", priority="high", effort="l")
    write_quest(log, "QST-bbbbb", title="B", priority="high", effort="xs")
    monkeypatch.chdir(isolated)

    result = run("list", "--sort", "priority:asc,effort:desc", "--where", "status:exists")

    assert _ids(result) == ["QST-aaaaa", "QST-bbbbb"]


def test_sort_on_an_unranked_field_is_still_a_string_sort(
    isolated, make_log, write_quest, run, monkeypatch
):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", title="Zebra")
    write_quest(log, "QST-bbbbb", title="Aardvark")
    monkeypatch.chdir(isolated)

    result = run("list", "--sort", "title:asc", "--where", "status:exists")

    assert _ids(result) == ["QST-bbbbb", "QST-aaaaa"]


def test_missing_values_still_sort_last_regardless_of_direction(
    isolated, make_log, write_quest, run, monkeypatch, absent
):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", title="A", effort="m")
    write_quest(log, "QST-bbbbb", title="B", effort=absent)
    write_quest(log, "QST-ccccc", title="C", effort="xs")
    monkeypatch.chdir(isolated)

    for direction in ("asc", "desc"):
        result = run("list", "--sort", f"effort:{direction}", "--where", "status:exists")
        assert _ids(result)[-1] == "QST-bbbbb", direction
