"""Tests for quest log resolution: --in, walk-up, QUEST_LOG, and the error case."""

import pytest

from questkit.config import QuestLogConfig
from questkit.discovery import QuestLogNotFoundError, resolve_log


def test_resolve_log_walks_up_to_zone_quests_dir(tmp_path, monkeypatch):
    zone = tmp_path / "pensieve"
    quests_dir = zone / "quests"
    quests_dir.mkdir(parents=True)
    QuestLogConfig().save(quests_dir)

    nested = zone / "src" / "plugins"
    nested.mkdir(parents=True)
    monkeypatch.delenv("QUEST_LOG", raising=False)

    found = resolve_log(start=nested)

    assert found == quests_dir


def test_resolve_log_finds_marker_in_place(tmp_path, monkeypatch):
    log_dir = tmp_path / "common" / "quests"
    log_dir.mkdir(parents=True)
    QuestLogConfig().save(log_dir)
    monkeypatch.delenv("QUEST_LOG", raising=False)

    found = resolve_log(start=log_dir)

    assert found == log_dir


def test_resolve_log_falls_back_to_env(tmp_path, monkeypatch):
    log_dir = tmp_path / "central"
    log_dir.mkdir()
    QuestLogConfig().save(log_dir)

    empty = tmp_path / "elsewhere"
    empty.mkdir()
    monkeypatch.setenv("QUEST_LOG", str(log_dir))

    found = resolve_log(start=empty)

    assert found == log_dir


def test_resolve_log_raises_when_nothing_found(tmp_path, monkeypatch):
    monkeypatch.delenv("QUEST_LOG", raising=False)
    nowhere = tmp_path / "nowhere"
    nowhere.mkdir()

    with pytest.raises(QuestLogNotFoundError):
        resolve_log(start=nowhere)


def test_explicit_in_overrides_everything(tmp_path, monkeypatch):
    walked_dir = tmp_path / "walked"
    walked_quests = walked_dir / "quests"
    walked_quests.mkdir(parents=True)
    QuestLogConfig().save(walked_quests)

    explicit_dir = tmp_path / "explicit"
    explicit_dir.mkdir()
    QuestLogConfig().save(explicit_dir)
    monkeypatch.delenv("QUEST_LOG", raising=False)

    found = resolve_log(explicit=str(explicit_dir), start=walked_dir)

    assert found == explicit_dir


def test_explicit_in_without_config_raises(tmp_path):
    plain_dir = tmp_path / "plain"
    plain_dir.mkdir()

    with pytest.raises(QuestLogNotFoundError):
        resolve_log(explicit=str(plain_dir))
