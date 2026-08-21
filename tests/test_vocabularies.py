"""Tests for ordered vocabularies, terminal statuses, and the status enum.

Vocabularies were `frozenset`s, so `list_cmd._apply_sort` fell back to a
lexicographic string sort. Measured before this change:

    --sort priority:asc  ->  critical, deferred, high, low, medium
    --sort effort:asc    ->  l, m, s, xl, xs
    --sort tier:asc      ->  blueprint, brief, spark

So `views.next`, specified as `sort: priority:asc,effort:asc`, would have
ranked a `deferred` quest second. A second, independent bug compounded it:
`sort_expr.partition(":")` on `"priority:asc,effort:asc"` yields
direction=`"asc,effort:asc"`, so every key after the first was silently
dropped and `desc` never matched. Multi-key sort did not exist, and `next`
needs it. Both are fixed here.
"""

from __future__ import annotations

import pytest

from questkit import schema
from questkit.config import QuestLogConfig

# --- vocabularies are ordered sequences -------------------------------------------


def test_default_vocabularies_keep_their_declared_order():
    config = schema.SchemaConfig.default()

    assert config.statuses == ("draft", "todo", "in-progress", "parked", "done", "scrapped")
    assert config.priorities == ("critical", "high", "medium", "low", "deferred")
    assert config.efforts == ("xs", "s", "m", "l", "xl")
    assert config.tiers == ("spark", "brief", "blueprint")


def test_a_declared_vocabulary_keeps_the_order_it_was_written_in(isolated, make_log):
    log = make_log(
        isolated,
        schema={"statuses": ["icebox", "doing", "shipped"], "terminal_statuses": ["shipped"]},
    )

    assert QuestLogConfig.load(log).schema.statuses == ("icebox", "doing", "shipped")


def test_membership_still_works_on_an_ordered_vocabulary():
    config = schema.SchemaConfig.default()

    assert "todo" in config.statuses
    assert "completed" not in config.statuses


def test_rank_of_returns_declaration_order():
    config = schema.SchemaConfig.default()

    assert config.rank_of("priority", "critical") < config.rank_of("priority", "deferred")
    assert config.rank_of("effort", "xs") < config.rank_of("effort", "xl")


def test_rank_of_sorts_an_unknown_value_last():
    """An out-of-vocabulary value must not silently rank first."""
    config = schema.SchemaConfig.default()

    assert config.rank_of("priority", "nonsense") > config.rank_of("priority", "deferred")


def test_rank_of_an_unranked_field_is_none():
    """A free-text field has no declared order, so sorting falls back to string."""
    assert schema.SchemaConfig.default().rank_of("title", "anything") is None


# --- the status enum ---------------------------------------------------------------


def test_completed_is_gone_and_done_replaces_it():
    statuses = schema.SchemaConfig.default().statuses

    assert "done" in statuses
    assert "completed" not in statuses


def test_blocked_is_gone_from_the_status_enum():
    """A status value and a computed field cannot share a name in a query language.

    With `blocked` computed, `--where blocked=true` and
    `--where status=blocked` would be two different questions one word apart,
    and a quest could satisfy either without the other.
    """
    assert "blocked" not in schema.SchemaConfig.default().statuses


def test_parked_stays():
    """Removal was about the name collision, not about disuse -- both had 0 uses."""
    assert "parked" in schema.SchemaConfig.default().statuses


def test_milestone_leaves_the_core_types_enum():
    assert "milestone" not in schema.SchemaConfig.default().types


# --- terminal statuses -------------------------------------------------------------


def test_terminal_statuses_default_to_the_tail_of_statuses():
    config = schema.SchemaConfig.default()

    assert config.terminal_statuses == ("done", "scrapped")
    assert config.statuses[-2:] == config.terminal_statuses


def test_terminal_statuses_can_be_declared(isolated, make_log):
    log = make_log(
        isolated,
        schema={
            "statuses": ["draft", "todo", "in-review", "shipped", "cancelled"],
            "terminal_statuses": ["shipped", "cancelled"],
        },
    )

    assert QuestLogConfig.load(log).schema.terminal_statuses == ("shipped", "cancelled")


def test_terminal_statuses_intersect_the_declared_statuses(isolated, make_log):
    """A log that keeps one default terminal status needs no declaration."""
    log = make_log(isolated, schema={"statuses": ["icebox", "doing", "done"]})

    assert QuestLogConfig.load(log).schema.terminal_statuses == ("done",)


def test_overriding_statuses_with_no_surviving_default_and_no_declaration_is_a_hard_error(
    isolated, make_log
):
    """Degrading would deliver a wrong answer confidently -- an OPEN column
    silently equal to total, a `blocked` field that is always false."""
    log = make_log(isolated, schema={"statuses": ["icebox", "doing", "shipped"]})

    with pytest.raises(schema.SchemaConfigError) as exc:
        QuestLogConfig.load(log)

    assert "terminal_statuses" in str(exc.value)


def test_a_declared_terminal_status_must_be_a_declared_status(isolated, make_log):
    log = make_log(
        isolated,
        schema={"statuses": ["icebox", "doing", "shipped"], "terminal_statuses": ["nope"]},
    )

    with pytest.raises(schema.SchemaConfigError):
        QuestLogConfig.load(log)


def test_terminal_statuses_are_ordered_so_quest_done_has_a_first_entry(isolated, make_log):
    log = make_log(
        isolated,
        schema={
            "statuses": ["todo", "cancelled", "shipped"],
            "terminal_statuses": ["shipped", "cancelled"],
        },
    )

    assert QuestLogConfig.load(log).schema.terminal_statuses[0] == "shipped"


# --- the computed-field collision rule --------------------------------------------


@pytest.mark.parametrize("reserved", ["blocked", "blocks", "idle", "age", "archived"])
def test_declaring_an_enum_value_named_after_a_computed_field_is_an_error(
    isolated, make_log, reserved
):
    """This is what makes `blocked` leaving the enum permanent rather than a
    tidy-up someone reverses in six months."""
    log = make_log(isolated, schema={"statuses": ["draft", "todo", reserved, "done"]})

    with pytest.raises(schema.SchemaConfigError) as exc:
        QuestLogConfig.load(log)

    assert reserved in str(exc.value)
    assert "computed" in str(exc.value)


def test_the_collision_rule_covers_every_vocabulary(isolated, make_log):
    log = make_log(isolated, schema={"types": ["task", "idle"]})

    with pytest.raises(schema.SchemaConfigError):
        QuestLogConfig.load(log)


def test_a_custom_field_may_not_be_named_after_a_computed_field(isolated, make_log):
    log = make_log(isolated, schema={"fields": {"blocked": {"type": "string"}}})

    with pytest.raises(schema.SchemaConfigError):
        QuestLogConfig.load(log)


def test_an_unreserved_value_is_fine(isolated, make_log):
    log = make_log(isolated, schema={"statuses": ["draft", "waiting", "done"]})

    assert "waiting" in QuestLogConfig.load(log).schema.statuses
