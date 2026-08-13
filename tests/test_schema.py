"""Tests for frontmatter validation, including the AFK-readiness rule."""

from pathlib import Path

from questkit import schema
from questkit.quest import Quest
from questkit.utils import slugify


def _quest(frontmatter, body="", path=None):
    """Build a Quest whose path/aliases self-consistently match frontmatter
    by default, so tests targeting one rule don't incidentally trip the
    identity-drift checks. Pass path= explicitly to test drift itself."""
    fm = dict(frontmatter)
    if "aliases" not in fm and fm.get("id"):
        fm["aliases"] = [fm["id"]]
    if path is None:
        slug = slugify(fm["title"]) if fm.get("title") else "test"
        path = Path(f"{fm.get('id', 'QST-abcde')}--{slug}.md")
    return Quest(path=path, frontmatter=fm, body=body)


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


def _base_fm(**overrides):
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
    }
    fm.update(overrides)
    return fm


def test_filename_id_disagreeing_with_frontmatter_id_is_flagged():
    errors = schema.validate_quest(
        _quest(_base_fm(), path=Path("QST-zzzzz--example.md"))
    )
    messages = " ".join(e.message for e in errors)
    assert "filename id" in messages


def test_filename_slug_disagreeing_with_title_is_flagged():
    quest = _quest(_base_fm(title="A brand new title"), path=Path("QST-abcde--example.md"))

    errors = schema.check_slug_drift(quest)

    messages = " ".join(e.message for e in errors)
    assert "filename slug" in messages
    assert "a-brand-new-title" in messages


def test_slug_drift_is_not_part_of_validate_quest_hard_rules():
    quest = _quest(_base_fm(title="A brand new title"), path=Path("QST-abcde--example.md"))

    assert schema.validate_quest(quest) == []


def test_missing_self_alias_is_flagged():
    fm = _base_fm(aliases=["QST-somebody-else"])
    errors = schema.validate_quest(_quest(fm, path=Path("QST-abcde--example.md")))
    messages = " ".join(e.message for e in errors)
    assert "aliases does not include" in messages


def test_consistent_identity_has_no_drift_errors():
    assert schema.validate_quest(_quest(_base_fm())) == []
