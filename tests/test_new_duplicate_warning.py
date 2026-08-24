"""Tests for QST-lc3d7: `quest new` warns (never blocks) on a title collision.

Detection is scoped to the target log, never blocks capture, and is
suppressible with `--allow-duplicate`.
"""

from __future__ import annotations


def _id_of(result) -> str:
    return result.out.strip().split("/")[-1].split("--")[0]


def test_exact_title_repeat_warns_and_still_creates(quest_log, run):
    first_id = _id_of(run("new", "Allow for --select and --distinct when listing quests"))

    result = run("new", "Allow for --select and --distinct when listing quests")

    assert result.code == 0
    assert "similar quest" in result.err.lower()
    assert first_id in result.err
    second_id = _id_of(result)
    assert second_id != first_id
    assert len(list(quest_log.glob("QST-*.md"))) == 2


def test_warning_names_id_status_and_title(quest_log, run):
    first_id = _id_of(run("new", "Fix the login redirect loop", "--status", "todo"))

    result = run("new", "Fix the login redirect loop")

    assert first_id in result.err
    assert "todo" in result.err
    assert "Fix the login redirect loop" in result.err


def test_near_match_by_token_overlap_warns(quest_log, run):
    _id_of(run("new", "Add support for --format json in list"))

    result = run("new", "Add support for --format json in list command")

    assert "similar quest" in result.err.lower()


def test_unrelated_titles_do_not_warn(quest_log, run):
    _id_of(run("new", "Fix the login redirect loop"))

    result = run("new", "Add dark mode support to the settings page")

    assert "similar quest" not in result.err.lower()


def test_allow_duplicate_suppresses_the_warning(quest_log, run):
    _id_of(run("new", "Fix the login redirect loop"))

    result = run("new", "Fix the login redirect loop", "--allow-duplicate")

    assert result.code == 0
    assert "similar quest" not in result.err.lower()


def test_exit_code_is_zero_even_with_a_duplicate_warning(quest_log, run):
    _id_of(run("new", "Fix the login redirect loop"))

    result = run("new", "Fix the login redirect loop")

    assert result.code == 0


def test_detection_is_scoped_to_the_target_log(isolated, make_log, write_quest, run):
    log_a = make_log(isolated, "alpha")
    log_b = make_log(isolated, "beta")
    write_quest(log_a, "QST-aaaaa", title="Fix the login redirect loop")

    result = run("new", "Fix the login redirect loop", "--in", str(log_b))

    assert result.code == 0
    assert "similar quest" not in result.err.lower()
