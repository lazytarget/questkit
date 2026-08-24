"""Tests for QST-46rdv: `--log MESSAGE` on `set`/`done`/`scrap`.

Appends a dated bullet to the quest's `## Log` section (created at the end
of the body if missing), in the same save as any field assignment. A pure
`--log` with no assignments is legal on `set`.
"""

from __future__ import annotations

from questkit.quest import Quest


def _id_of(result) -> str:
    return result.out.strip().split("/")[-1].split("--")[0]


def test_set_log_appends_a_dated_bullet(quest_log, run, monkeypatch):
    monkeypatch.setattr("questkit.commands.set_cmd.today", lambda: "2026-08-24")
    quest_id = _id_of(run("new", "A quest", "--status", "todo"))

    result = run("set", quest_id, "priority=high", "--log", "bumped priority")

    assert result.code == 0
    body = Quest.load(next(quest_log.glob(f"{quest_id}*.md"))).body
    assert "- 2026-08-24: bumped priority" in body


def test_set_log_only_is_legal_and_bumps_modified(quest_log, run, monkeypatch):
    monkeypatch.setattr("questkit.commands.set_cmd.today", lambda: "2026-08-24")
    quest_id = _id_of(run("new", "A quest", "--status", "todo"))
    path = next(quest_log.glob(f"{quest_id}*.md"))
    text = path.read_text().replace("modified: 2026-08-24", "modified: 2020-01-01")
    path.write_text(text)

    result = run("set", quest_id, "--log", "just a note")

    assert result.code == 0
    quest = Quest.load(path)
    assert "- 2026-08-24: just a note" in quest.body
    assert str(quest.get("modified")) == "2026-08-24"


def test_log_section_created_when_missing(quest_log, run, monkeypatch):
    monkeypatch.setattr("questkit.commands.set_cmd.today", lambda: "2026-08-24")
    quest_id = _id_of(run("new", "A quest", "--status", "todo", "--body", "## Description\n\nno log here.\n"))

    run("set", quest_id, "--log", "added later")

    body = Quest.load(next(quest_log.glob(f"{quest_id}*.md"))).body
    assert "## Log" in body
    assert "- 2026-08-24: added later" in body


def test_done_log_appends_in_the_same_save(quest_log, run, monkeypatch):
    monkeypatch.setattr("questkit.commands.set_cmd.today", lambda: "2026-08-24")
    quest_id = _id_of(run("new", "A quest", "--status", "todo"))

    result = run("done", quest_id, "--log", "shipped it")

    assert result.code == 0
    quest = Quest.load(next(quest_log.glob(f"{quest_id}*.md")))
    assert quest.get("status") == "done"
    assert "- 2026-08-24: shipped it" in quest.body


def test_scrap_log_appends_in_the_same_save(quest_log, run, monkeypatch):
    monkeypatch.setattr("questkit.commands.set_cmd.today", lambda: "2026-08-24")
    quest_id = _id_of(run("new", "A quest", "--status", "todo"))

    result = run("scrap", quest_id, "--log", "superseded by QST-y")

    assert result.code == 0
    quest = Quest.load(next(quest_log.glob(f"{quest_id}*.md")))
    assert quest.get("status") == "scrapped"
    assert "- 2026-08-24: superseded by QST-y" in quest.body


def test_no_log_flag_leaves_the_log_section_untouched(quest_log, run):
    quest_id = _id_of(run("new", "A quest", "--status", "todo"))
    path = next(quest_log.glob(f"{quest_id}*.md"))
    before = Quest.load(path).body

    run("set", quest_id, "priority=high")

    after = Quest.load(path).body
    assert after == before
