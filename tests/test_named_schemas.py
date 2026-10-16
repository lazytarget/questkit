"""Tests for named schema resolution and the `archived` core field.

Shared schemas live at `99-system/questkit/schemas/<name>.yaml` (the built-in
default directory), resolved via a search path along the log's ancestors, or
via `QST_SCHEMA_PATH`.
"""

from __future__ import annotations

import os

import pytest

from questkit import schema
from questkit.config import QuestLogConfig


def _schemas_dir(root):
    d = root / "99-system" / "questkit" / "schemas"
    d.mkdir(parents=True, exist_ok=True)
    return d


# --- resolution -------------------------------------------------------------------


def test_a_bare_name_resolves_from_the_shared_schema_dir(isolated, make_log, write_schema):
    write_schema(_schemas_dir(isolated), "development", {"types": ["task", "bug"]})
    log = make_log(isolated / "project", "alpha", schema={"extends": "development"})

    assert QuestLogConfig.load(log).schema.types == ("task", "bug")


def test_a_scalar_schema_key_is_shorthand_for_extends(isolated, make_log, write_schema):
    write_schema(_schemas_dir(isolated), "development", {"types": ["task", "bug"]})
    log = make_log(isolated / "project", "alpha")
    config_path = log / ".questkit.yaml"
    config_path.write_text(
        config_path.read_text().rstrip("\n") + "\nschema: development\n", encoding="utf-8"
    )

    assert QuestLogConfig.load(log).schema.types == ("task", "bug")


def test_a_path_like_extends_stays_path_relative(isolated, make_log, write_schema):
    """Anything with a separator or a .yaml suffix is a path, unchanged."""
    write_schema(isolated / "shared", "base", {"types": ["task"]})
    log = make_log(isolated, schema={"extends": "../shared/base.yaml"})

    assert QuestLogConfig.load(log).schema.types == ("task",)


def test_the_search_path_is_configurable_by_env(isolated, make_log, write_schema, monkeypatch):
    elsewhere = isolated / "elsewhere"
    write_schema(elsewhere, "development", {"types": ["chore"]})
    monkeypatch.setenv("QST_SCHEMA_PATH", str(elsewhere))
    log = make_log(isolated, schema={"extends": "development"})

    assert QuestLogConfig.load(log).schema.types == ("chore",)


def test_the_env_search_path_accepts_several_directories(
    isolated, make_log, write_schema, monkeypatch
):
    first = isolated / "first"
    second = isolated / "second"
    first.mkdir()
    write_schema(second, "chores", {"types": ["chore"]})
    monkeypatch.setenv("QST_SCHEMA_PATH", os.pathsep.join([str(first), str(second)]))
    log = make_log(isolated, schema={"extends": "chores"})

    assert QuestLogConfig.load(log).schema.types == ("chore",)


def test_the_env_search_path_wins_over_the_shared_dir(
    isolated, make_log, write_schema, monkeypatch
):
    write_schema(_schemas_dir(isolated), "development", {"types": ["task"]})
    override = isolated / "override"
    write_schema(override, "development", {"types": ["chore"]})
    monkeypatch.setenv("QST_SCHEMA_PATH", str(override))
    log = make_log(isolated, schema={"extends": "development"})

    assert QuestLogConfig.load(log).schema.types == ("chore",)


def test_an_unresolvable_name_errors_naming_the_places_it_looked(isolated, make_log):
    log = make_log(isolated, schema={"extends": "nonexistent"})

    with pytest.raises(schema.SchemaExtendsError) as exc:
        QuestLogConfig.load(log)

    assert "nonexistent" in str(exc.value)
    assert "99-system" in str(exc.value) or "searched" in str(exc.value)


def test_a_named_schema_can_itself_extend_another(isolated, make_log, write_schema):
    schemas = _schemas_dir(isolated)
    write_schema(schemas, "base", {"types": ["task"]})
    write_schema(schemas, "development", {"extends": "base", "tiers": ["spark"]})
    log = make_log(isolated / "project", "alpha", schema={"extends": "development"})

    config = QuestLogConfig.load(log).schema
    assert config.types == ("task",)
    assert config.tiers == ("spark",)


def test_a_log_key_overrides_the_named_schema(isolated, make_log, write_schema):
    write_schema(_schemas_dir(isolated), "development", {"types": ["task", "bug"]})
    log = make_log(
        isolated / "project", "alpha", schema={"extends": "development", "types": ["chore"]}
    )

    assert QuestLogConfig.load(log).schema.types == ("chore",)


def test_the_shared_dir_is_found_by_walking_up(isolated, make_log, write_schema):
    """A log nested several levels down still finds 99-system/questkit/schemas."""
    write_schema(_schemas_dir(isolated), "development", {"types": ["task"]})
    log = make_log(isolated / "projects" / "team" / "thing", "alpha",
                   schema={"extends": "development"})

    assert QuestLogConfig.load(log).schema.types == ("task",)


# --- the archived core field -------------------------------------------------------


def test_archived_is_a_known_core_field():
    assert "archived" in schema.CORE_FIELDS


def test_archived_is_described_by_schema_introspection(quest_log, run):
    result = run("schema", "quest", "archived")

    assert result.code == 0
    assert "bool" in result.out


def test_archived_sorts_into_the_alphabetical_tail(isolated, make_log, write_quest, run):
    """Rarely set, never scanned -- so it does not belong in the explicit head."""
    log = make_log(isolated)
    path = write_quest(log, "QST-aaaaa", archived=True)

    run("format", str(log))

    from questkit.quest import Quest

    keys = list(Quest.load(path).frontmatter.keys())
    assert "archived" not in schema.SchemaConfig.default().field_order
    assert keys.index("archived") > keys.index("modified")


def test_archived_true_validates_clean(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", archived=True)

    assert run("validate", "--in", str(log)).code == 0


def test_a_schema_may_not_redeclare_archived_as_a_custom_field(isolated, make_log):
    log = make_log(isolated, schema={"fields": {"archived": {"type": "string"}}})

    with pytest.raises(schema.SchemaConfigError):
        QuestLogConfig.load(log)
