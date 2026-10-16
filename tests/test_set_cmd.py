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


# --- QST-hzlny: schema-type-driven list coercion, shared with `new --set` -----


def _frontmatter(path: Path) -> dict:
    import yaml

    text = path.read_text(encoding="utf-8")
    return yaml.safe_load(text.split("---")[1])


def test_set_blocked_by_single_id_writes_a_list(quest_log, run):
    quest_id = _id_of(run("new", "A quest", "--status", "todo"))
    path = next(quest_log.glob(f"{quest_id}*.md"))

    assert run("set", quest_id, "blocked_by=QST-aaaaa").code == 0

    assert _frontmatter(path)["blocked_by"] == ["QST-aaaaa"]


def test_set_blocked_by_comma_list(quest_log, run):
    quest_id = _id_of(run("new", "A quest", "--status", "todo"))
    path = next(quest_log.glob(f"{quest_id}*.md"))

    run("set", quest_id, "blocked_by=QST-aaaaa, QST-bbbbb")

    assert _frontmatter(path)["blocked_by"] == ["QST-aaaaa", "QST-bbbbb"]


def test_set_blocked_by_flow_list(quest_log, run):
    quest_id = _id_of(run("new", "A quest", "--status", "todo"))
    path = next(quest_log.glob(f"{quest_id}*.md"))

    run("set", quest_id, "blocked_by=[QST-aaaaa, QST-bbbbb]")

    assert _frontmatter(path)["blocked_by"] == ["QST-aaaaa", "QST-bbbbb"]


def test_set_blocked_by_empty_clears_to_empty_list(quest_log, run):
    quest_id = _id_of(run("new", "A quest", "--status", "todo"))
    path = next(quest_log.glob(f"{quest_id}*.md"))
    run("set", quest_id, "blocked_by=QST-aaaaa")

    run("set", quest_id, "blocked_by=")

    assert _frontmatter(path)["blocked_by"] == []


def test_set_empty_flow_list_clears_to_empty_list(quest_log, run):
    quest_id = _id_of(run("new", "A quest", "--status", "todo"))
    path = next(quest_log.glob(f"{quest_id}*.md"))
    run("set", quest_id, "blocked_by=QST-aaaaa")

    run("set", quest_id, "blocked_by=[]")

    assert _frontmatter(path)["blocked_by"] == []


def test_set_aliases_and_tags_use_the_same_list_coercion(quest_log, run):
    quest_id = _id_of(run("new", "A quest", "--status", "todo"))
    path = next(quest_log.glob(f"{quest_id}*.md"))

    run("set", quest_id, "aliases=[x, y]", "tags=a,b")

    fm = _frontmatter(path)
    assert fm["aliases"] == ["x", "y"]
    assert fm["tags"] == ["a", "b"]


def test_set_custom_list_field_is_coerced_by_declared_type(isolated, make_log, write_quest, run):
    log = make_log(isolated, schema={"fields": {"owners": {"type": "list"}}})
    path = write_quest(log, "QST-aaaaa")

    assert run("set", "--in", str(log), "QST-aaaaa", "owners=ann,bob").code == 0

    assert _frontmatter(path)["owners"] == ["ann", "bob"]


def test_set_leaves_scalar_fields_alone(quest_log, run):
    quest_id = _id_of(run("new", "A quest", "--status", "todo"))
    path = next(quest_log.glob(f"{quest_id}*.md"))

    run("set", quest_id, "component=a,b")

    assert _frontmatter(path)["component"] == "a,b"


def test_new_set_blocked_by_writes_a_list(quest_log, run):
    result = run("new", "A quest", "--set", "blocked_by=QST-aaaaa")
    path = next(quest_log.glob(f"{_id_of(result)}*.md"))
    assert _frontmatter(path)["blocked_by"] == ["QST-aaaaa"]


def test_new_set_blocked_by_flow_and_comma_forms(quest_log, run):
    flow = run("new", "Flow quest", "--set", "blocked_by=[QST-aaaaa, QST-bbbbb]")
    comma = run("new", "Comma quest", "--set", "blocked_by=QST-aaaaa,QST-bbbbb")
    for result in (flow, comma):
        path = next(quest_log.glob(f"{_id_of(result)}*.md"))
        assert _frontmatter(path)["blocked_by"] == ["QST-aaaaa", "QST-bbbbb"]


def test_new_set_empty_list_field_is_an_empty_list(quest_log, run):
    result = run("new", "A quest", "--set", "blocked_by=")
    path = next(quest_log.glob(f"{_id_of(result)}*.md"))
    assert _frontmatter(path)["blocked_by"] == []
