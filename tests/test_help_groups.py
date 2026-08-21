"""Tests for QST-zl5xc's grouped `--help` rendering.

Grouping is purely a rendering concern: every command stays reachable
exactly as `quest <verb>`, unrenamed and unnested. A subparser registered
without a group is a startup error, not a silently-ungrouped command.
"""

from __future__ import annotations

import argparse

import pytest

from questkit.cli import build_parser
from questkit.help_groups import GROUP_ORDER, GroupedSubparsers


def test_every_registered_command_appears_in_the_help_text():
    parser = build_parser()
    subparsers_action = next(
        a for a in parser._subparsers._group_actions if isinstance(a, argparse._SubParsersAction)
    )
    help_text = parser.format_help()
    for name in subparsers_action.choices:
        assert name in help_text


def test_help_renders_labelled_groups_in_order(capsys):
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--help"])
    out = capsys.readouterr().out
    positions = [out.index(f"\n{group}\n") for group in GROUP_ORDER if f"\n{group}\n" in out]
    assert positions == sorted(positions)
    assert "Capture" in out
    assert "Query" in out


def test_views_are_marked_in_the_query_group(capsys):
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--help"])
    out = capsys.readouterr().out
    for view in ("next", "stale", "blocked"):
        line = next(line for line in out.splitlines() if line.strip().startswith(view))
        assert "(view)" in line


def test_a_subcommand_still_reachable_as_a_flat_verb(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", status="todo")

    result = run("list", "--in", str(log))

    assert result.code == 0
    assert "QST-aaaaa" in result.out


def test_a_subparser_added_without_a_group_fails_validation():
    parser = argparse.ArgumentParser()
    raw = parser.add_subparsers(dest="command")
    grouped = GroupedSubparsers(raw)
    grouped.add("known", group="Capture", help="known command")
    raw.add_parser("rogue", help="added directly, bypassing .add()")

    with pytest.raises(RuntimeError, match="rogue"):
        grouped.validate()


def test_an_unknown_group_name_is_rejected_immediately():
    parser = argparse.ArgumentParser()
    raw = parser.add_subparsers(dest="command")
    grouped = GroupedSubparsers(raw)

    with pytest.raises(ValueError):
        grouped.add("x", group="Nonsense", help="x")


def test_a_subcommand_specific_help_is_unchanged(capsys):
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["new", "--help"])
    out = capsys.readouterr().out
    assert "usage: quest new" in out
    assert "Capture" not in out
