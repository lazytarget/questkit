"""Tests for the shared fixtures in conftest.py.

The fixtures are test infrastructure, so a bug in one shows up as a confusing
failure somewhere else entirely -- a `write_quest` that produced invalid
frontmatter would look like a validation bug in every test that used it. These
assertions keep that diagnosis local.
"""

from __future__ import annotations

from questkit import schema
from questkit.config import QuestLogConfig
from questkit.quest import Quest


def test_write_quest_produces_a_file_that_validates_clean(isolated, make_log, write_quest):
    log = make_log(isolated)

    path = write_quest(log, "QST-aaaaa")

    assert schema.validate_quest(Quest.load(path)) == []


def test_write_quest_overrides_win_over_defaults(isolated, make_log, write_quest):
    log = make_log(isolated)

    path = write_quest(log, "QST-aaaaa", status="in-progress", priority="critical")

    frontmatter = Quest.load(path).frontmatter
    assert frontmatter["status"] == "in-progress"
    assert frontmatter["priority"] == "critical"


def test_write_quest_absent_omits_the_key_entirely(isolated, make_log, write_quest, absent):
    log = make_log(isolated)

    path = write_quest(log, "QST-aaaaa", description=absent)

    assert "description" not in Quest.load(path).frontmatter


def test_write_quest_slug_lands_in_the_filename(isolated, make_log, write_quest):
    log = make_log(isolated)

    path = write_quest(log, "QST-aaaaa", slug="a-real-slug")

    assert path.name == "QST-aaaaa--a-real-slug.md"


def test_write_quest_body_is_written_verbatim(isolated, make_log, write_quest):
    log = make_log(isolated)

    path = write_quest(log, "QST-aaaaa", body="## Spec\n\nDo the thing.")

    assert Quest.load(path).body.strip() == "## Spec\n\nDo the thing."


def test_make_log_writes_a_loadable_config(isolated, make_log):
    log = make_log(isolated, "alpha", git="auto")

    config = QuestLogConfig.load(log)
    assert config.project == "alpha"
    assert config.git == "auto"
    assert config.pattern == "QST-*.md"


def test_make_log_passes_a_schema_block_through(isolated, make_log):
    log = make_log(isolated, schema={"statuses": ["draft", "todo", "done"]})

    assert QuestLogConfig.load(log).schema.statuses == ("draft", "todo", "done")


def test_write_schema_supports_dict_and_text_bodies(isolated, write_schema):
    from ruamel.yaml import YAML

    as_dict = write_schema(isolated, "one", {"statuses": ["a", "b"]})
    as_text = write_schema(isolated, "two", "statuses: [a, b]\n")

    loader = YAML()
    assert loader.load(as_dict.read_text()) == loader.load(as_text.read_text())


def test_run_captures_streams_and_exit_code(quest_log, run):
    result = run("list")

    assert result.code == 0
    assert "no matching quests" in result.out


def test_run_reports_a_nonzero_exit_without_raising(isolated, run):
    result = run("show", "QST-nope")

    assert result.code == 1


def test_multi_log_builds_three_logs_under_one_root(multi_log):
    assert sorted(multi_log) == ["alpha", "beta", "gamma", "root"]
    assert len(list(multi_log["alpha"].glob("QST-*.md"))) == 2
    assert len(list(multi_log["gamma"].glob("QST-*.md"))) == 2


def test_multi_log_quests_all_validate_clean(multi_log):
    for name in ("alpha", "beta", "gamma"):
        for path in multi_log[name].glob("QST-*.md"):
            assert schema.validate_quest(Quest.load(path)) == [], path
