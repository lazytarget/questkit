"""Tests for `quest validate`'s notes-vs-errors split.

Slug drift is *documented as expected*: filenames are immutable by design so
links never break, so drift is what happens whenever a title is edited after
creation. Reporting it as an `error:` that fails the exit code means a
supported operation makes the flagship command red -- which is how a log ends
up permanently "failing" validation and everyone stops reading the output.

This is a channel, not a special case for one rule: any future informational
check (project drift heuristics, orphan detection) uses the same one.
"""

from __future__ import annotations


def _retitle(path, new_title: str) -> None:
    """Change the title without renaming the file -- i.e. cause slug drift."""
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        lines.append(f"title: {new_title}" if line.startswith("title:") else line)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_slug_drift_prints_as_a_note_not_an_error(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    path = write_quest(log, "QST-aaaaa", slug="original-slug")
    _retitle(path, "A completely different title")

    result = run("validate", "--in", str(log))

    assert "note:" in result.out
    assert "error:" not in result.out


def test_a_log_whose_only_finding_is_drift_exits_zero(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    path = write_quest(log, "QST-aaaaa", slug="original-slug")
    _retitle(path, "A completely different title")

    assert run("validate", "--in", str(log)).code == 0


def test_a_real_error_still_exits_one_and_still_prints_notes(
    isolated, make_log, write_quest, run, absent
):
    log = make_log(isolated)
    drifted = write_quest(log, "QST-aaaaa", slug="original-slug")
    _retitle(drifted, "A completely different title")
    write_quest(log, "QST-bbbbb", status="nonsense")

    result = run("validate", "--in", str(log))

    assert result.code == 1
    assert "error:" in result.out
    assert "note:" in result.out


def test_the_summary_counts_errors_and_notes_separately(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    drifted = write_quest(log, "QST-aaaaa", slug="original-slug")
    _retitle(drifted, "A completely different title")
    write_quest(log, "QST-bbbbb", status="nonsense")

    result = run("validate", "--in", str(log))

    assert "2 quest(s) checked, 1 error(s), 1 note(s)" in result.out


def test_a_clean_log_reports_no_errors_and_no_notes(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", slug="a-quest", title="A quest")

    result = run("validate", "--in", str(log))

    assert result.code == 0
    assert "no errors" in result.out


def test_no_notes_hides_them_without_changing_the_exit_code(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    path = write_quest(log, "QST-aaaaa", slug="original-slug")
    _retitle(path, "A completely different title")

    result = run("validate", "--in", str(log), "--no-notes")

    assert result.code == 0
    assert "note:" not in result.out


def test_notes_is_the_default_and_can_be_asked_for_explicitly(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    path = write_quest(log, "QST-aaaaa", slug="original-slug")
    _retitle(path, "A completely different title")

    assert "note:" in run("validate", "--in", str(log), "--notes").out


def test_no_notes_does_not_suppress_a_real_error(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-bbbbb", status="nonsense")

    result = run("validate", "--in", str(log), "--no-notes")

    assert result.code == 1
    assert "error:" in result.out


def test_a_file_with_both_reports_them_under_distinct_prefixes(
    isolated, make_log, write_quest, run
):
    log = make_log(isolated)
    path = write_quest(log, "QST-aaaaa", slug="original-slug", status="nonsense")
    _retitle(path, "A completely different title")

    result = run("validate", "--in", str(log))

    assert "error: status 'nonsense'" in result.out
    assert "note: filename slug" in result.out


def test_the_pre_commit_hook_still_excludes_drift(tmp_path):
    """The hook never enforced drift, and this must not change that."""
    from questkit.hooks import validate_main

    path = tmp_path / "QST-aaaaa--original-slug.md"
    path.write_text(
        "---\nid: QST-aaaaa\ntitle: A completely different title\ncreated: 2026-01-01\n"
        "modified: 2026-01-01\ntype: task\nstatus: todo\npriority: medium\n"
        "description: d\ntags: []\naliases:\n  - QST-aaaaa\n---\n\n## Description\n",
        encoding="utf-8",
    )

    assert validate_main([str(path)]) == 0
