"""Tests for resolving `--in` by project name as well as by path.

One rule: a value containing a `/` or `\\`, or naming a directory that exists
on disk, is a **path**. Anything else is a **project name**, matched against
each discovered log's `project:` under the sweep root. `project:` becomes
identity -- unique per log -- rather than a free label.

A path that is not itself a log expands to the logs beneath it: read commands
get all of them, write commands get exactly one or an actionable ambiguity
error -- the same guard `resolve_log_for_new` already implements, applied one
level up.
"""

from __future__ import annotations

import pytest

from questkit.discovery import (
    AmbiguousDestinationError,
    QuestLogNotFoundError,
    resolve_by_name_or_path,
    resolve_log,
)


def test_a_bare_name_resolves_to_its_log(isolated, make_log, monkeypatch):
    make_log(isolated, "family", project="family")
    monkeypatch.chdir(isolated)

    found = resolve_by_name_or_path("family", root=isolated)

    assert found == [isolated / "family" / "quests"]


def test_a_relative_path_still_resolves_as_a_path(isolated, make_log, monkeypatch):
    log = make_log(isolated)
    monkeypatch.chdir(isolated)

    assert resolve_by_name_or_path("./quests", root=isolated) == [log]


def test_a_dot_path_resolves_the_log_at_that_root(isolated, make_log, monkeypatch):
    log = make_log(isolated)
    monkeypatch.chdir(log)

    assert resolve_by_name_or_path(".", root=isolated) == [log]


def test_a_directory_containing_one_child_log_expands_to_it(isolated, make_log):
    log = make_log(isolated / "project", "alpha")

    assert resolve_by_name_or_path(str(isolated / "project"), root=isolated) == [log]


def test_a_directory_containing_several_logs_expands_to_all_for_reads(isolated, make_log):
    alpha = make_log(isolated / "group", "alpha")
    beta = make_log(isolated / "group", "beta")

    found = resolve_by_name_or_path(str(isolated / "group"), root=isolated)

    assert sorted(found) == sorted([alpha, beta])


def test_an_existing_directory_name_that_is_also_a_project_name_resolves_as_the_path(
    isolated, make_log, monkeypatch
):
    """Disk existence wins: `family` the directory beats `family` the project name."""
    named_family = make_log(isolated / "not-family", "family", project="family")
    path_family = make_log(isolated, "family", project="not-the-same-name")
    monkeypatch.chdir(isolated)

    found = resolve_by_name_or_path("family", root=isolated)

    assert found == [path_family]
    assert found != [named_family]


def test_an_unknown_name_errors_listing_known_projects_with_paths(isolated, make_log):
    make_log(isolated, "alpha", project="alpha")

    with pytest.raises(QuestLogNotFoundError) as exc:
        resolve_by_name_or_path("nonexistent", root=isolated)

    assert "alpha" in str(exc.value)


def test_a_name_matching_two_logs_errors_naming_both(isolated, make_log):
    a = make_log(isolated / "one", "dup", project="dup")
    b = make_log(isolated / "two", "dup", project="dup")

    with pytest.raises(QuestLogNotFoundError) as exc:
        resolve_by_name_or_path("dup", root=isolated)

    assert str(a) in str(exc.value)
    assert str(b) in str(exc.value)


def test_a_path_that_is_not_a_log_and_has_no_logs_beneath_it_errors(isolated):
    empty = isolated / "nowhere"
    empty.mkdir()

    with pytest.raises(QuestLogNotFoundError):
        resolve_by_name_or_path(str(empty), root=isolated)


def test_name_resolution_respects_an_explicit_root(isolated, make_log):
    outside = isolated.parent / "outside-family"
    try:
        make_log(outside, "family", project="family")
        with pytest.raises(QuestLogNotFoundError):
            resolve_by_name_or_path("family", root=isolated)
    finally:
        import shutil

        shutil.rmtree(outside, ignore_errors=True)


# --- resolve_log integration: single-target commands -------------------------------


def test_resolve_log_by_name(isolated, make_log, monkeypatch):
    log = make_log(isolated, "family", project="family")
    monkeypatch.setenv("QST_ROOT", str(isolated))

    assert resolve_log(explicit="family") == log


def test_resolve_log_still_resolves_explicit_paths(isolated, make_log, monkeypatch):
    log = make_log(isolated)
    monkeypatch.chdir(isolated)
    monkeypatch.setenv("QST_ROOT", str(isolated))

    assert resolve_log(explicit="./quests") == log


def test_resolve_log_a_single_child_log_directory(isolated, make_log, monkeypatch):
    log = make_log(isolated / "grocy-ecosystem", "grocy-ecosystem")
    monkeypatch.setenv("QST_ROOT", str(isolated))

    assert resolve_log(explicit=str(isolated / "grocy-ecosystem")) == log


def test_resolve_log_errors_ambiguously_for_a_single_target_command(isolated, make_log, monkeypatch):
    make_log(isolated / "group", "alpha")
    make_log(isolated / "group", "beta")
    monkeypatch.setenv("QST_ROOT", str(isolated))

    with pytest.raises(AmbiguousDestinationError):
        resolve_log(explicit=str(isolated / "group"))


def test_the_ambiguity_error_names_the_candidates(isolated, make_log, monkeypatch):
    alpha = make_log(isolated / "group", "alpha")
    beta = make_log(isolated / "group", "beta")
    monkeypatch.setenv("QST_ROOT", str(isolated))

    with pytest.raises(AmbiguousDestinationError) as exc:
        resolve_log(explicit=str(isolated / "group"))

    assert str(alpha) in str(exc.value)
    assert str(beta) in str(exc.value)


# --- CLI level ---------------------------------------------------------------------


def test_quest_new_resolves_in_by_project_name(isolated, make_log, run, monkeypatch):
    log = make_log(isolated, "family", project="family")
    monkeypatch.setenv("QST_ROOT", str(isolated))

    result = run("new", "A quest", "--status", "todo", "--in", "family")

    assert result.code == 0
    assert len(list(log.glob("QST-*.md"))) == 1


def test_quest_show_resolves_in_by_project_name(isolated, make_log, write_quest, run, monkeypatch):
    log = make_log(isolated, "family", project="family")
    write_quest(log, "QST-aaaaa")
    monkeypatch.setenv("QST_ROOT", str(isolated))

    result = run("show", "QST-aaaaa", "--in", "family")

    assert result.code == 0
    assert "QST-aaaaa" in result.out


def test_quest_new_into_an_ambiguous_directory_errors_naming_candidates(
    isolated, make_log, run, monkeypatch
):
    make_log(isolated / "group", "alpha")
    make_log(isolated / "group", "beta")
    monkeypatch.setenv("QST_ROOT", str(isolated))

    result = run("new", "A quest", "--status", "todo", "--in", str(isolated / "group"))

    assert result.code == 1
