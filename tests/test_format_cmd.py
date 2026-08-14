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
