"""Tests for QST-onxad's `language` field on the `household` schema.

No core field: `language` is exactly the kind of vocabulary that varies per
log, so it is declared where it is wanted (99-system/questkit/schemas/
household.yaml) rather than shipped as an opinion every log carries. This
mirrors test_milestone_view.py's approach for the `development` schema --
one characterization test against the real, Syncthing-tracked schema file,
plus synthetic-schema tests for the general (schema-declared field with a
default) behavior so the suite doesn't depend on the real file's exact shape.
"""

from __future__ import annotations

import os
from pathlib import Path

from questkit.config import QuestLogConfig


def test_the_household_schema_declares_language_with_a_swedish_default():
    """Characterization test for 99-system/questkit/schemas/household.yaml."""
    quests_dir = Path(__file__).resolve().parents[1] / "quests"  # schema: development, not household
    schemas_dir = None
    for ancestor in quests_dir.parents:
        candidate = ancestor / "99-system" / "questkit" / "schemas"
        if candidate.is_dir():
            schemas_dir = candidate
            break
    if schemas_dir is None or not (schemas_dir / "household.yaml").is_file():
        import pytest

        pytest.skip("real household.yaml not present in this environment")

    from questkit import schema as schema_module

    old = os.environ.get("QST_SCHEMA_PATH")
    os.environ["QST_SCHEMA_PATH"] = str(schemas_dir)
    try:
        config = schema_module.SchemaConfig.load(quests_dir, {"extends": "household"})
    finally:
        if old is None:
            os.environ.pop("QST_SCHEMA_PATH", None)
        else:
            os.environ["QST_SCHEMA_PATH"] = old

    spec = config.fields["language"]
    assert spec.type == "enum"
    assert spec.values == ("sv", "en")
    assert spec.default == "sv"


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
