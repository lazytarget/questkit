"""Tests for the `status_changed` field and its write path.

`modified` cannot measure staleness: the `quest-bump-modified` hook writes it
on every commit and `quest format` used to write it on every run. The concrete
failure this field exists to prevent is `quest format --fill-defaults` across
the corpus giving every quest a fresh `modified`, laundering the whole backlog
into looking freshly worked.

So the load-bearing property is not "it gets written" -- it is "it is written
*only* on a real transition". An agent re-asserting a status it already holds
must not touch it, for exactly the same reason.
"""

from __future__ import annotations

from questkit.quest import Quest, effective_status_changed


def _id_of(result) -> str:
    return result.out.strip().split("/")[-1].split("--")[0]


def test_set_status_stamps_status_changed(quest_log, run, monkeypatch):
    monkeypatch.setattr("questkit.commands.set_cmd.today", lambda: "2026-08-21")
    quest_id = _id_of(run("new", "A quest", "--status", "todo"))

    run("set", quest_id, "status=in-progress")

    path = next(quest_log.glob(f"{quest_id}*.md"))
    assert str(Quest.load(path).get("status_changed")) == "2026-08-21"


def test_re_setting_the_same_status_changes_neither_timestamp(quest_log, run):
    """The laundering case: an agent re-asserting a status it already holds."""
    quest_id = _id_of(run("new", "A quest", "--status", "todo"))
    path = next(quest_log.glob(f"{quest_id}*.md"))
    run("set", quest_id, "status_changed=2020-01-01", "modified=2020-06-06")
    before = path.read_text()

    run("set", quest_id, "status=todo")

    assert path.read_text() == before
    assert "status_changed: 2020-01-01" in before


def test_done_stamps_status_changed(quest_log, run, monkeypatch):
    monkeypatch.setattr("questkit.commands.set_cmd.today", lambda: "2026-08-21")
    quest_id = _id_of(run("new", "A quest", "--status", "todo"))

    run("done", quest_id)

    path = next(quest_log.glob(f"{quest_id}*.md"))
    quest = Quest.load(path)
    assert quest.get("status") == "completed"
    assert str(quest.get("status_changed")) == "2026-08-21"


def test_setting_a_non_status_field_leaves_status_changed_alone(quest_log, run):
    quest_id = _id_of(run("new", "A quest", "--status", "todo"))
    run("set", quest_id, "status_changed=2020-01-01")
    path = next(quest_log.glob(f"{quest_id}*.md"))

    run("set", quest_id, "priority=high")

    quest = Quest.load(path)
    assert str(quest.get("status_changed")) == "2020-01-01"
    assert quest.get("priority") == "high"


def test_an_explicit_status_changed_assignment_is_not_overwritten(quest_log, run):
    """Setting both at once must respect what the caller asked for."""
    quest_id = _id_of(run("new", "A quest", "--status", "todo"))
    path = next(quest_log.glob(f"{quest_id}*.md"))

    run("set", quest_id, "status=in-progress", "status_changed=2019-03-03")

    assert str(Quest.load(path).get("status_changed")) == "2019-03-03"


# --- position in frontmatter ------------------------------------------------------


def _keys(path) -> list[str]:
    return list(Quest.load(path).frontmatter.keys())


def test_quest_new_never_writes_status_changed(quest_log, run):
    """A new quest is *born* at its status; it has not transitioned to it.

    So `created` is the honest answer for "when did this last move", which is
    exactly what `effective_status_changed` falls back to. Stamping it at
    creation would make the field indistinguishable from `created` on every
    quest that has never moved, and cost a line of frontmatter to say nothing.
    """
    quest_id = _id_of(run("new", "A quest", "--status", "todo"))

    assert "status_changed" not in _keys(next(quest_log.glob(f"{quest_id}*.md")))


def test_set_inserts_status_changed_between_created_and_modified(quest_log, run):
    """A field appended to the end would be correct YAML and wrong for a human reader."""
    quest_id = _id_of(run("new", "A quest", "--status", "todo"))
    path = next(quest_log.glob(f"{quest_id}*.md"))
    text = path.read_text()
    kept = [line for line in text.splitlines() if not line.startswith("status_changed")]
    path.write_text("\n".join(kept) + "\n")

    run("set", quest_id, "status=in-progress")

    keys = _keys(path)
    assert keys.index("created") < keys.index("status_changed") < keys.index("modified")


def test_a_new_quest_reports_created_as_its_effective_status_change(quest_log, run):
    quest_id = _id_of(run("new", "A draft"))
    quest = Quest.load(next(quest_log.glob(f"{quest_id}*.md")))

    assert effective_status_changed(quest.frontmatter) == str(quest.get("created"))


# --- null-safe fallback -----------------------------------------------------------


def test_effective_status_changed_falls_back_to_created(isolated, make_log, write_quest, absent):
    log = make_log(isolated)
    path = write_quest(log, "QST-aaaaa", created="2026-01-05", status_changed=absent)

    assert effective_status_changed(Quest.load(path).frontmatter) == "2026-01-05"


def test_effective_status_changed_prefers_the_field_when_present(
    isolated, make_log, write_quest
):
    log = make_log(isolated)
    path = write_quest(log, "QST-aaaaa", created="2026-01-05", status_changed="2026-07-07")

    assert effective_status_changed(Quest.load(path).frontmatter) == "2026-07-07"


def test_effective_status_changed_falls_back_through_a_blank_value(
    isolated, make_log, write_quest
):
    log = make_log(isolated)
    path = write_quest(log, "QST-aaaaa", created="2026-01-05", status_changed="")

    assert effective_status_changed(Quest.load(path).frontmatter) == "2026-01-05"


def test_effective_status_changed_is_none_when_neither_exists(absent):
    assert effective_status_changed({}) is None


# --- normalization and introspection ---------------------------------------------


def test_status_changed_normalizes_to_a_bare_date(isolated, make_log, write_quest):
    """It must round-trip unquoted like created/modified, or the CLI and Obsidian
    fight over quoting the same field forever."""
    log = make_log(isolated)
    path = write_quest(log, "QST-aaaaa")
    path.write_text(
        path.read_text().replace("modified:", "status_changed: '2026-07-07'\nmodified:")
    )

    Quest.load(path).save()

    assert "status_changed: 2026-07-07\n" in path.read_text()


def test_schema_describes_status_changed(quest_log, run):
    result = run("schema", "quest", "status_changed")

    assert result.code == 0
    assert "date" in result.out
    assert "status" in result.out.lower()


def test_status_changed_is_a_known_core_field(quest_log, run):
    result = run("schema", "quest", "--format", "json")

    assert "status_changed" in result.out
