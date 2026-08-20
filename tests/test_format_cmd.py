"""Tests for `quest format`: bulk re-normalization of a log's frontmatter."""

from __future__ import annotations

import pytest

from questkit.cli import main
from questkit.config import QuestLogConfig


@pytest.fixture(autouse=True)
def _no_quest_log_env(monkeypatch):
    monkeypatch.delenv("QUEST_LOG", raising=False)


def _write(quests_dir, name, text):
    (quests_dir / name).write_text(text, encoding="utf-8")


def test_format_reports_and_rewrites_changed_files(tmp_path, capsys):
    quests_dir = tmp_path / "quests"
    quests_dir.mkdir()
    QuestLogConfig().save(quests_dir)
    _write(
        quests_dir,
        "QST-abcde--needs-format.md",
        "---\n"
        "id: QST-abcde\n"
        "title: 'Some: Title'\n"
        "created: '2026-05-25'\n"
        "tags: [a]\n"
        "---\n\n"
        "## Description\n",
    )
    capsys.readouterr()

    exit_code = main(["format", "--in", str(quests_dir)])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "QST-abcde--needs-format.md: reformatted" in out
    assert "1 quest(s) checked, 1 reformatted" in out

    text = (quests_dir / "QST-abcde--needs-format.md").read_text()
    assert 'title: "Some: Title"' in text
    assert "created: 2026-05-25\n" in text
    assert "tags:\n  - a\n" in text


def test_format_is_a_no_op_on_already_normalized_files(tmp_path, capsys):
    quests_dir = tmp_path / "quests"
    quests_dir.mkdir()
    QuestLogConfig().save(quests_dir)
    assert main(["new", "Already tidy", "--in", str(quests_dir)]) == 0
    capsys.readouterr()

    exit_code = main(["format", "--in", str(quests_dir)])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "reformatted" not in out.split("checked")[0]  # no per-file reformat lines
    assert "1 quest(s) checked, 0 reformatted" in out


def test_format_does_not_touch_field_values(tmp_path):
    quests_dir = tmp_path / "quests"
    quests_dir.mkdir()
    QuestLogConfig().save(quests_dir)
    _write(
        quests_dir,
        "QST-abcde--example.md",
        "---\nid: QST-abcde\nstatus: draft\nmodified: '2026-08-13'\n---\n\n## Description\n",
    )

    assert main(["format", "--in", str(quests_dir)]) == 0

    text = (quests_dir / "QST-abcde--example.md").read_text()
    assert "status: draft" in text
    assert "modified: 2026-08-13" in text  # unquoted, but NOT bumped to today


def test_format_missing_log_errors(tmp_path):
    not_a_log = tmp_path / "nowhere"
    not_a_log.mkdir()

    assert main(["format", "--in", str(not_a_log)]) == 1


# --- mtime, explicit targets, and --check ---------------------------------------


def test_format_leaves_mtimes_alone_when_nothing_changes(quest_log, run):
    run("new", "Already tidy")
    run("format")
    mtimes = {p: p.stat().st_mtime_ns for p in quest_log.glob("QST-*.md")}

    result = run("format")

    assert result.code == 0
    assert "0 reformatted" in result.out
    assert {p: p.stat().st_mtime_ns for p in quest_log.glob("QST-*.md")} == mtimes


def test_format_accepts_multiple_space_separated_files(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    one = write_quest(log, "QST-aaaaa", slug="one", title="Some: quoted")
    two = write_quest(log, "QST-bbbbb", slug="two", created="2026-05-25")
    three = write_quest(log, "QST-ccccc", slug="three", title="Some: other")
    for path in (one, two, three):
        path.write_text(path.read_text().replace('"', "'"), encoding="utf-8")

    result = run("format", str(one), str(two))

    assert result.code == 0
    assert "2 quest(s) checked" in result.out
    assert "'" not in one.read_text()
    assert "'" in three.read_text()  # untargeted, so untouched


def test_format_a_directory_uses_that_logs_own_pattern(isolated, make_log, write_quest, run):
    """`pattern` is per-log config, so a hardcoded QST-*.md would skip a renamed prefix."""
    log = make_log(isolated, "renamed", pattern="TASK-*.md", prefix="TASK-")
    path = write_quest(log, "TASK-aaaaa", slug="example", title="Some: quoted")
    path.write_text(path.read_text().replace('"', "'"), encoding="utf-8")

    result = run("format", str(log))

    assert result.code == 0
    assert "1 quest(s) checked, 1 reformatted" in result.out
    assert "'" not in path.read_text()


def test_format_accepts_several_directories_each_with_its_own_config(
    isolated, make_log, write_quest, run
):
    alpha = make_log(isolated, "alpha")
    beta = make_log(isolated, "beta", pattern="TASK-*.md", prefix="TASK-")
    write_quest(alpha, "QST-aaaaa")
    write_quest(beta, "TASK-bbbbb")

    result = run("format", str(alpha), str(beta))

    assert result.code == 0
    assert "2 quest(s) checked" in result.out


def test_format_check_writes_nothing_and_exits_1_when_a_file_would_change(
    isolated, make_log, write_quest, run
):
    log = make_log(isolated)
    path = write_quest(log, "QST-aaaaa", title="Some: quoted")
    path.write_text(path.read_text().replace('"', "'"), encoding="utf-8")
    before = path.read_text()
    mtime_before = path.stat().st_mtime_ns

    result = run("format", "--check", str(log))

    assert result.code == 1
    assert path.read_text() == before
    assert path.stat().st_mtime_ns == mtime_before
    assert "would reformat" in result.out


def test_format_check_exits_0_when_everything_is_already_normalized(quest_log, run):
    run("new", "Already tidy")
    run("format")

    result = run("format", "--check")

    assert result.code == 0
    assert "0 would be reformatted" in result.out


def test_format_reports_a_file_whose_parent_is_not_a_log(isolated, write_quest, run):
    """hooks._schema_for already has this fallback; format reuses it rather than crashing."""
    stray = isolated / "stray"
    stray.mkdir()
    path = write_quest(stray, "QST-aaaaa", title="Some: quoted")
    path.write_text(path.read_text().replace('"', "'"), encoding="utf-8")

    result = run("format", str(path))

    assert result.code == 0
    assert "1 quest(s) checked, 1 reformatted" in result.out
    assert "'" not in path.read_text()


def test_format_with_no_targets_still_uses_the_resolved_log(quest_log, run):
    run("new", "Something")

    result = run("format")

    assert result.code == 0
    assert "1 quest(s) checked" in result.out


def test_format_a_missing_path_errors(isolated, make_log, run):
    make_log(isolated)

    result = run("format", str(isolated / "nope.md"))

    assert result.code == 1
