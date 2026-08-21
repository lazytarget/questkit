"""Tests for the `readiness:` engine.

Readiness is a *grooming judgment*, not a file-format contract, and that
distinction is the whole reason it exists as its own thing: the old AFK rule
was a category error, turning grooming judgment into a commit-blocking
contract. `quest validate` enforces none of this and cannot fail on it --
`quest brief` (a later quest) is the intended consumer of the verdict.

Three constructs, deliberately just three: `where:` reuses the `--where`
grammar verbatim (needs `!=`, which QST-b9lqo's split put here already);
`when:` guards a rule conditionally; `sections:`/`checklist:` are the only
body-aware predicates.
"""

from __future__ import annotations

from questkit import schema
from questkit.config import QuestLogConfig
from questkit.quest import Quest


def _rule(**kwargs):
    return schema.ReadinessRule(**kwargs)


# --- the default core rules ---------------------------------------------------


def test_the_core_ships_all_four_universal_readiness_rules():
    assert len(schema.SchemaConfig.default().readiness) == 4


def test_a_schema_can_override_the_readiness_list_to_fewer(isolated, make_log):
    log = make_log(isolated, schema={"readiness": [{"require": {"where": "description:exists"}, "message": "no description"}]})

    assert len(QuestLogConfig.load(log).schema.readiness) == 1


def test_a_readiness_rule_missing_require_or_message_is_a_schema_error(isolated, make_log):
    import pytest

    log = make_log(isolated, schema={"readiness": [{"message": "no require"}]})

    with pytest.raises(schema.SchemaConfigError):
        QuestLogConfig.load(log)


# --- where: ---------------------------------------------------------------------


def test_where_require_is_satisfied_when_the_expression_matches(isolated, make_log, write_quest):
    log = make_log(isolated, schema={"readiness": [
        {"require": {"where": "description:exists"}, "message": "no description"},
    ]})
    path = write_quest(log, "QST-aaaaa", description="Something real")

    failures = schema.evaluate_readiness(Quest.load(path), QuestLogConfig.load(log).schema)

    assert failures == []


def test_where_require_fails_and_reports_the_rules_own_message(isolated, make_log, write_quest, absent):
    log = make_log(isolated, schema={"readiness": [
        {"require": {"where": "description:exists"}, "message": "no description here"},
    ]})
    path = write_quest(log, "QST-aaaaa", description=absent)

    failures = schema.evaluate_readiness(Quest.load(path), QuestLogConfig.load(log).schema)

    assert failures == ["no description here"]


def test_where_uses_not_equal(isolated, make_log, write_quest):
    log = make_log(isolated, schema={"readiness": [
        {"require": {"where": "status!=draft"}, "message": "still a draft"},
    ]})
    draft = write_quest(log, "QST-aaaaa", status="draft")
    todo = write_quest(log, "QST-bbbbb", status="todo")

    assert schema.evaluate_readiness(Quest.load(draft), QuestLogConfig.load(log).schema) == ["still a draft"]
    assert schema.evaluate_readiness(Quest.load(todo), QuestLogConfig.load(log).schema) == []


# --- sections: (any-of) ----------------------------------------------------------


def test_sections_is_satisfied_by_any_one_of_the_listed_headings(isolated, make_log, write_quest):
    log = make_log(isolated, schema={"readiness": [
        {"require": {"sections": ["## Spec", "## Design"]}, "message": "no spec or design"},
    ]})
    path = write_quest(log, "QST-aaaaa", body="## Design\n\nSome design.\n")

    assert schema.evaluate_readiness(Quest.load(path), QuestLogConfig.load(log).schema) == []


def test_sections_fails_when_none_are_present(isolated, make_log, write_quest):
    log = make_log(isolated, schema={"readiness": [
        {"require": {"sections": ["## Spec", "## Design"]}, "message": "no spec or design"},
    ]})
    path = write_quest(log, "QST-aaaaa", body="## Description\n\nJust a description.\n")

    assert schema.evaluate_readiness(Quest.load(path), QuestLogConfig.load(log).schema) == ["no spec or design"]


# --- checklist: -------------------------------------------------------------------


def test_checklist_counts_items_under_a_heading(isolated, make_log, write_quest):
    log = make_log(isolated, schema={"readiness": [
        {"require": {"checklist": "## Acceptance Criteria", "min": 1}, "message": "no criteria"},
    ]})
    path = write_quest(
        log, "QST-aaaaa",
        body="## Acceptance Criteria\n\n- [ ] one\n- [x] two\n\n## Log\n\n- did stuff\n",
    )

    assert schema.evaluate_readiness(Quest.load(path), QuestLogConfig.load(log).schema) == []


def test_checklist_fails_below_the_minimum(isolated, make_log, write_quest):
    log = make_log(isolated, schema={"readiness": [
        {"require": {"checklist": "## Acceptance Criteria", "min": 2}, "message": "need 2"},
    ]})
    path = write_quest(log, "QST-aaaaa", body="## Acceptance Criteria\n\n- [ ] only one\n")

    assert schema.evaluate_readiness(Quest.load(path), QuestLogConfig.load(log).schema) == ["need 2"]


def test_checklist_does_not_count_items_under_a_different_heading(isolated, make_log, write_quest):
    log = make_log(isolated, schema={"readiness": [
        {"require": {"checklist": "## Acceptance Criteria", "min": 1}, "message": "no criteria"},
    ]})
    path = write_quest(
        log, "QST-aaaaa",
        body="## Spec\n\n- [ ] not acceptance criteria\n\n## Acceptance Criteria\n\nnothing here\n",
    )

    assert schema.evaluate_readiness(Quest.load(path), QuestLogConfig.load(log).schema) == ["no criteria"]


def test_checklist_defaults_min_to_one(isolated, make_log, write_quest):
    log = make_log(isolated, schema={"readiness": [
        {"require": {"checklist": "## Acceptance Criteria"}, "message": "no criteria"},
    ]})
    path = write_quest(log, "QST-aaaaa", body="## Acceptance Criteria\n\n- [ ] one\n")

    assert schema.evaluate_readiness(Quest.load(path), QuestLogConfig.load(log).schema) == []


# --- when: --------------------------------------------------------------------


def test_when_guards_a_rule_conditionally(isolated, make_log, write_quest):
    log = make_log(
        isolated,
        schema={
            "fields": {"agentic": {"type": "enum", "values": ["afk", "hitl"]}},
            "readiness": [
                {
                    "when": "agentic=afk",
                    "require": {"where": "owner:exists"},
                    "message": "AFK work needs an accountable owner",
                },
            ],
        },
    )
    afk_no_owner = write_quest(log, "QST-aaaaa", agentic="afk", owner=None)
    afk_with_owner = write_quest(log, "QST-bbbbb", agentic="afk", owner="peter")
    not_afk = write_quest(log, "QST-ccccc", agentic="hitl", owner=None)

    cfg = QuestLogConfig.load(log).schema
    assert schema.evaluate_readiness(Quest.load(afk_no_owner), cfg) == ["AFK work needs an accountable owner"]
    assert schema.evaluate_readiness(Quest.load(afk_with_owner), cfg) == []
    assert schema.evaluate_readiness(Quest.load(not_afk), cfg) == []  # guard not met, rule skipped


def test_multiple_failures_are_all_reported(isolated, make_log, write_quest, absent):
    log = make_log(isolated)
    path = write_quest(
        log, "QST-aaaaa", status="draft", description=absent,
        body="## Description\n\nnothing else\n",
    )

    failures = schema.evaluate_readiness(Quest.load(path), QuestLogConfig.load(log).schema)

    assert len(failures) >= 2  # no description, still a draft, no spec, no criteria


# --- validate never enforces readiness ---------------------------------------------


def test_quest_validate_does_not_enforce_readiness(isolated, make_log, write_quest, run):
    """An entirely ungroomed quest -- no description, no spec, no criteria,
    still draft -- must still validate clean. Readiness is advisory."""
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", status="draft", description=None, body="## Description\n\nbare\n")

    assert run("validate", "--in", str(log)).code == 0


def test_the_household_style_schema_can_override_the_list_to_one_rule(isolated, make_log, write_quest, run):
    log = make_log(isolated, schema={
        "readiness": [{"require": {"where": "description:exists"}, "message": "needs a description"}],
    })
    write_quest(log, "QST-aaaaa", status="draft", description="A chore")

    cfg = QuestLogConfig.load(log).schema
    assert len(cfg.readiness) == 1
    path = next(log.glob("QST-*.md"))
    assert schema.evaluate_readiness(Quest.load(path), cfg) == []
