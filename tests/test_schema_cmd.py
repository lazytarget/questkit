"""Tests for `quest schema` — schema introspection for agents."""

from __future__ import annotations

import json

import pytest

from questkit.cli import main


@pytest.fixture
def quest_log(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("QUEST_LOG", raising=False)
    assert main(["init"]) == 0
    return tmp_path / "quests"


def test_schema_quest_dumps_full_schema_as_json(quest_log, capsys):
    assert main(["schema", "quest"]) == 0
    data = json.loads(capsys.readouterr().out)

    assert "todo" in data["statuses"]
    assert data["fields"] == {}


def test_schema_quest_field_returns_just_that_array(quest_log, capsys):
    assert main(["schema", "quest", "status"]) == 0
    data = json.loads(capsys.readouterr().out)

    assert set(data) == {
        "draft",
        "todo",
        "in-progress",
        "blocked",
        "parked",
        "completed",
        "scrapped",
    }


def test_schema_quest_custom_field_returns_its_spec(quest_log, capsys):
    config_path = quest_log / ".questkit.yaml"
    with config_path.open("a", encoding="utf-8") as handle:
        handle.write("schema:\n  fields:\n    sprint:\n      type: string\n      required: true\n")

    assert main(["schema", "quest", "sprint"]) == 0
    data = json.loads(capsys.readouterr().out)

    assert data == {"type": "string", "required": True}


def test_schema_quest_unknown_field_errors(quest_log, capsys):
    exit_code = main(["schema", "quest", "not-a-field"])

    assert exit_code == 1
    assert "unknown schema field" in capsys.readouterr().out


def test_schema_quest_table_format_is_not_json(quest_log, capsys):
    assert main(["schema", "quest", "status", "--format", "table"]) == 0
    out = capsys.readouterr().out

    assert "todo" in out
    assert "[" not in out
