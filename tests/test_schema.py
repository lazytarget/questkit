"""Tests for frontmatter validation, including the AFK-readiness rule."""

from pathlib import Path

from questkit import schema
from questkit.quest import Quest


def _quest(frontmatter, body=""):
    return Quest(path=Path("QST-test.md"), frontmatter=frontmatter, body=body)


def test_valid_quest_has_no_errors():
    fm = {
        "id": "QST-abcde",
        "title": "Example",
        "description": "A thing to do",
        "created": "2026-08-13",
        "modified": "2026-08-13",
        "type": "task",
        "status": "todo",
        "priority": "medium",
        "tags": ["x"],
    }
    assert schema.validate_quest(_quest(fm)) == []


def test_draft_status_exempts_description():
    fm = {
        "id": "QST-abcde",
        "title": "Example",
        "created": "2026-08-13",
        "modified": "2026-08-13",
        "type": "task",
        "status": "draft",
        "priority": "medium",
        "tags": [],
    }
    assert schema.validate_quest(_quest(fm)) == []


def test_unknown_status_is_flagged():
    fm = {
        "id": "QST-abcde",
        "title": "Example",
        "description": "A thing to do",
        "created": "2026-08-13",
        "modified": "2026-08-13",
        "type": "task",
        "status": "done",
        "priority": "medium",
        "tags": [],
    }
    errors = schema.validate_quest(_quest(fm))
    assert any("status" in e.message for e in errors)


def test_afk_without_acceptance_criteria_is_flagged():
    fm = {
        "id": "QST-abcde",
        "title": "Example",
        "description": "A thing to do",
        "created": "2026-08-13",
        "modified": "2026-08-13",
        "type": "task",
        "status": "todo",
        "priority": "medium",
        "tags": [],
        "agentic": "afk",
    }
    errors = schema.validate_quest(_quest(fm, body="## Description\n\nNothing else here.\n"))
    messages = " ".join(e.message for e in errors)
    assert "Acceptance Criteria" in messages
    assert "Spec" in messages


def test_afk_with_full_spec_passes():
    fm = {
        "id": "QST-abcde",
        "title": "Example",
        "description": "A thing to do",
        "created": "2026-08-13",
        "modified": "2026-08-13",
        "type": "task",
        "status": "todo",
        "priority": "medium",
        "tags": [],
        "agentic": "afk",
    }
    body = (
        "## Description\n\nDo the thing.\n\n"
        "## Spec\n\nDetails here.\n\n"
        "## Acceptance Criteria\n\n- [ ] step one\n"
    )
    assert schema.validate_quest(_quest(fm, body=body)) == []
