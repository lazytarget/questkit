"""Tests for pre-commit hook entry points: format, validate, bump-modified."""

from __future__ import annotations

from questkit.hooks import bump_modified_main, format_main, validate_main
from questkit.quest import Quest


def _write(path, text):
    path.write_text(text, encoding="utf-8")


def test_format_main_normalizes_and_reports(tmp_path, capsys):
    path = tmp_path / "QST-abcde--example.md"
    _write(
        path,
        "---\nid: QST-abcde\ntitle: 'A: B'\ncreated: '2026-05-25'\ntags: [x]\n---\n\n## Description\n",
    )
    capsys.readouterr()

    exit_code = format_main([str(path)])

    assert exit_code == 0
    assert f"{path}: reformatted" in capsys.readouterr().out
    text = path.read_text()
    assert 'title: "A: B"' in text
    assert "created: 2026-05-25\n" in text
    assert "tags:\n  - x\n" in text


def test_format_main_is_quiet_and_idempotent_on_second_run(tmp_path, capsys):
    path = tmp_path / "QST-abcde--example.md"
    _write(path, "---\nid: QST-abcde\ntitle: 'A: B'\n---\n\n## Description\n")
    format_main([str(path)])
    capsys.readouterr()

    exit_code = format_main([str(path)])

    assert exit_code == 0
    assert capsys.readouterr().out == ""


def test_format_main_does_not_change_modified(tmp_path):
    path = tmp_path / "QST-abcde--example.md"
    _write(path, "---\nid: QST-abcde\nmodified: '2020-01-01'\n---\n\n## Description\n")

    format_main([str(path)])

    assert Quest.load(path).get("modified").isoformat() == "2020-01-01"


def test_format_main_reports_bad_frontmatter_without_crashing(tmp_path, capsys):
    path = tmp_path / "QST-abcde--broken.md"
    _write(path, "no frontmatter here\n")

    exit_code = format_main([str(path)])

    assert exit_code == 0
    assert "missing YAML frontmatter" in capsys.readouterr().out


def test_bump_modified_main_does_not_rewrite_when_already_today(tmp_path, monkeypatch):
    path = tmp_path / "QST-abcde--example.md"
    _write(path, "---\nid: QST-abcde\nmodified: 2026-08-14\n---\n\n## Description\n")
    monkeypatch.setattr("questkit.hooks.today", lambda: "2026-08-14")
    before = path.read_text()

    bump_modified_main([str(path)])

    # A real `date` object (unquoted `modified`) compares equal to today's
    # string via str() -- no rewrite, so re-saving doesn't touch the file
    # (and doesn't spuriously mark it changed on every commit).
    assert path.read_text() == before


def test_bump_modified_main_rewrites_when_stale(tmp_path, monkeypatch):
    path = tmp_path / "QST-abcde--example.md"
    _write(path, "---\nid: QST-abcde\nmodified: 2020-01-01\n---\n\n## Description\n")
    monkeypatch.setattr("questkit.hooks.today", lambda: "2026-08-14")

    bump_modified_main([str(path)])

    assert Quest.load(path).get("modified").isoformat() == "2026-08-14"


def test_validate_main_still_works_unchanged(tmp_path, capsys):
    path = tmp_path / "QST-abcde--example.md"
    _write(
        path,
        "---\nid: QST-abcde\ntitle: T\ncreated: 2026-08-13\nmodified: 2026-08-13\n"
        "type: task\nstatus: draft\npriority: medium\ntags: []\naliases: [QST-abcde]\n"
        "---\n\n## Description\n",
    )

    assert validate_main([str(path)]) == 0
    assert capsys.readouterr().out == ""


def test_format_main_leaves_an_already_normalized_file_untouched(tmp_path, capsys):
    """The hook runs on every commit, so it must not touch mtimes needlessly."""
    path = tmp_path / "QST-abcde--example.md"
    _write(path, "---\nid: QST-abcde\ntitle: T\n---\n\n## Description\n")
    format_main([str(path)])
    capsys.readouterr()
    mtime_before = path.stat().st_mtime_ns

    format_main([str(path)])

    assert capsys.readouterr().out == ""
    assert path.stat().st_mtime_ns == mtime_before


def test_format_main_reports_only_the_files_it_actually_rewrote(tmp_path, capsys):
    needs = tmp_path / "QST-aaaaa--needs.md"
    clean = tmp_path / "QST-bbbbb--clean.md"
    _write(needs, "---\nid: QST-aaaaa\ntitle: 'Some: Title'\n---\n\n## Description\n")
    _write(clean, "---\nid: QST-bbbbb\ntitle: T\n---\n\n## Description\n")
    format_main([str(clean)])
    capsys.readouterr()

    format_main([str(needs), str(clean)])

    out = capsys.readouterr().out
    assert "QST-aaaaa--needs.md: reformatted" in out
    assert "QST-bbbbb--clean.md" not in out
