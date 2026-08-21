"""Tests for `quest set` — assignment coercion and the no-op write path.

The no-op cases matter more than they look. `quest set` is the command an
agent re-runs when it is unsure whether a state was already applied, and
every one of those re-runs used to bump `modified`, rewrite the file, and (in
a `git: auto` log) produce a commit. That laundered the staleness signal v3
exists to create.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def _id_of(result) -> str:
    return result.out.strip().split("/")[-1].split("--")[0]


def _age(path: Path, when: str = "2020-01-01") -> None:
    """Backdate `modified` so an unconditional bump is visible.

    Without this, a fresh quest's `modified` is already today, so a
    same-day test cannot tell "did not bump" from "bumped to the value it
    already had" -- the assertion would pass against the bug.
    """
    text = path.read_text(encoding="utf-8")
    lines = [
        f"modified: {when}" if line.startswith("modified:") else line
        for line in text.splitlines()
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_set_changes_a_field_and_bumps_modified(quest_log, run):
    quest_id = _id_of(run("new", "A quest", "--status", "todo"))
    path = next(quest_log.glob(f"{quest_id}*.md"))
    _age(path)

    result = run("set", quest_id, "status=in-progress")

    assert result.code == 0
    text = path.read_text()
    assert "status: in-progress" in text
    assert "modified: 2020-01-01" not in text


def test_set_to_the_current_value_writes_nothing_and_does_not_bump_modified(quest_log, run):
    quest_id = _id_of(run("new", "A quest", "--status", "todo"))
    path = next(quest_log.glob(f"{quest_id}*.md"))
    _age(path)
    before = path.read_text()
    mtime_before = path.stat().st_mtime_ns

    result = run("set", quest_id, "status=todo")

    assert result.code == 0
    assert "modified: 2020-01-01" in path.read_text()
    assert path.read_text() == before
    assert path.stat().st_mtime_ns == mtime_before


def test_set_reports_that_nothing_changed(quest_log, run):
    quest_id = _id_of(run("new", "A quest", "--status", "todo"))

    result = run("set", quest_id, "status=todo")

    assert "no change" in result.out.lower()


def test_set_bumps_modified_exactly_once_for_several_assignments(quest_log, run, monkeypatch):
    quest_id = _id_of(run("new", "A quest", "--status", "todo"))
    path = next(quest_log.glob(f"{quest_id}*.md"))

    run("set", quest_id, "status=in-progress", "priority=high")

    text = path.read_text()
    assert text.count("modified:") == 1
    assert "status: in-progress" in text
    assert "priority: high" in text


def test_set_writes_when_only_one_of_several_assignments_changes(quest_log, run):
    quest_id = _id_of(run("new", "A quest", "--status", "todo", "--priority", "high"))
    path = next(quest_log.glob(f"{quest_id}*.md"))

    result = run("set", quest_id, "status=todo", "priority=low")

    assert result.code == 0
    assert "priority: low" in path.read_text()
    assert "no change" not in result.out.lower()


def test_set_a_new_field_is_a_change(quest_log, run):
    quest_id = _id_of(run("new", "A quest", "--status", "todo"))
    run("format")

    result = run("set", quest_id, "owner=peter")

    assert "no change" not in result.out.lower()
    assert "owner: peter" in next(quest_log.glob(f"{quest_id}*.md")).read_text()


def test_set_tags_coercion_compares_the_coerced_value(quest_log, run):
    """`tags=a,b` becomes a list, so the comparison must be against the list."""
    quest_id = _id_of(run("new", "A quest", "--status", "todo", "--tag", "a", "--tag", "b"))
    path = next(quest_log.glob(f"{quest_id}*.md"))
    _age(path)
    mtime_before = path.stat().st_mtime_ns

    result = run("set", quest_id, "tags=a,b")

    assert "no change" in result.out.lower()
    assert path.stat().st_mtime_ns == mtime_before


def test_set_unknown_id_errors(quest_log, run):
    assert run("set", "QST-zzzzz", "status=todo").code == 1


def test_a_no_op_set_produces_no_empty_commit_in_a_git_auto_log(isolated, run, monkeypatch):
    subprocess.run(["git", "init", "-q"], cwd=isolated, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=isolated, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=isolated, check=True)
    run("init", str(isolated), "--git", "auto")
    quest_id = _id_of(run("new", "A quest", "--status", "todo", "--in", str(isolated / "quests")))
    run("format", "--in", str(isolated / "quests"))

    def _count() -> int:
        out = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=isolated,
            capture_output=True,
            text=True,
            check=True,
        )
        return int(out.stdout.strip())

    before = _count()
    run("set", quest_id, "status=todo", "--in", str(isolated / "quests"))

    assert _count() == before
