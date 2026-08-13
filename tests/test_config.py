"""Tests for `.questkit.yaml` load/save."""

import pytest

from questkit import schema
from questkit.config import (
    CONFIG_FILENAME,
    ConfigVersionError,
    IgnoreConfigError,
    QuestLogConfig,
    config_exists,
)


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


def test_load_with_no_schema_block_is_fully_backward_compatible(tmp_path):
    (tmp_path / CONFIG_FILENAME).write_text("version: 1\n")

    loaded = QuestLogConfig.load(tmp_path)

    assert loaded.schema == schema.SchemaConfig.default()
    assert loaded.ignore == []


def test_load_wires_schema_block_through(tmp_path):
    (tmp_path / CONFIG_FILENAME).write_text(
        "version: 1\nschema:\n  fields:\n    sprint:\n      type: string\n      required: true\n"
    )

    loaded = QuestLogConfig.load(tmp_path)

    assert loaded.schema.fields["sprint"].required is True


def test_resolved_ignores_returns_literal_patterns(tmp_path):
    (tmp_path / CONFIG_FILENAME).write_text("version: 1\nignore:\n  - dist\n  - coverage\n")

    loaded = QuestLogConfig.load(tmp_path)

    assert loaded.resolved_ignores(tmp_path) == ["dist", "coverage"]


def test_resolved_ignores_expands_include_directive(tmp_path):
    (tmp_path / "shared-ignores.txt").write_text("// a comment\nbuild\ntarget\n")
    (tmp_path / CONFIG_FILENAME).write_text("version: 1\nignore:\n  - '#include shared-ignores.txt'\n")

    loaded = QuestLogConfig.load(tmp_path)

    assert loaded.resolved_ignores(tmp_path) == ["build", "target"]


def test_resolved_ignores_include_chains_recursively(tmp_path):
    (tmp_path / "grandparent.txt").write_text("build\n")
    (tmp_path / "parent.txt").write_text("#include grandparent.txt\ntarget\n")
    (tmp_path / CONFIG_FILENAME).write_text("version: 1\nignore:\n  - '#include parent.txt'\n")

    loaded = QuestLogConfig.load(tmp_path)

    assert loaded.resolved_ignores(tmp_path) == ["build", "target"]


def test_resolved_ignores_missing_include_target_raises(tmp_path):
    (tmp_path / CONFIG_FILENAME).write_text("version: 1\nignore:\n  - '#include nope.txt'\n")

    loaded = QuestLogConfig.load(tmp_path)

    with pytest.raises(IgnoreConfigError):
        loaded.resolved_ignores(tmp_path)


def test_resolved_ignores_circular_include_raises(tmp_path):
    (tmp_path / "a.txt").write_text("#include b.txt\n")
    (tmp_path / "b.txt").write_text("#include a.txt\n")
    (tmp_path / CONFIG_FILENAME).write_text("version: 1\nignore:\n  - '#include a.txt'\n")

    loaded = QuestLogConfig.load(tmp_path)

    with pytest.raises(IgnoreConfigError):
        loaded.resolved_ignores(tmp_path)
