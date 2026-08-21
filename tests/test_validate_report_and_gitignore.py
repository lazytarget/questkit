"""Tests for QST-e6g6t's `quest validate --report FILE` and `quest init`'s
`.gitignore` entry for `_validation.md`.

`_validation.md` is derived state (Syncthing-transported, not git-tracked);
both pieces exist so the realm-01 timer's `quest validate --report
quests/_validation.md || true` never leaves stale or untracked cruft behind.
"""

from __future__ import annotations


def test_report_is_written_when_there_are_errors(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", status="nonsense")
    report = log / "_validation.md"

    result = run("validate", "--in", str(log), "--report", str(report))

    assert result.code == 1
    assert report.is_file()
    text = report.read_text()
    assert "QST-aaaaa" in text
    assert "error" in text.lower()


def test_report_is_deleted_when_the_log_is_clean(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", status="todo")
    report = log / "_validation.md"
    report.write_text("stale findings from a previous run\n")

    result = run("validate", "--in", str(log), "--report", str(report))

    assert result.code == 0
    assert not report.exists()


def test_without_report_no_file_is_written(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", status="nonsense")

    run("validate", "--in", str(log))

    assert not (log / "_validation.md").exists()


def test_exit_code_semantics_are_unaffected_by_report(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", status="todo")

    result = run("validate", "--in", str(log), "--report", str(log / "_validation.md"))

    assert result.code == 0


# --- quest init .gitignore ---------------------------------------------------


def test_init_creates_a_gitignore_ignoring_validation_md(isolated, run):
    run("init", str(isolated))

    gitignore = isolated / "quests" / ".gitignore"
    assert gitignore.is_file()
    assert "_validation.md" in gitignore.read_text().splitlines()


def test_init_appends_to_an_existing_gitignore(isolated, run):
    quests_dir = isolated / "quests"
    quests_dir.mkdir()
    (quests_dir / ".gitignore").write_text("*.tmp\n")

    run("init", str(isolated))

    text = (quests_dir / ".gitignore").read_text()
    assert "*.tmp" in text
    assert "_validation.md" in text.splitlines()


def test_init_is_idempotent_on_gitignore(isolated, run):
    run("init", str(isolated))
    gitignore = isolated / "quests" / ".gitignore"
    before = gitignore.read_text()

    run("init", str(isolated))

    assert gitignore.read_text() == before
