"""Tests for `agentic` leaving the core schema entirely.

`afk|hitl` is not a universal vocabulary -- household work has no
unsupervised-agent axis, so shipping one in the core is questkit having an
opinion about what kind of work its users do. Both hardcoded rules that
guarded it (AFK requires a non-draft status; agentic is meaningless on an
epic) are removed and not reintroduced elsewhere -- the general mechanism
that replaces both is `readiness:` (see test_readiness.py).
"""

from __future__ import annotations

from questkit import schema
from questkit.quest import Quest


def test_agentic_modes_is_gone_from_schema():
    assert not hasattr(schema, "AGENTIC_MODES")


def test_agentic_is_not_a_core_field():
    assert "agentic" not in schema.CORE_FIELDS


def test_agentic_afk_no_longer_requires_a_spec_or_criteria_section(
    isolated, make_log, write_quest, run
):
    """The old hardcoded AFK rule is gone outright, not relocated into validate."""
    log = make_log(
        isolated,
        schema={"fields": {"agentic": {"type": "enum", "values": ["afk", "hitl"]}}},
    )
    write_quest(log, "QST-aaaaa", agentic="afk", body="## Description\n\nNothing else.\n")

    assert run("validate", "--in", str(log)).code == 0


def test_agentic_on_a_draft_quest_no_longer_errors(isolated, make_log, write_quest, run):
    """The old rule: 'afk requires a non-draft status'. Not reintroduced."""
    log = make_log(
        isolated,
        schema={"fields": {"agentic": {"type": "enum", "values": ["afk", "hitl"]}}},
    )
    write_quest(log, "QST-aaaaa", status="draft", agentic="afk", description=None)

    assert run("validate", "--in", str(log)).code == 0


def test_agentic_on_an_epic_no_longer_errors(isolated, make_log, write_quest, run):
    """The old rule: 'agentic is meaningless on type: epic'. Not reintroduced."""
    log = make_log(
        isolated,
        schema={"fields": {"agentic": {"type": "enum", "values": ["afk", "hitl"]}}},
    )
    write_quest(log, "QST-aaaaa", type="epic", agentic="afk")

    assert run("validate", "--in", str(log)).code == 0


def test_agentic_still_validates_against_its_declared_values(isolated, make_log, write_quest, run):
    log = make_log(
        isolated,
        schema={"fields": {"agentic": {"type": "enum", "values": ["afk", "hitl"]}}},
    )
    write_quest(log, "QST-aaaaa", agentic="nonsense")

    result = run("validate", "--in", str(log))

    assert result.code == 1
    assert "agentic" in result.out


def test_set_agentic_afk_errors_under_strict_in_a_log_that_has_not_declared_it(
    isolated, make_log, run
):
    log = make_log(isolated)

    result = run("new", "A quest", "--status", "todo", "--set", "agentic=afk", "--in", str(log))

    assert result.code == 1
    assert "agentic" in result.err


def test_set_agentic_afk_succeeds_in_a_log_that_declares_it(isolated, make_log, run):
    log = make_log(
        isolated,
        schema={"fields": {"agentic": {"type": "enum", "values": ["afk", "hitl"]}}},
    )

    result = run("new", "A quest", "--status", "todo", "--set", "agentic=afk", "--in", str(log))

    assert result.code == 0
    assert Quest.load(next(log.glob("QST-*.md"))).get("agentic") == "afk"


def test_the_development_schema_declares_agentic_component_related_adrs_and_milestone():
    """A characterization test for 99-system/questkit/schemas/development.yaml,
    which this repo's own log already adopts."""
    from pathlib import Path

    from questkit.config import QuestLogConfig

    quests_dir = Path(__file__).resolve().parents[1] / "quests"
    config = QuestLogConfig.load(quests_dir)

    assert config.schema.fields["agentic"].values == ("afk", "hitl")
    assert "component" in config.schema.fields
    assert "related_adrs" in config.schema.fields
    assert "milestone" in config.schema.fields
