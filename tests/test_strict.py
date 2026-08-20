"""Tests for `strict`: the write-path guard and its validate-time extension.

`strict` governs two things. On the CLI write path, `quest new --set` naming a
field the schema does not declare is a hard error under `strict: true` (the
default) and a warning under `strict: false` -- silent is never correct, since
the failure mode is a field that appears in no filter, fails no validation,
and is only ever found by grep months later. Under `strict: true`, the same
rule extends to `quest validate`: an undeclared field found *in a file* is a
validation error, with a short allowlist for the property names Obsidian's
Properties panel adds on its own.
"""

from __future__ import annotations

from questkit import schema
from questkit.config import QuestLogConfig
from questkit.quest import Quest

# --- strict defaults and inheritance -----------------------------------------------


def test_strict_defaults_to_true():
    assert schema.SchemaConfig.default().strict is True


def test_strict_can_be_declared_false(isolated, make_log):
    log = make_log(isolated, schema={"strict": False})

    assert QuestLogConfig.load(log).schema.strict is False


def test_strict_is_inherited_through_extends(isolated, make_log, write_schema):
    write_schema(isolated / "schemas", "lenient", {"strict": False})
    log = make_log(isolated, schema={"extends": "../schemas/lenient.yaml"})

    assert QuestLogConfig.load(log).schema.strict is False


def test_a_child_schema_can_override_the_parents_strict(isolated, make_log, write_schema):
    write_schema(isolated / "schemas", "lenient", {"strict": False})
    log = make_log(isolated, schema={"extends": "../schemas/lenient.yaml", "strict": True})

    assert QuestLogConfig.load(log).schema.strict is True


# --- the write path: quest new --set -----------------------------------------------


def test_new_set_of_an_undeclared_field_errors_under_strict(isolated, make_log, run):
    log = make_log(isolated)

    result = run("new", "A quest", "--status", "todo", "--set", "nonsense=x", "--in", str(log))

    assert result.code == 1
    assert "nonsense" in result.err


def test_the_strict_error_names_the_valid_fields(isolated, make_log, run):
    log = make_log(isolated, schema={"fields": {"component": {"type": "string"}}})

    result = run("new", "A quest", "--status", "todo", "--set", "nonsense=x", "--in", str(log))

    assert "component" in result.err
    assert "effort" in result.err  # a core field


def test_new_set_of_an_undeclared_field_warns_under_lenient(isolated, make_log, run):
    log = make_log(isolated, schema={"strict": False})

    result = run("new", "A quest", "--status", "todo", "--set", "nonsense=x", "--in", str(log))

    assert result.code == 0
    assert "nonsense" in result.err


def test_lenient_still_writes_the_field(isolated, make_log, run):
    log = make_log(isolated, schema={"strict": False})

    run("new", "A quest", "--status", "todo", "--set", "nonsense=x", "--in", str(log))

    assert Quest.load(next(log.glob("QST-*.md"))).get("nonsense") == "x"


def test_new_set_of_a_declared_custom_field_is_fine_under_strict(isolated, make_log, run):
    log = make_log(isolated, schema={"fields": {"component": {"type": "string"}}})

    result = run("new", "A quest", "--status", "todo", "--set", "component=api", "--in", str(log))

    assert result.code == 0


def test_shorthand_flags_are_never_subject_to_the_strict_check(isolated, make_log, run):
    """--status/--priority/etc. are always core fields, regardless of strict."""
    log = make_log(isolated)

    result = run("new", "A quest", "--status", "todo", "--priority", "high", "--in", str(log))

    assert result.code == 0
    assert result.err == ""


# --- the validate-time extension: undeclared fields in a file ---------------------


def test_an_undeclared_field_in_a_file_is_a_validation_error_under_strict(
    isolated, make_log, write_quest, run
):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", nonsense="x")

    result = run("validate", "--in", str(log))

    assert result.code == 1
    assert "nonsense" in result.out


def test_a_declared_custom_field_is_not_flagged(isolated, make_log, write_quest, run):
    log = make_log(isolated, schema={"fields": {"component": {"type": "string"}}})
    write_quest(log, "QST-aaaaa", component="api")

    assert run("validate", "--in", str(log)).code == 0


def test_a_core_field_is_never_flagged(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", owner="peter", due="2026-09-01")

    assert run("validate", "--in", str(log)).code == 0


def test_an_undeclared_field_is_not_flagged_under_lenient(isolated, make_log, write_quest, run):
    log = make_log(isolated, schema={"strict": False})
    write_quest(log, "QST-aaaaa", nonsense="x")

    assert run("validate", "--in", str(log)).code == 0


# --- Obsidian-reserved property names ----------------------------------------------


def test_obsidian_reserved_names_are_allowlisted(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", cssclasses="wide")

    assert run("validate", "--in", str(log)).code == 0


def test_every_obsidian_reserved_name_is_allowlisted(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    fields = dict.fromkeys(schema.OBSIDIAN_RESERVED_FIELDS, "x")
    write_quest(log, "QST-aaaaa", **fields)

    assert run("validate", "--in", str(log)).code == 0


def test_obsidian_reserved_names_are_listed_by_schema_introspection(quest_log, run):
    result = run("schema", "quest", "--format", "json")

    for name in schema.OBSIDIAN_RESERVED_FIELDS:
        assert name in result.out
