"""Tests for `quest done` and `quest scrap`.

`quest done` used to write the literal string `completed`, which was a
hardcoded status value in a tool whose whole point is that the vocabulary is
declarable. It now writes `terminal_statuses[0]`, so a log using
`shipped`/`cancelled` gets `shipped`.

`quest scrap` is the mirror, added so the symmetry holds on both axes:
`done`/`scrap` as commands, `done`/`scrapped` as states.
"""

from __future__ import annotations

from questkit.quest import Quest


def _id_of(result) -> str:
    return result.out.strip().split("/")[-1].split("--")[0]


def test_done_writes_done_under_the_default_vocabulary(quest_log, run):
    quest_id = _id_of(run("new", "A quest", "--status", "todo"))

    assert run("done", quest_id).code == 0
    assert Quest.load(next(quest_log.glob(f"{quest_id}*.md"))).get("status") == "done"


def test_done_writes_the_logs_first_terminal_status(isolated, make_log, write_quest, run):
    log = make_log(
        isolated,
        schema={
            "statuses": ["todo", "in-review", "shipped", "cancelled"],
            "terminal_statuses": ["shipped", "cancelled"],
        },
    )
    path = write_quest(log, "QST-aaaaa", status="todo")

    assert run("done", "QST-aaaaa", "--in", str(log)).code == 0
    assert Quest.load(path).get("status") == "shipped"


def test_scrap_writes_scrapped(quest_log, run):
    quest_id = _id_of(run("new", "A quest", "--status", "todo"))

    assert run("scrap", quest_id).code == 0
    assert Quest.load(next(quest_log.glob(f"{quest_id}*.md"))).get("status") == "scrapped"


def test_scrap_writes_the_logs_last_terminal_status(isolated, make_log, write_quest, run):
    """`done` takes the first terminal status, `scrap` the last -- the pair."""
    log = make_log(
        isolated,
        schema={
            "statuses": ["todo", "in-review", "shipped", "cancelled"],
            "terminal_statuses": ["shipped", "cancelled"],
        },
    )
    path = write_quest(log, "QST-aaaaa", status="todo")

    assert run("scrap", "QST-aaaaa", "--in", str(log)).code == 0
    assert Quest.load(path).get("status") == "cancelled"


def test_scrap_falls_back_to_the_only_terminal_status(isolated, make_log, write_quest, run):
    log = make_log(isolated, schema={"statuses": ["todo", "done"]})
    path = write_quest(log, "QST-aaaaa", status="todo")

    assert run("scrap", "QST-aaaaa", "--in", str(log)).code == 0
    assert Quest.load(path).get("status") == "done"


def test_done_stamps_status_changed(quest_log, run, monkeypatch):
    monkeypatch.setattr("questkit.commands.set_cmd.today", lambda: "2026-08-21")
    quest_id = _id_of(run("new", "A quest", "--status", "todo"))

    run("done", quest_id)

    quest = Quest.load(next(quest_log.glob(f"{quest_id}*.md")))
    assert str(quest.get("status_changed")) == "2026-08-21"


def test_done_on_an_already_done_quest_is_a_no_op(quest_log, run):
    quest_id = _id_of(run("new", "A quest", "--status", "todo"))
    run("done", quest_id)
    path = next(quest_log.glob(f"{quest_id}*.md"))
    before = path.read_text()

    result = run("done", quest_id)

    assert result.code == 0
    assert path.read_text() == before


def test_completed_is_no_longer_a_valid_status(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", status="completed")

    result = run("validate", "--in", str(log))

    assert result.code == 1
    assert "completed" in result.out


def test_list_default_filter_no_longer_mentions_blocked(quest_log, run):
    """`blocked` left the enum, so the default filter cannot name it -- it now
    lives in `schema.DEFAULT_VIEWS["default"]` (QST-37n0t)."""
    from questkit.schema import DEFAULT_VIEWS

    assert DEFAULT_VIEWS["default"].where == ("status=todo,in-progress",)
