"""Tests for QST-xk7js's `quest brief` -- a self-contained, agent-agnostic
Markdown work order.

READY (is this document executable as written -- schema `readiness:` rules)
and STATE (should anyone pick it up right now -- computed graph facts) are
separate verdicts: only a READY failure collapses the brief; a STATE failure
is a warning, never a refusal.
"""

from __future__ import annotations

_SPEC_BODY = """## Spec

Do the actual thing.

## Acceptance Criteria

- [ ] It works
"""


def test_a_groomed_quest_gets_the_full_brief(isolated, make_log, write_quest, run):
    log = make_log(isolated, project="proj")
    write_quest(log, "QST-aaaaa", status="todo", body=_SPEC_BODY)

    result = run("brief", "QST-aaaaa", "--in", str(log))

    assert result.code == 0
    assert "LOCATION" in result.out
    assert "SPEC" in result.out
    assert "ACCEPTANCE" in result.out
    assert "DEPENDENCIES" in result.out
    assert "REPORT BACK" in result.out
    assert "READY" in result.out
    assert "STATE" in result.out
    assert "Do the actual thing." in result.out
    assert "It works" in result.out


def test_an_ungroomed_quest_collapses_to_header_location_and_warnings(
    isolated, make_log, write_quest, run
):
    log = make_log(isolated, project="proj")
    write_quest(log, "QST-aaaaa", status="draft", description=None)

    result = run("brief", "QST-aaaaa", "--in", str(log))

    assert result.code == 0
    assert "LOCATION" in result.out
    assert "READY" in result.out
    assert "NOT implementation-ready" in result.out
    assert "SPEC" not in result.out
    assert "ACCEPTANCE" not in result.out
    assert "DEPENDENCIES" not in result.out
    assert "REPORT BACK" not in result.out


def test_ready_and_state_are_separate_lines(isolated, make_log, write_quest, run):
    log = make_log(isolated, project="proj")
    write_quest(log, "QST-aaaaa", status="todo", body=_SPEC_BODY)

    result = run("brief", "QST-aaaaa", "--in", str(log))

    lines = result.out.splitlines()
    ready_line = next(line for line in lines if line.startswith("READY"))
    state_line = next(line for line in lines if line.startswith("STATE"))
    assert ready_line != state_line


def test_ready_comes_from_the_schemas_own_readiness_rules_only(isolated, make_log, write_quest, run):
    """A household schema needing only a description reports READY, with no
    hardcoded spec/acceptance-criteria requirement."""
    log = make_log(
        isolated,
        project="household",
        schema={"readiness": [{"require": {"where": "description:exists"}, "message": "no description"}]},
    )
    write_quest(log, "QST-aaaaa", status="todo", description="Buy milk", body="## Description\n\nBuy milk.\n")

    result = run("brief", "QST-aaaaa", "--in", str(log))

    assert "READY  ✅" in result.out
    assert "NOT implementation-ready" not in result.out


def test_brief_never_fails_on_agentic_specifically(isolated, make_log, write_quest, run):
    log = make_log(
        isolated,
        project="proj",
        schema={"readiness": [{"require": {"where": "description:exists"}, "message": "no description"}]},
    )
    write_quest(log, "QST-aaaaa", status="todo", description="A thing", body="## Description\n\nA thing.\n")

    result = run("brief", "QST-aaaaa", "--in", str(log))

    assert "READY  ✅" in result.out


def test_a_blocked_quest_still_gets_a_full_brief_naming_the_blocker(
    isolated, make_log, write_quest, run
):
    log = make_log(isolated, project="proj")
    write_quest(log, "QST-aaaaa", slug="a", status="todo", body=_SPEC_BODY)
    write_quest(
        log, "QST-bbbbb", slug="b", status="todo", blocked_by=["QST-aaaaa"], body=_SPEC_BODY
    )

    result = run("brief", "QST-bbbbb", "--in", str(log))

    assert result.code == 0
    assert "SPEC" in result.out  # full brief, not collapsed
    state_line = next(line for line in result.out.splitlines() if line.startswith("STATE"))
    assert "QST-aaaaa" in state_line
    assert "blocked" in state_line.lower()


def test_a_completed_quest_warns_but_still_briefs(isolated, make_log, write_quest, run):
    log = make_log(isolated, project="proj")
    write_quest(log, "QST-aaaaa", status="done", body=_SPEC_BODY)

    result = run("brief", "QST-aaaaa", "--in", str(log))

    assert result.code == 0
    assert "SPEC" in result.out
    state_line = next(line for line in result.out.splitlines() if line.startswith("STATE"))
    assert "done" in state_line.lower()


def test_only_a_ready_failure_produces_the_not_implementation_ready_verdict(
    isolated, make_log, write_quest, run
):
    log = make_log(isolated, project="proj")
    write_quest(log, "QST-aaaaa", slug="a", status="todo", body=_SPEC_BODY)
    write_quest(
        log, "QST-bbbbb", slug="b", status="todo", blocked_by=["QST-aaaaa"], body=_SPEC_BODY
    )

    result = run("brief", "QST-bbbbb", "--in", str(log))

    assert "NOT implementation-ready" not in result.out


def test_dependencies_resolves_blocked_by_to_title_status_and_path(isolated, make_log, write_quest, run):
    log = make_log(isolated, project="proj")
    write_quest(log, "QST-aaaaa", slug="a", status="done", title="The dependency")
    write_quest(
        log, "QST-bbbbb", slug="b", status="todo", blocked_by=["QST-aaaaa"], body=_SPEC_BODY
    )

    result = run("brief", "QST-bbbbb", "--in", str(log))

    assert "QST-aaaaa" in result.out
    assert "done" in result.out


def test_dependencies_lists_reverse_dependents_via_blocks(isolated, make_log, write_quest, run):
    log = make_log(isolated, project="proj")
    write_quest(log, "QST-aaaaa", slug="a", status="todo", body=_SPEC_BODY)
    write_quest(log, "QST-bbbbb", slug="b", status="todo", blocked_by=["QST-aaaaa"])

    result = run("brief", "QST-aaaaa", "--in", str(log))

    assert "QST-bbbbb" in result.out
    assert "blocks" in result.out.lower()


def test_report_back_names_exact_commands_and_the_commit_prefix(isolated, make_log, write_quest, run):
    log = make_log(isolated, "proj", project="proj")
    write_quest(log, "QST-aaaaa", status="todo", body=_SPEC_BODY)

    result = run("brief", "QST-aaaaa", "--in", str(log))

    assert "quest set QST-aaaaa status=in-progress" in result.out
    assert "quest done QST-aaaaa" in result.out
    assert "quest(proj):" in result.out


def test_report_back_omits_the_start_work_line_when_the_schema_renamed_in_progress(
    isolated, make_log, write_quest, run
):
    """A schema that renamed `in-progress` (e.g. household.yaml's `doing`) has
    no declared equivalent -- REPORT BACK must never suggest a status value
    that isn't actually in this log's own vocabulary."""
    log = make_log(
        isolated,
        project="household",
        schema={"statuses": ["draft", "waiting", "doing", "done", "scrapped"]},
    )
    write_quest(log, "QST-aaaaa", status="waiting", body=_SPEC_BODY)

    result = run("brief", "QST-aaaaa", "--in", str(log))

    assert "status=in-progress" not in result.out
    assert "quest done QST-aaaaa" in result.out


def test_schema_block_is_omitted_for_a_default_vocabulary_log(isolated, make_log, write_quest, run):
    log = make_log(isolated, project="proj")
    write_quest(log, "QST-aaaaa", status="todo", body=_SPEC_BODY)

    result = run("brief", "QST-aaaaa", "--in", str(log))

    assert "SCHEMA" not in result.out


def test_schema_block_is_present_when_the_log_declares_custom_fields(isolated, make_log, write_quest, run):
    log = make_log(isolated, project="proj", schema={"fields": {"component": {"type": "string"}}})
    write_quest(log, "QST-aaaaa", status="todo", body=_SPEC_BODY)

    result = run("brief", "QST-aaaaa", "--in", str(log))

    assert "SCHEMA" in result.out


def test_header_metadata_line_surfaces_a_schema_declared_custom_field_value(
    isolated, make_log, write_quest, run
):
    """QST-onxad: a schema-declared custom field (e.g. `language`) reaches the
    header's metadata line for free, the same way `effort`/`tier` do -- no
    core field, no brief_cmd change needed per log."""
    log = make_log(
        isolated,
        project="proj",
        schema={"fields": {"language": {"type": "enum", "values": ["sv", "en"], "default": "sv"}}},
    )
    write_quest(log, "QST-aaaaa", status="todo", body=_SPEC_BODY, language="sv")

    result = run("brief", "QST-aaaaa", "--in", str(log))

    assert "language=sv" in result.out


def test_header_metadata_line_omits_a_custom_field_with_no_value(isolated, make_log, write_quest, run):
    log = make_log(isolated, project="proj", schema={"fields": {"language": {"type": "string"}}})
    write_quest(log, "QST-aaaaa", status="todo", body=_SPEC_BODY, language=None)

    result = run("brief", "QST-aaaaa", "--in", str(log))

    assert "language=" not in result.out


def test_output_contains_no_vendor_specific_text(isolated, make_log, write_quest, run):
    log = make_log(isolated, project="proj")
    write_quest(log, "QST-aaaaa", status="todo", body=_SPEC_BODY)

    result = run("brief", "QST-aaaaa", "--in", str(log))

    lowered = result.out.lower()
    for banned in ("claude", "anthropic", "openai", "gpt", "system prompt"):
        assert banned not in lowered


def test_unknown_id_is_an_error(isolated, make_log, run):
    make_log(isolated, project="proj")

    result = run("brief", "QST-zzzzz", "--in", str(isolated / "quests"))

    assert result.code == 1
