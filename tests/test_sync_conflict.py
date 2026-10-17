"""Syncthing conflict copies must never be enumerated as quests (QST-oe92z).

Syncthing inserts `.sync-conflict-TIMESTAMP-DEVICE` *before* the extension,
so `QST-x7k2m--fix.sync-conflict-20260814-120000-ABCDEFG.md` matches both
`config.pattern` ("QST-*.md") and `find_by_id`'s `{id}*.md` glob just as
well as the real file -- enumeration, id resolution, and commit tracking
all need to exclude it, and `list`/`validate` need to warn on its presence.
"""

from __future__ import annotations

from questkit.quest import (
    count_sync_conflicts,
    find_by_id,
    glob_quests,
    is_sync_conflict_copy,
)


def _conflict_name(quest_id: str) -> str:
    return f"{quest_id}--fix-thing.sync-conflict-20260814-120000-ABCDEFG.md"


def test_is_sync_conflict_copy_detects_the_marker():
    assert is_sync_conflict_copy("QST-x7k2m--fix.sync-conflict-20260814-120000-ABCDEFG.md")
    assert not is_sync_conflict_copy("QST-x7k2m--fix.md")


def test_glob_quests_excludes_conflict_copies(tmp_path):
    real = tmp_path / "QST-x7k2m--fix.md"
    real.write_text("---\nid: QST-x7k2m\n---\n")
    conflict = tmp_path / _conflict_name("QST-x7k2m")
    conflict.write_text("---\nid: QST-x7k2m\n---\n")

    found = glob_quests(tmp_path, "QST-*.md")

    assert found == [real]


def test_count_sync_conflicts(tmp_path):
    (tmp_path / "QST-x7k2m--fix.md").write_text("---\nid: QST-x7k2m\n---\n")
    (tmp_path / _conflict_name("QST-x7k2m")).write_text("---\nid: QST-x7k2m\n---\n")
    (tmp_path / _conflict_name("QST-y8k2m")).write_text("---\nid: QST-y8k2m\n---\n")

    assert count_sync_conflicts(tmp_path, "QST-*.md") == 2


def test_find_by_id_ignores_a_conflict_copy(tmp_path):
    real = tmp_path / "QST-x7k2m--fix.md"
    real.write_text("---\nid: QST-x7k2m\n---\n")
    (tmp_path / _conflict_name("QST-x7k2m")).write_text("---\nid: QST-x7k2m\n---\n")

    assert find_by_id(tmp_path, "QST-x7k2m") == real


def test_find_by_id_returns_none_when_only_a_conflict_copy_exists(tmp_path):
    (tmp_path / _conflict_name("QST-x7k2m")).write_text("---\nid: QST-x7k2m\n---\n")

    assert find_by_id(tmp_path, "QST-x7k2m") is None


# --- CLI-level regression: list/validate/commit never surface a conflict copy ----


def _write_conflict_copy(quest_log, quest_id: str) -> None:
    real = next(quest_log.glob(f"{quest_id}*.md"))
    conflict = real.with_name(
        real.stem + ".sync-conflict-20260814-120000-ABCDEFG" + real.suffix
    )
    conflict.write_text(real.read_text(encoding="utf-8"), encoding="utf-8")


def _id_of(result) -> str:
    return result.out.strip().split("/")[-1].split("--")[0]


def test_list_excludes_conflict_copies_and_warns(quest_log, run):
    quest_id = _id_of(run("new", "A quest", "--status", "todo"))
    _write_conflict_copy(quest_log, quest_id)

    result = run("list", "--format", "json")

    import json as _json

    rows = _json.loads(result.out)
    assert len(rows) == 1  # one row, not two
    assert "sync-conflict" in result.err


def test_list_does_not_warn_when_no_conflicts(quest_log, run):
    _id_of(run("new", "A quest", "--status", "todo"))

    result = run("list", "--format", "json")

    assert "sync-conflict" not in result.err


def test_validate_excludes_conflict_copies_and_warns(quest_log, run):
    quest_id = _id_of(run("new", "A quest", "--status", "todo"))
    _write_conflict_copy(quest_log, quest_id)

    result = run("validate")

    assert "sync-conflict" in result.err
    assert result.out.count(f"{quest_id} ") <= 1


def test_commit_never_stages_a_conflict_copy(isolated, run):
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=isolated, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=isolated, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=isolated, check=True)
    run("init", str(isolated))
    quest_log = isolated / "quests"
    quest_id = _id_of(run("new", "A quest", "--status", "todo", "--in", str(isolated)))
    _write_conflict_copy(quest_log, quest_id)
    run("format", "--in", str(isolated))

    run("commit", "--in", str(isolated))

    tracked = subprocess.run(
        ["git", "ls-files"], cwd=isolated, capture_output=True, text=True, check=True
    ).stdout
    assert "sync-conflict" not in tracked
