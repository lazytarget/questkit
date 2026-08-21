"""Tests for schema defaults, `{{ }}` macros, typed custom fields, and --fill-defaults.

These ship together because they are unshippable apart: the moment any log
declares `required: true`, `quest validate` fails every quest that predates it
and the pre-commit hook blocks every commit -- unless `--fill-defaults` lands
in the same release.
"""

from __future__ import annotations

import pytest

from questkit import schema
from questkit.config import QuestLogConfig
from questkit.quest import Quest


def _id_of(result) -> str:
    return result.out.strip().split("/")[-1].split("--")[0]


# --- defaults in one place --------------------------------------------------------


def test_a_field_spec_default_is_applied_at_creation(isolated, make_log, run):
    log = make_log(isolated, schema={"fields": {"component": {"default": "core"}}})

    result = run("new", "A quest", "--status", "todo", "--in", str(log))

    assert Quest.load(next(log.glob("QST-*.md"))).get("component") == "core"
    assert result.code == 0


def test_top_level_defaults_are_sugar_for_the_same_map(isolated, make_log, run):
    log = make_log(isolated, defaults={"priority": "high"})

    run("new", "A quest", "--status", "todo", "--in", str(log))

    assert Quest.load(next(log.glob("QST-*.md"))).get("priority") == "high"


def test_a_field_spec_default_beats_a_top_level_default(isolated, make_log, run):
    """Documented precedence: --flag > fields.<n>.default > defaults.<n> > built-in."""
    log = make_log(
        isolated,
        defaults={"priority": "low"},
        schema={"fields": {"priority": {"default": "high"}}},
    )

    run("new", "A quest", "--status", "todo", "--in", str(log))

    assert Quest.load(next(log.glob("QST-*.md"))).get("priority") == "high"


def test_an_explicit_flag_beats_every_default(isolated, make_log, run):
    log = make_log(
        isolated,
        defaults={"priority": "low"},
        schema={"fields": {"priority": {"default": "high"}}},
    )

    run("new", "A quest", "--status", "todo", "--priority", "critical", "--in", str(log))

    assert Quest.load(next(log.glob("QST-*.md"))).get("priority") == "critical"


def test_a_custom_field_without_a_default_is_still_flagged_as_uninitialized(
    isolated, make_log, run
):
    log = make_log(isolated, schema={"fields": {"component": {"type": "string"}}})

    result = run("new", "A quest", "--status", "todo", "--in", str(log))

    assert "component" in result.err


# --- macros -----------------------------------------------------------------------


def test_project_macro_expands_at_creation(isolated, make_log, run):
    log = make_log(isolated, "alpha", project="alpha", schema={"fields": {"note": {"default": "for {{ project }}"}}})

    run("new", "A quest", "--status", "todo", "--in", str(log))

    assert Quest.load(next(log.glob("QST-*.md"))).get("note") == "for alpha"


def test_today_macro_expands_at_creation(isolated, make_log, run, monkeypatch):
    monkeypatch.setattr("questkit.macros.today", lambda: "2026-08-21")
    log = make_log(isolated, schema={"fields": {"reviewed": {"default": "{{ today }}"}}})

    run("new", "A quest", "--status", "todo", "--in", str(log))

    assert str(Quest.load(next(log.glob("QST-*.md"))).get("reviewed")) == "2026-08-21"


def test_id_and_slug_macros_expand_after_id_generation(isolated, make_log, run):
    """One evaluation point: after id generation, before first save."""
    log = make_log(isolated, schema={"fields": {"ref": {"default": "{{ id }}/{{ slug }}"}}})

    run("new", "A quest", "--status", "todo", "--in", str(log))

    path = next(log.glob("QST-*.md"))
    quest = Quest.load(path)
    assert quest.get("ref") == f"{quest.get('id')}/a-quest"


def test_env_macro_reads_the_environment(isolated, make_log, run, monkeypatch):
    monkeypatch.setenv("QUESTKIT_TEST_USER", "peter")
    log = make_log(isolated, schema={"fields": {"owner": {"default": "{{ env.QUESTKIT_TEST_USER }}"}}})

    run("new", "A quest", "--status", "todo", "--in", str(log))

    assert Quest.load(next(log.glob("QST-*.md"))).get("owner") == "peter"


def test_title_and_log_macros_expand(isolated, make_log, run):
    log = make_log(isolated, "alpha", schema={"fields": {"note": {"default": "{{ title }} in {{ log }}"}}})

    run("new", "Some title", "--status", "todo", "--in", str(log))

    assert Quest.load(next(log.glob("QST-*.md"))).get("note") == "Some title in quests"


def test_an_unknown_macro_is_an_error_not_an_empty_string(isolated, make_log, run):
    """A default silently expanding to nothing writes a blank field into every
    quest the log ever captures, and is only ever found by grep months later."""
    log = make_log(isolated, schema={"fields": {"note": {"default": "{{ projekt }}"}}})

    result = run("new", "A quest", "--status", "todo", "--in", str(log))

    assert result.code == 1
    assert "projekt" in result.err


def test_no_control_flow_is_supported():
    """`{{ }}` is a strict subset of Jinja, deliberately -- no `{% if %}`."""
    assert schema is not None  # anchor
    from questkit import macros

    assert macros.expand("{% if x %}y{% endif %}", {}) == "{% if x %}y{% endif %}"


# --- typed custom fields ----------------------------------------------------------


def test_an_enum_field_rejects_an_out_of_vocabulary_value(isolated, make_log, write_quest, run):
    log = make_log(
        isolated,
        schema={"fields": {"component": {"type": "enum", "values": ["api", "ui"]}}},
    )
    write_quest(log, "QST-aaaaa", component="nonsense")

    result = run("validate", "--in", str(log))

    assert result.code == 1
    assert "component" in result.out


def test_an_enum_field_accepts_a_declared_value(isolated, make_log, write_quest, run):
    log = make_log(
        isolated,
        schema={"fields": {"component": {"type": "enum", "values": ["api", "ui"]}}},
    )
    write_quest(log, "QST-aaaaa", component="api")

    assert run("validate", "--in", str(log)).code == 0


def test_an_enum_field_without_values_is_a_schema_error(isolated, make_log):
    log = make_log(isolated, schema={"fields": {"component": {"type": "enum"}}})

    with pytest.raises(schema.SchemaConfigError):
        QuestLogConfig.load(log)


def test_an_enum_fields_values_are_ordered_for_sorting(isolated, make_log):
    log = make_log(
        isolated,
        schema={"fields": {"component": {"type": "enum", "values": ["ui", "api", "db"]}}},
    )

    config = QuestLogConfig.load(log).schema
    assert config.fields["component"].values == ("ui", "api", "db")
    assert config.rank_of("component", "ui") < config.rank_of("component", "db")


def test_schema_introspection_shows_a_fields_values(isolated, make_log, run):
    log = make_log(
        isolated,
        schema={"fields": {"component": {"type": "enum", "values": ["api", "ui"]}}},
    )

    result = run("schema", "quest", "component", "--in", str(log))

    assert "api" in result.out


# --- required + static default is validation theater ------------------------------


def test_required_with_a_static_default_warns(isolated, make_log, run):
    log = make_log(
        isolated,
        schema={"fields": {"component": {"required": True, "default": "core"}}},
    )

    result = run("validate", "--in", str(log))

    assert "validation theater" in result.err or "static default" in result.err


def test_required_with_a_macro_default_does_not_warn(isolated, make_log, run):
    """A computed default that genuinely varies carries real information."""
    log = make_log(
        isolated,
        schema={"fields": {"owner": {"required": True, "default": "{{ env.USER }}"}}},
    )

    result = run("validate", "--in", str(log))

    assert "static default" not in result.err


# --- --fill-defaults --------------------------------------------------------------


def test_fill_defaults_backfills_a_declared_default(isolated, make_log, write_quest, run, absent):
    log = make_log(isolated, schema={"fields": {"component": {"default": "core"}}})
    path = write_quest(log, "QST-aaaaa", component=absent)

    result = run("format", "--fill-defaults", str(log))

    assert result.code == 0
    assert Quest.load(path).get("component") == "core"


def test_fill_defaults_is_idempotent(isolated, make_log, write_quest, run, absent):
    log = make_log(isolated, schema={"fields": {"component": {"default": "core"}}})
    write_quest(log, "QST-aaaaa", component=absent)

    run("format", "--fill-defaults", str(log))
    second = run("format", "--fill-defaults", str(log))

    assert "0 reformatted" in second.out


def test_fill_defaults_never_overwrites_an_existing_value(isolated, make_log, write_quest, run):
    log = make_log(isolated, schema={"fields": {"component": {"default": "core"}}})
    path = write_quest(log, "QST-aaaaa", component="ui")

    run("format", "--fill-defaults", str(log))

    assert Quest.load(path).get("component") == "ui"


def test_fill_defaults_expands_macros(isolated, make_log, write_quest, run, absent, monkeypatch):
    monkeypatch.setattr("questkit.macros.today", lambda: "2026-08-21")
    log = make_log(isolated, schema={"fields": {"reviewed": {"default": "{{ today }}"}}})
    path = write_quest(log, "QST-aaaaa", reviewed=absent)

    run("format", "--fill-defaults", str(log))

    assert str(Quest.load(path).get("reviewed")) == "2026-08-21"


def test_format_without_fill_defaults_backfills_nothing(
    isolated, make_log, write_quest, run, absent
):
    log = make_log(isolated, schema={"fields": {"component": {"default": "core"}}})
    path = write_quest(log, "QST-aaaaa", component=absent)

    run("format", str(log))

    assert "component" not in Quest.load(path).frontmatter


def test_fill_defaults_does_not_bump_modified(isolated, make_log, write_quest, run, absent):
    """Backfilling a field nobody asked about is not a content edit."""
    log = make_log(isolated, schema={"fields": {"component": {"default": "core"}}})
    path = write_quest(log, "QST-aaaaa", component=absent, modified="2020-01-01")

    run("format", "--fill-defaults", str(log))

    assert str(Quest.load(path).get("modified")) == "2020-01-01"


def test_fill_defaults_makes_a_newly_required_field_validate(
    isolated, make_log, write_quest, run, absent
):
    """The reason this ships in the same release as `required: true`."""
    log = make_log(
        isolated,
        schema={"fields": {"component": {"required": True, "default": "{{ project }}"}}},
    )
    write_quest(log, "QST-aaaaa", component=absent)
    assert run("validate", "--in", str(log)).code == 1

    run("format", "--fill-defaults", str(log))

    assert run("validate", "--in", str(log)).code == 0


# --- generic --set on quest new ---------------------------------------------------


def test_new_set_writes_a_custom_field(isolated, make_log, run):
    log = make_log(isolated, schema={"fields": {"component": {"type": "string"}}})

    result = run("new", "A quest", "--status", "todo", "--set", "component=api", "--in", str(log))

    assert result.code == 0
    assert Quest.load(next(log.glob("QST-*.md"))).get("component") == "api"


def test_new_set_is_repeatable(isolated, make_log, run):
    log = make_log(
        isolated, schema={"fields": {"component": {"type": "string"}, "sprint": {"type": "string"}}}
    )

    run(
        "new", "A quest", "--status", "todo",
        "--set", "component=api", "--set", "sprint=12", "--in", str(log),
    )

    quest = Quest.load(next(log.glob("QST-*.md")))
    assert quest.get("component") == "api"
    assert quest.get("sprint") == "12"


def test_new_set_beats_a_declared_default(isolated, make_log, run):
    log = make_log(isolated, schema={"fields": {"component": {"default": "core"}}})

    run("new", "A quest", "--status", "todo", "--set", "component=api", "--in", str(log))

    assert Quest.load(next(log.glob("QST-*.md"))).get("component") == "api"


def test_new_set_can_write_a_core_field(isolated, make_log, run):
    log = make_log(isolated)

    run("new", "A quest", "--status", "todo", "--set", "effort=m", "--in", str(log))

    assert Quest.load(next(log.glob("QST-*.md"))).get("effort") == "m"


def test_quest_set_rejects_a_set_flag_with_a_helpful_message(quest_log, run):
    """`set` keeps positional assignments; a --set there is a second grammar."""
    quest_id = _id_of(run("new", "A quest", "--status", "todo"))

    result = run("set", quest_id, "--set", "effort=m")

    assert result.code != 0


def test_new_stamps_the_logs_project(isolated, make_log, run):
    """Regression guard: `project` is identity, so a log declaring one stamps it.

    The defaults rewrite briefly dropped this -- `config.project` is not one of
    `config.defaults`, so routing everything through the defaults map lost it.
    """
    log = make_log(isolated, "alpha", project="alpha")

    run("new", "A quest", "--status", "todo", "--in", str(log))

    assert Quest.load(next(log.glob("QST-*.md"))).get("project") == "alpha"


def test_an_explicit_project_flag_beats_the_logs_project(isolated, make_log, run):
    log = make_log(isolated, "alpha", project="alpha")

    run("new", "A quest", "--status", "todo", "--project", "other", "--in", str(log))

    assert Quest.load(next(log.glob("QST-*.md"))).get("project") == "other"


def test_a_log_with_no_project_stamps_nothing(isolated, make_log, run):
    log = make_log(isolated, project=None)

    run("new", "A quest", "--status", "todo", "--in", str(log))

    assert "project" not in Quest.load(next(log.glob("QST-*.md"))).frontmatter
