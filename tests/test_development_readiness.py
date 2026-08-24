"""Tests for QST-z1exq's per-type readiness rule in the `development` schema.

`when:` guards already shipped in v0.3 (see test_readiness.py) -- this is
schema authoring, not new engine code: `type=bug` gains a conditional rule
requiring a `## Repro` section before the brief reads READY. Loaded the same
way test_milestone_view.py and test_agentic_demotion.py characterize the real
`99-system/questkit/schemas/development.yaml` -- via this repo's own
`quests/` log, which already adopts `schema: development`.
"""

from __future__ import annotations

from pathlib import Path

from questkit import schema
from questkit.config import QuestLogConfig
from questkit.quest import Quest

_QUESTS_DIR = Path(__file__).resolve().parents[1] / "quests"


def _bug(tmp_path, body: str) -> Path:
    path = tmp_path / "QST-aaaaa--a-bug.md"
    path.write_text(
        "---\nid: QST-aaaaa\ntitle: A bug\ncreated: 2026-01-01\nmodified: 2026-01-01\n"
        "type: bug\nstatus: todo\npriority: medium\ndescription: d\ntags: []\n"
        "aliases:\n  - QST-aaaaa\n---\n\n" + body,
        encoding="utf-8",
    )
    return path


def test_the_development_schema_still_ships_the_four_universal_rules():
    config = QuestLogConfig.load(_QUESTS_DIR)

    messages = [rule.message for rule in config.schema.readiness]
    assert "no description" in messages
    assert "still a draft -- not groomed" in messages or "still a draft — not groomed" in messages
    assert any("acceptance criteria" in m for m in messages)


def test_a_bug_with_no_repro_section_fails_readiness(tmp_path):
    config = QuestLogConfig.load(_QUESTS_DIR)
    path = _bug(
        tmp_path,
        "## Spec\n\nSomething.\n\n## Acceptance Criteria\n\n- [ ] one\n",
    )

    failures = schema.evaluate_readiness(Quest.load(path), config.schema)

    assert any("repro" in f.lower() for f in failures)


def test_a_bug_with_a_repro_section_passes_that_rule(tmp_path):
    config = QuestLogConfig.load(_QUESTS_DIR)
    path = _bug(
        tmp_path,
        "## Repro\n\n1. do the thing\n\n## Acceptance Criteria\n\n- [ ] one\n",
    )

    failures = schema.evaluate_readiness(Quest.load(path), config.schema)

    assert not any("repro" in f.lower() for f in failures)


def test_a_non_bug_type_is_not_held_to_the_repro_rule(tmp_path):
    config = QuestLogConfig.load(_QUESTS_DIR)
    path = tmp_path / "QST-bbbbb--a-task.md"
    path.write_text(
        "---\nid: QST-bbbbb\ntitle: A task\ncreated: 2026-01-01\nmodified: 2026-01-01\n"
        "type: task\nstatus: todo\npriority: medium\ndescription: d\ntags: []\n"
        "aliases:\n  - QST-bbbbb\n---\n\n## Spec\n\nSomething.\n\n"
        "## Acceptance Criteria\n\n- [ ] one\n",
        encoding="utf-8",
    )

    failures = schema.evaluate_readiness(Quest.load(path), config.schema)

    assert not any("repro" in f.lower() for f in failures)
