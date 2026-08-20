"""Tests for `quest list`'s dynamic --where filter engine and output formats."""

from __future__ import annotations

import json

import pytest

from questkit.cli import main
from questkit.commands import list_cmd

# --- unit tests: --where parsing and matching -----------------------------------


def test_parse_where_eq():
    assert list_cmd._parse_where("status=todo") == ("status", "eq", "todo")


def test_parse_where_contains():
    assert list_cmd._parse_where("tags~frontend") == ("tags", "contains", "frontend")


def test_parse_where_exists():
    assert list_cmd._parse_where("agentic:exists") == ("agentic", "exists", None)


def test_parse_where_malformed_raises():
    with pytest.raises(ValueError):
        list_cmd._parse_where("nonsense")


def test_matches_eq_is_case_insensitive_and_supports_or_set():
    row = {"status": "Todo"}
    assert list_cmd._matches(row, "status", "eq", "todo,in-progress")
    assert not list_cmd._matches(row, "status", "eq", "blocked")


def test_matches_eq_handles_bool_like_values():
    row = {"requires_downtime": True}
    assert list_cmd._matches(row, "requires_downtime", "eq", "true")


def test_matches_contains_list_field():
    row = {"tags": ["frontend", "urgent"]}
    assert list_cmd._matches(row, "tags", "contains", "frontend")
    assert not list_cmd._matches(row, "tags", "contains", "backend")


def test_matches_contains_comma_list_is_or_on_list_field():
    assert list_cmd._matches({"tags": ["frontend"]}, "tags", "contains", "frontend,backend")
    assert list_cmd._matches({"tags": ["backend"]}, "tags", "contains", "frontend,backend")
    assert not list_cmd._matches({"tags": ["design"]}, "tags", "contains", "frontend,backend")


def test_matches_contains_comma_list_is_or_on_scalar_field():
    row = {"title": "Fix the frontend bug"}
    assert list_cmd._matches(row, "title", "contains", "frontend,backend")
    assert not list_cmd._matches(row, "title", "contains", "database,backend")


def test_matches_exists():
    assert list_cmd._matches({"agentic": "afk"}, "agentic", "exists", None)
    assert not list_cmd._matches({"agentic": None}, "agentic", "exists", None)
    assert not list_cmd._matches({}, "agentic", "exists", None)


def test_apply_sort_missing_values_sort_last_regardless_of_direction():
    rows = [{"id": "a", "rank": "2"}, {"id": "b"}, {"id": "c", "rank": "1"}]

    asc = list_cmd._apply_sort(rows, "rank:asc")
    desc = list_cmd._apply_sort(rows, "rank:desc")

    assert [r["id"] for r in asc] == ["c", "a", "b"]
    assert [r["id"] for r in desc] == ["a", "c", "b"]


# --- CLI-level integration ------------------------------------------------------


@pytest.fixture
def quest_log(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("QUEST_LOG", raising=False)
    assert main(["init"]) == 0
    return tmp_path / "quests"


def _new(quest_log, title, capsys, status="todo", extra=None):
    assert main(["new", title, "--status", status, *(extra or [])]) == 0
    return capsys.readouterr().out.strip().split("/")[-1].split("--")[0]


def test_list_default_filters_to_active_statuses(quest_log, capsys):
    todo_id = _new(quest_log, "Todo item", capsys, status="todo")
    done_id = _new(quest_log, "Done item", capsys, status="todo")
    capsys.readouterr()
    assert main(["set", done_id, "status=completed"]) == 0
    capsys.readouterr()

    assert main(["list"]) == 0
    out = capsys.readouterr().out

    assert todo_id in out
    assert done_id not in out


def test_list_where_overrides_default_status_filter(quest_log, capsys):
    done_id = _new(quest_log, "Done item", capsys, status="todo")
    capsys.readouterr()
    assert main(["set", done_id, "status=completed"]) == 0
    capsys.readouterr()

    assert main(["list", "--where", "status=completed"]) == 0
    out = capsys.readouterr().out

    assert done_id in out


def test_list_where_tag_contains(quest_log, capsys):
    frontend_id = _new(quest_log, "Frontend work", capsys, extra=["--tag", "frontend"])
    _new(quest_log, "Backend work", capsys, extra=["--tag", "backend"])

    assert main(["list", "--where", "tags~frontend"]) == 0
    out = capsys.readouterr().out

    assert frontend_id in out
    assert "Backend work" not in out


def test_list_where_tag_contains_comma_list_is_or(quest_log, capsys):
    frontend_id = _new(quest_log, "Frontend work", capsys, extra=["--tag", "frontend"])
    backend_id = _new(quest_log, "Backend work", capsys, extra=["--tag", "backend"])
    _new(quest_log, "Docs work", capsys, extra=["--tag", "docs"])

    assert main(["list", "--where", "tags~frontend,backend"]) == 0
    out = capsys.readouterr().out

    assert frontend_id in out
    assert backend_id in out
    assert "Docs work" not in out


def test_list_repeated_where_on_same_field_is_and(quest_log, capsys):
    _new(quest_log, "Frontend only", capsys, extra=["--tag", "frontend"])
    both_id = _new(quest_log, "Frontend and urgent", capsys, extra=["--tag", "frontend", "--tag", "urgent"])

    assert main(["list", "--where", "tags~frontend", "--where", "tags~urgent"]) == 0
    out = capsys.readouterr().out

    assert both_id in out
    assert "Frontend only" not in out


def test_list_json_format_dumps_full_frontmatter(quest_log, capsys):
    quest_id = _new(quest_log, "JSON me", capsys)

    assert main(["list", "--where", "status:exists", "--format", "json"]) == 0
    rows = json.loads(capsys.readouterr().out)

    assert rows[0]["id"] == quest_id
    assert "created" in rows[0]


def test_list_select_overrides_table_headers(quest_log, capsys):
    """`--columns` is retired outright in favor of `--select` (QST-8hjjk)."""
    _new(quest_log, "Columns test", capsys)

    assert main(["list", "--select", "id,title"]) == 0
    out = capsys.readouterr().out

    assert "STATUS" not in out
    assert "ID" in out
    assert "TITLE" in out


def test_list_sort_and_limit(quest_log, capsys):
    _new(quest_log, "Low one", capsys, extra=["--priority", "low"])
    _new(quest_log, "High one", capsys, extra=["--priority", "high"])

    assert main(["list", "--sort", "priority", "--limit", "1"]) == 0
    out = capsys.readouterr().out

    assert "High one" in out
    assert "Low one" not in out


def test_list_out_writes_rendered_output_to_file(quest_log, capsys, tmp_path):
    _new(quest_log, "Out file test", capsys)
    out_file = tmp_path / "out.txt"

    assert main(["list", "--out", str(out_file)]) == 0
    capsys.readouterr()

    assert "Out file test" in out_file.read_text()


def test_list_all_aggregates_across_logs_with_project_column(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("QUEST_LOG", raising=False)
    proj_a = tmp_path / "proj_a"
    proj_b = tmp_path / "proj_b"
    proj_a.mkdir()
    proj_b.mkdir()
    monkeypatch.chdir(proj_a)
    assert main(["init", "--project", "proj_a"]) == 0
    monkeypatch.chdir(proj_b)
    assert main(["init", "--project", "proj_b"]) == 0

    monkeypatch.chdir(proj_a)
    assert main(["new", "In proj A", "--status", "todo"]) == 0
    capsys.readouterr()
    monkeypatch.chdir(proj_b)
    assert main(["new", "In proj B", "--status", "todo"]) == 0
    capsys.readouterr()

    monkeypatch.setenv("QST_ROOT", str(tmp_path))
    assert main(["list", "--all", "--format", "csv"]) == 0
    out = capsys.readouterr().out

    assert "proj_a" in out
    assert "proj_b" in out
    assert "project" in out.splitlines()[0]
