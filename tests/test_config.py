"""Tests for `.questkit.yaml` load/save."""

import pytest

from questkit.config import CONFIG_FILENAME, ConfigVersionError, QuestLogConfig, config_exists


def test_save_and_load_round_trip(tmp_path):
    config = QuestLogConfig(git="auto", project="pensieve")
    config.save(tmp_path)
    assert config_exists(tmp_path)

    loaded = QuestLogConfig.load(tmp_path)

    assert loaded.git == "auto"
    assert loaded.project == "pensieve"
    assert loaded.pattern == "QST-*.md"


def test_load_rejects_unsupported_version(tmp_path):
    (tmp_path / CONFIG_FILENAME).write_text("version: 999\n")

    with pytest.raises(ConfigVersionError):
        QuestLogConfig.load(tmp_path)


def test_defaults_are_merged_not_replaced(tmp_path):
    (tmp_path / CONFIG_FILENAME).write_text("version: 1\ndefaults:\n  priority: high\n")

    loaded = QuestLogConfig.load(tmp_path)

    assert loaded.defaults["priority"] == "high"
    assert loaded.defaults["type"] == "task"


def test_no_project_by_default(tmp_path):
    QuestLogConfig().save(tmp_path)

    loaded = QuestLogConfig.load(tmp_path)

    assert loaded.project is None
