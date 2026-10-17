"""Tests for `quest edit <id>` (QST-grmbv): open the resolved quest in
$EDITOR, with the same id resolution `quest show` uses, then re-save through
`Quest.save()` so hand edits are normalized immediately.
"""

from __future__ import annotations

from unittest.mock import patch

from questkit.quest import Quest


def test_edit_opens_the_resolved_quest_in_editor(quest_log, run, monkeypatch):
    result = run("new", "A quest", "--status", "todo")
    quest_id = result.out.strip().rsplit("/", 1)[-1].split("--")[0]
    monkeypatch.setenv("EDITOR", "myeditor")

    with patch("questkit.editing.subprocess.run") as mock_run:
        result = run("edit", quest_id)

    assert result.code == 0
    path = next(quest_log.glob("QST-*.md"))
    mock_run.assert_called_once_with(["myeditor", str(path)])


def test_edit_without_editor_set_prints_a_clean_message_and_skips(quest_log, run, monkeypatch):
    result = run("new", "A quest", "--status", "todo")
    quest_id = result.out.strip().rsplit("/", 1)[-1].split("--")[0]
    monkeypatch.delenv("EDITOR", raising=False)

    with patch("questkit.editing.subprocess.run") as mock_run:
        result = run("edit", quest_id)

    assert result.code == 0
    assert "$EDITOR" in result.out
    mock_run.assert_not_called()


def test_edit_renormalizes_the_file_after_the_editor_exits(quest_log, run, monkeypatch):
    result = run("new", "A quest", "--status", "todo")
    quest_id = result.out.strip().rsplit("/", 1)[-1].split("--")[0]
    path = next(quest_log.glob("QST-*.md"))
    monkeypatch.setenv("EDITOR", "myeditor")

    def _simulate_hand_edit(argv):
        # Reorder frontmatter by hand, as a real editor save would -- `save()`
        # (not `reorder()`, which needs a schema) still normalizes quoting/
        # formatting, which is the guarantee under test here.
        quest = Quest.load(path)
        quest.frontmatter["title"] = "A quest -- hand edited"
        quest.save()

    with patch("questkit.editing.subprocess.run", side_effect=_simulate_hand_edit):
        result = run("edit", quest_id)

    assert result.code == 0
    assert Quest.load(path).get("title") == "A quest -- hand edited"


def test_edit_reports_a_clear_message_for_an_unknown_id(quest_log, run):
    result = run("edit", "QST-zzzzz")

    assert result.code == 1
    assert "QST-zzzzz" in result.out


def test_edit_resolves_in_by_project_name(isolated, make_log, write_quest, run, monkeypatch):
    log = make_log(isolated, "family", project="family")
    write_quest(log, "QST-aaaaa")
    monkeypatch.setenv("QST_ROOT", str(isolated))
    monkeypatch.setenv("EDITOR", "myeditor")

    with patch("questkit.editing.subprocess.run") as mock_run:
        result = run("edit", "QST-aaaaa", "--in", "family")

    assert result.code == 0
    mock_run.assert_called_once()
