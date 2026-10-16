"""QST-f0329: two physical logs declaring one `project:` name (the git-worktree case).

Policy under test: pure enumeration never hard-fails on a collision (it warns
once on stderr and labels the logs by path); single-log resolution never
silently picks one of several matches, and `--in` accepts a path to
disambiguate.
"""

from __future__ import annotations

import json

import pytest

from questkit.discovery import QuestLogNotFoundError, resolve_by_name_or_path


@pytest.fixture
def twin_logs(isolated, make_log, write_quest, monkeypatch):
    """Primary checkout + worktree checkout, both `project: twin`."""
    primary = make_log(isolated / "main", "quests", project="twin")
    worktree = make_log(isolated / "main-worktrees" / "feature-x", "quests", project="twin")
    write_quest(primary, "QST-aaaaa", title="Primary only", status="todo")
    write_quest(worktree, "QST-bbbbb", title="Worktree only", status="todo")
    monkeypatch.setenv("QST_ROOT", str(isolated))
    return primary, worktree


def test_logs_lists_both_with_paths_and_warns_instead_of_erroring(twin_logs, run, isolated):
    primary, worktree = twin_logs

    result = run("logs", "--root", str(isolated))

    assert result.code == 0
    assert "main/quests" in result.out
    assert "main-worktrees/feature-x/quests" in result.out
    assert result.err.lower().count("warning") == 1
    assert str(primary) in result.err
    assert str(worktree) in result.err


def test_logs_json_lists_both_on_a_collision(twin_logs, run, isolated):
    result = run("logs", "--root", str(isolated), "--format", "json")

    assert result.code == 0
    assert len(json.loads(result.out)) == 2


def test_list_all_does_not_merge_colliding_logs_under_one_header(twin_logs, run):
    primary, worktree = twin_logs

    result = run("list", "-A")

    assert result.code == 0
    headers = [line for line in result.out.splitlines() if line.startswith("──")]
    assert len(headers) == 2
    assert headers[0] != headers[1]
    assert all("twin" in h for h in headers)
    assert any("feature-x" in h for h in headers)
    assert "QST-aaaaa" in result.out and "QST-bbbbb" in result.out
    assert result.err.lower().count("warning") == 1
    assert str(primary) in result.err and str(worktree) in result.err


def test_list_all_json_rows_keep_the_real_project_name(twin_logs, run):
    result = run("list", "-A", "--format", "json")

    assert result.code == 0
    assert {row["project"] for row in json.loads(result.out)} == {"twin"}


def test_unique_project_names_get_no_warning_and_plain_headers(
    isolated, make_log, write_quest, run, monkeypatch
):
    a = make_log(isolated, "alpha", project="alpha")
    b = make_log(isolated, "beta", project="beta")
    write_quest(a, "QST-aaaaa")
    write_quest(b, "QST-bbbbb")
    monkeypatch.setenv("QST_ROOT", str(isolated))

    result = run("list", "-A")

    assert "warning" not in result.err.lower()
    assert any(line.startswith("── alpha ") for line in result.out.splitlines())


def test_in_name_that_is_ambiguous_errors_listing_every_candidate(twin_logs, run):
    primary, worktree = twin_logs

    result = run("list", "--in", "twin")

    assert result.code == 1
    assert str(primary) in result.err and str(worktree) in result.err
    assert "--in" in result.err and "path" in result.err.lower()


def test_in_path_resolves_one_of_the_colliding_logs(twin_logs, run):
    _, worktree = twin_logs

    result = run("list", "--in", str(worktree))

    assert result.code == 0
    assert "QST-bbbbb" in result.out
    assert "QST-aaaaa" not in result.out


def test_in_accepts_the_project_directory_as_well_as_the_quests_dir(twin_logs, run):
    primary, _ = twin_logs

    result = run("list", "--in", str(primary.parent))

    assert result.code == 0
    assert "QST-aaaaa" in result.out


def test_write_command_by_ambiguous_name_refuses_to_guess(twin_logs, run):
    primary, worktree = twin_logs
    path = next(primary.glob("QST-aaaaa*.md"))
    before = path.read_text()

    result = run("set", "QST-aaaaa", "status=in-progress", "--in", "twin")

    assert result.code == 1
    assert str(primary) in result.err and str(worktree) in result.err
    assert path.read_text() == before


@pytest.mark.parametrize("cmd", ["done", "scrap"])
def test_done_and_scrap_by_ambiguous_name_refuse_to_guess(twin_logs, run, cmd):
    primary, _ = twin_logs
    path = next(primary.glob("QST-aaaaa*.md"))
    before = path.read_text()

    result = run(cmd, "QST-aaaaa", "--in", "twin")

    assert result.code == 1
    assert path.read_text() == before


def test_write_command_by_path_works(twin_logs, run):
    _, worktree = twin_logs

    result = run("set", "QST-bbbbb", "status=in-progress", "--in", str(worktree))

    assert result.code == 0
    assert "in-progress" in next(worktree.glob("QST-bbbbb*.md")).read_text()


@pytest.mark.parametrize("cmd", ["show", "edit", "open"])
def test_read_by_id_commands_refuse_an_ambiguous_name(twin_logs, run, cmd):
    primary, worktree = twin_logs

    result = run(cmd, "QST-aaaaa", "--in", "twin")

    assert result.code == 1
    assert str(primary) in result.err and str(worktree) in result.err


def test_new_in_ambiguous_name_refuses_to_guess(twin_logs, run):
    primary, worktree = twin_logs
    before = sorted(p.name for p in primary.glob("QST-*.md"))

    result = run("new", "Something", "--in", "twin")

    assert result.code == 1
    assert sorted(p.name for p in primary.glob("QST-*.md")) == before
    assert not list(worktree.glob("QST-*Something*"))


def test_same_id_in_both_logs_refuses_to_guess_without_in(isolated, make_log, write_quest, run, monkeypatch):
    a = make_log(isolated / "one", "x", project="dup")
    b = make_log(isolated / "two", "x", project="dup")
    write_quest(a, "QST-sameid", title="Copy A")
    write_quest(b, "QST-sameid", title="Copy B")
    monkeypatch.setenv("QST_ROOT", str(isolated))

    result = run("set", "QST-sameid", "status=in-progress")

    assert result.code == 1
    assert str(a) in result.err and str(b) in result.err


def test_same_id_in_both_logs_resolves_with_a_path(isolated, make_log, write_quest, run, monkeypatch):
    a = make_log(isolated / "one", "x", project="dup")
    b = make_log(isolated / "two", "x", project="dup")
    write_quest(a, "QST-sameid", title="Copy A")
    write_quest(b, "QST-sameid", title="Copy B")
    monkeypatch.setenv("QST_ROOT", str(isolated))

    result = run("set", "QST-sameid", "status=in-progress", "--in", str(b))

    assert result.code == 0
    assert "in-progress" in next(b.glob("QST-sameid*.md")).read_text()
    assert "in-progress" not in next(a.glob("QST-sameid*.md")).read_text()


def test_resolve_by_name_error_says_how_to_disambiguate(twin_logs, isolated):
    with pytest.raises(QuestLogNotFoundError) as exc:
        resolve_by_name_or_path("twin", root=isolated)

    assert "--in <path>" in str(exc.value)


def test_doctor_warns_once_on_stderr_and_does_not_fail(twin_logs, run, isolated):
    result = run("doctor", "--root", str(isolated))

    assert "project" not in result.out.lower()
    assert result.err.lower().count("declared by") == 1
