"""Tests for QST-lcsza's archival: a core `archived:` field, per-quest and
whole-log commands, and the `--archived` query axis.

Archival is orthogonal to `status` -- it answers a retention question, not
"what happened to this work" -- and affects listing, never id resolution.
"""

from __future__ import annotations

import json

from questkit.quest import Quest

# --- quest archive / unarchive --------------------------------------------------


def test_archive_sets_the_field_true(quest_log, run):
    result = run("new", "A quest", "--status", "todo")
    quest_id = result.lines[-1].split()[0].split("/")[-1].split("--")[0]

    result = run("archive", quest_id)

    assert result.code == 0
    path = next(quest_log.glob(f"{quest_id}--*.md"))
    assert Quest.load(path).get("archived") is True


def test_unarchive_clears_it(quest_log, run):
    result = run("new", "A quest", "--status", "todo")
    quest_id = result.lines[-1].split()[0].split("/")[-1].split("--")[0]
    run("archive", quest_id)

    result = run("unarchive", quest_id)

    assert result.code == 0
    path = next(quest_log.glob(f"{quest_id}--*.md"))
    assert not Quest.load(path).get("archived")


def test_archive_does_not_change_status_or_status_changed(isolated, make_log, write_quest, run):
    from datetime import date

    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", status="todo", status_changed=date(2026, 1, 1))

    run("archive", "QST-aaaaa", "--in", str(log))

    quest = Quest.load(next(log.glob("QST-*.md")))
    assert quest.get("status") == "todo"
    assert quest.get("status_changed") == date(2026, 1, 1)


def test_archive_restricts_the_search_to_the_named_log(isolated, make_log, write_quest, run):
    alpha = make_log(isolated, "alpha")
    beta = make_log(isolated, "beta")
    write_quest(beta, "QST-bbbbb", status="todo")

    result = run("archive", "QST-bbbbb", "--in", str(alpha))

    assert result.code == 1


# --- quest archive-log / unarchive-log -----------------------------------------


def test_archive_log_archives_every_non_archived_quest(isolated, make_log, write_quest, run):
    log = make_log(isolated, project="dead")
    write_quest(log, "QST-aaaaa", slug="a", status="todo")
    write_quest(log, "QST-bbbbb", slug="b", status="done")

    result = run("archive-log", str(log))

    assert result.code == 0
    for path in log.glob("QST-*.md"):
        assert Quest.load(path).get("archived") is True


def test_archive_log_is_idempotent(isolated, make_log, write_quest, run):
    log = make_log(isolated, project="dead")
    write_quest(log, "QST-aaaaa", status="todo", archived=True)
    path = next(log.glob("QST-*.md"))
    before = path.read_text()

    run("archive-log", str(log))

    assert path.read_text() == before


def test_archive_log_writes_no_config(isolated, make_log, write_quest, run):
    log = make_log(isolated, project="dead")
    write_quest(log, "QST-aaaaa", status="todo")
    config_before = (log / ".questkit.yaml").read_text()

    run("archive-log", str(log))

    assert (log / ".questkit.yaml").read_text() == config_before


def test_unarchive_log_clears_every_quest(isolated, make_log, write_quest, run):
    log = make_log(isolated, project="revived")
    write_quest(log, "QST-aaaaa", slug="a", status="todo", archived=True)
    write_quest(log, "QST-bbbbb", slug="b", status="done", archived=True)

    result = run("unarchive-log", str(log))

    assert result.code == 0
    for path in log.glob("QST-*.md"):
        assert not Quest.load(path).get("archived")


def test_new_quest_in_a_fully_archived_log_succeeds_and_the_log_is_no_longer_fully_archived(
    isolated, make_log, run
):
    log = make_log(isolated, project="dead")
    run("new", "First quest", "--status", "todo", "--in", str(log))
    run("archive-log", str(log))

    result = run("new", "Second quest", "--status", "todo", "--in", str(log))

    assert result.code == 0
    statuses = [Quest.load(p).get("archived") for p in log.glob("QST-*.md")]
    assert not all(statuses)


# --- --archived query axis -------------------------------------------------------


def test_default_list_excludes_archived(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", slug="a", status="todo")
    write_quest(log, "QST-bbbbb", slug="b", status="todo", archived=True)

    result = run("list", "--in", str(log))

    assert "QST-aaaaa" in result.out
    assert "QST-bbbbb" not in result.out


def test_archived_include_shows_both(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", slug="a", status="todo")
    write_quest(log, "QST-bbbbb", slug="b", status="todo", archived=True)

    result = run("list", "--in", str(log), "--archived", "include", "--where", "status:exists")

    assert "QST-aaaaa" in result.out
    assert "QST-bbbbb" in result.out


def test_archived_only_shows_just_the_archived_ones(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", slug="a", status="todo")
    write_quest(log, "QST-bbbbb", slug="b", status="todo", archived=True)

    result = run("list", "--in", str(log), "--archived", "only", "--where", "status:exists")

    assert "QST-bbbbb" in result.out
    assert "QST-aaaaa" not in result.out


def test_where_archived_and_select_archived_work_once_in_scope(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", slug="a", status="todo", archived=True)

    result = run(
        "list", "--in", str(log), "--archived", "include",
        "--where", "archived=true", "--select", "id,archived", "--format", "json",
    )

    rows = json.loads(result.out)
    assert rows == [{"id": "QST-aaaaa", "archived": True}]


def test_stale_and_next_and_blocked_exclude_archived_by_default(isolated, make_log, write_quest, run):
    from datetime import date, timedelta

    log = make_log(isolated)
    write_quest(
        log, "QST-aaaaa", status="todo",
        created=date.today() - timedelta(days=40), archived=True,
    )

    result = run("stale", "--in", str(log))

    assert "QST-aaaaa" not in result.out


def test_a_fully_archived_log_returns_nothing_from_stale_under_a_sweep(
    isolated, make_log, write_quest, run, monkeypatch
):
    from datetime import date, timedelta

    log = make_log(isolated, "dead", project="dead")
    write_quest(log, "QST-aaaaa", status="todo", created=date.today() - timedelta(days=40), archived=True)
    monkeypatch.setenv("QST_ROOT", str(isolated))

    result = run("stale", "-A")

    assert "QST-aaaaa" not in result.out


# --- id resolution and computed fields still honor an archived quest -----------------


def test_show_still_resolves_an_archived_id_with_a_note(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", status="todo", archived=True)

    result = run("show", "QST-aaaaa", "--in", str(log))

    assert result.code == 0
    assert "QST-aaaaa" in result.out
    assert "archived" in result.err.lower()


def test_a_blocked_by_reference_into_an_archived_quest_still_resolves(
    isolated, make_log, write_quest, run
):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", slug="a", status="done", archived=True)
    write_quest(log, "QST-bbbbb", slug="b", status="todo", blocked_by=["QST-aaaaa"])

    result = run("validate", "--in", str(log))

    assert result.code == 0


def test_set_on_an_archived_quest_succeeds_with_a_warning(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", status="todo", archived=True)

    result = run("set", "QST-aaaaa", "priority=high", "--in", str(log))

    assert result.code == 0
    assert "archived" in result.err.lower()
    quest = Quest.load(next(log.glob("QST-*.md")))
    assert quest.get("priority") == "high"
