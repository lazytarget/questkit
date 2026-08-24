"""Tests for `quest open <id>` (QST-lh95o): the `gh --web` analog -- launch
the resolved quest via an `obsidian://open?path=<absolute path>` URI through
the platform opener, falling back to `$EDITOR` and then to printing the path.
"""

from __future__ import annotations

from unittest.mock import patch

from questkit.commands.open_cmd import build_obsidian_uri


def test_build_obsidian_uri_urlencodes_the_absolute_path(tmp_path):
    path = tmp_path / "QST-aaaaa--a-quest.md"

    uri = build_obsidian_uri(path)

    assert uri.startswith("obsidian://open?path=")
    from urllib.parse import parse_qs, urlparse

    parsed = urlparse(uri)
    assert parse_qs(parsed.query)["path"] == [str(path)]


def test_open_launches_the_obsidian_uri_via_the_platform_opener(quest_log, run):
    result = run("new", "A quest", "--status", "todo")
    quest_id = result.out.strip().rsplit("/", 1)[-1].split("--")[0]
    path = next(quest_log.glob("QST-*.md"))

    with patch("questkit.commands.open_cmd.sys.platform", "linux"), \
            patch("questkit.commands.open_cmd.subprocess.run") as mock_run:
        result = run("open", quest_id)

    assert result.code == 0
    args, _kwargs = mock_run.call_args
    assert args[0][0] == "xdg-open"
    assert build_obsidian_uri(path) in args[0][1]


def test_open_falls_back_to_editor_when_the_opener_is_unavailable(quest_log, run, monkeypatch):
    result = run("new", "A quest", "--status", "todo")
    quest_id = result.out.strip().rsplit("/", 1)[-1].split("--")[0]
    monkeypatch.setenv("EDITOR", "myeditor")

    with patch("questkit.commands.open_cmd.sys.platform", "linux"), \
            patch("questkit.commands.open_cmd.subprocess.run", side_effect=FileNotFoundError), \
            patch("questkit.editing.subprocess.run") as mock_editor_run:
        result = run("open", quest_id)

    assert result.code == 0
    mock_editor_run.assert_called_once()


def test_open_falls_back_to_printing_the_path_when_no_editor_either(quest_log, run, monkeypatch):
    result = run("new", "A quest", "--status", "todo")
    quest_id = result.out.strip().rsplit("/", 1)[-1].split("--")[0]
    path = next(quest_log.glob("QST-*.md"))
    monkeypatch.delenv("EDITOR", raising=False)

    with patch("questkit.commands.open_cmd.sys.platform", "linux"), \
            patch("questkit.commands.open_cmd.subprocess.run", side_effect=FileNotFoundError):
        result = run("open", quest_id)

    assert result.code == 0
    assert str(path) in result.out


def test_open_editor_flag_skips_obsidian_entirely(quest_log, run, monkeypatch):
    result = run("new", "A quest", "--status", "todo")
    quest_id = result.out.strip().rsplit("/", 1)[-1].split("--")[0]
    monkeypatch.setenv("EDITOR", "myeditor")

    with patch("questkit.commands.open_cmd.subprocess.run") as mock_open_run, \
            patch("questkit.editing.subprocess.run") as mock_editor_run:
        result = run("open", quest_id, "--editor")

    assert result.code == 0
    mock_open_run.assert_not_called()
    mock_editor_run.assert_called_once()


def test_open_reports_a_clear_message_for_an_unknown_id(quest_log, run):
    result = run("open", "QST-zzzzz")

    assert result.code == 1
    assert "QST-zzzzz" in result.out


def test_open_resolves_in_by_project_name(isolated, make_log, write_quest, run, monkeypatch):
    log = make_log(isolated, "family", project="family")
    write_quest(log, "QST-aaaaa")
    monkeypatch.setenv("QST_ROOT", str(isolated))

    with patch("questkit.commands.open_cmd.sys.platform", "linux"), \
            patch("questkit.commands.open_cmd.subprocess.run") as mock_run:
        result = run("open", "QST-aaaaa", "--in", "family")

    assert result.code == 0
    mock_run.assert_called_once()
