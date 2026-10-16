"""Tests for QST-onxad's `language` hint as a schema-declared field.

No core field: `language` is exactly the kind of vocabulary that varies per
log, so a log declares it where it is wanted (an enum field with a default)
rather than questkit shipping an opinion every log carries.
"""

from __future__ import annotations

from pathlib import Path

from questkit.config import QuestLogConfig


def _language_schema():
    return {"fields": {"language": {"type": "enum", "values": ["sv", "en"], "default": "sv"}}}


def test_development_does_not_declare_language():
    quests_dir = Path(__file__).resolve().parents[1] / "quests"
    config = QuestLogConfig.load(quests_dir)

    assert "language" not in config.schema.fields


def test_a_quest_created_in_a_log_using_the_schema_is_stamped_automatically(
    isolated, make_log, run
):
    log = make_log(isolated, project="family", schema=_language_schema())

    result = run("new", "Buy milk", "--in", str(log), "--status", "waiting")

    assert result.code == 0
    path = next(log.glob("QST-*.md"))
    assert "language: sv" in path.read_text()


def test_quest_brief_surfaces_language_in_the_metadata_line(isolated, make_log, write_quest, run):
    log = make_log(isolated, project="family", schema=_language_schema())
    write_quest(log, "QST-aaaaa", status="waiting", language="sv", description="Buy milk")

    result = run("brief", "QST-aaaaa", "--in", str(log))

    assert "language=sv" in result.out


def test_quest_schema_quest_language_describes_it(isolated, make_log, run):
    log = make_log(isolated, project="family", schema=_language_schema())

    result = run("schema", "quest", "language", "--in", str(log))

    assert result.code == 0
    assert "enum" in result.out
    assert "sv" in result.out
    assert "en" in result.out
