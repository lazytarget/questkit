"""End-to-end CLI smoke test: init -> new -> list -> show -> set -> done -> validate."""

import pytest

from questkit.cli import main


@pytest.fixture
def quest_log(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("QUEST_LOG", raising=False)
    assert main(["init"]) == 0
    return tmp_path / "quests"


def test_full_lifecycle(quest_log, capsys):
    assert main(["new", "Fix the garage door", "--type", "task", "--status", "todo"]) == 0
    created_path = capsys.readouterr().out.strip()
    quest_id = created_path.split("/")[-1].split("--")[0]

    assert main(["list"]) == 0
    listed = capsys.readouterr().out
    assert quest_id in listed

    assert main(["show", quest_id]) == 0
    shown = capsys.readouterr().out
    assert "Fix the garage door" in shown

    assert main(["set", quest_id, "priority=high"]) == 0
    capsys.readouterr()

    assert main(["done", quest_id]) == 0
    capsys.readouterr()

    assert main(["show", quest_id]) == 0
    shown_after = capsys.readouterr().out
    assert "status: completed" in shown_after
    assert "priority: high" in shown_after

    assert main(["validate"]) == 0


def test_new_without_init_reports_actionable_error(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("QUEST_LOG", raising=False)

    exit_code = main(["new", "Orphan quest"])

    assert exit_code == 1
    err = capsys.readouterr().err
    assert "quest init" in err


def test_init_is_idempotent(quest_log):
    marker = quest_log / ".questkit.yaml"
    original = marker.read_text()

    assert main(["init"]) == 0

    assert marker.read_text() == original


def test_draft_quest_is_created_without_description(quest_log):
    assert main(["new", "Just an idea"]) == 0
    path = next(quest_log.glob("QST-*.md"))
    assert "description:" not in path.read_text()


def test_init_git_flag_sets_config_mode(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("QUEST_LOG", raising=False)

    assert main(["init", "--git", "auto", "--project", "common"]) == 0

    config_text = (tmp_path / "quests" / ".questkit.yaml").read_text()
    assert "git: auto" in config_text
    assert "project: common" in config_text
