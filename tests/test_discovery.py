"""Tests for quest log resolution: --in, walk-up, QUEST_LOG, and the error case."""

import pytest

from questkit.config import CONFIG_FILENAME, QuestLogConfig
from questkit.discovery import (
    AmbiguousDestinationError,
    QuestLogNotFoundError,
    find_all_logs,
    resolve_log,
    resolve_log_for_new,
    resolve_mutation_target,
    resolve_sweep_root,
)


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


def _make_log(quests_dir, **config_kwargs):
    quests_dir.mkdir(parents=True, exist_ok=True)
    QuestLogConfig(**config_kwargs).save(quests_dir)
    return quests_dir


def _make_quest_file(quests_dir, quest_id):
    (quests_dir / f"{quest_id}--example.md").write_text("---\nid: " + quest_id + "\n---\n")


# --- find_all_logs: default pruning, custom ignore:, #include -----------------


def test_find_all_logs_finds_every_nested_log(tmp_path):
    _make_log(tmp_path / "a" / "quests")
    _make_log(tmp_path / "b" / "nested" / "quests")

    found = find_all_logs(tmp_path)

    assert found == sorted([tmp_path / "a" / "quests", tmp_path / "b" / "nested" / "quests"])


def test_find_all_logs_prunes_default_ignore_dirs(tmp_path):
    _make_log(tmp_path / "real" / "quests")
    _make_log(tmp_path / ".git" / "quests")
    _make_log(tmp_path / "node_modules" / "pkg" / "quests")

    found = find_all_logs(tmp_path)

    assert found == [tmp_path / "real" / "quests"]


def test_find_all_logs_local_ignore_only_scopes_its_own_subtree(tmp_path):
    a_quests = _make_log(tmp_path / "a" / "quests")
    (tmp_path / "a" / "quests" / CONFIG_FILENAME).write_text(
        "version: 1\nignore:\n  - dist\n"
    )
    _make_log(tmp_path / "a" / "dist" / "quests")  # pruned: inside a/'s own ignore
    _make_log(tmp_path / "b" / "dist" / "quests")  # NOT pruned: b/ never declared it

    found = find_all_logs(tmp_path)

    assert a_quests in found
    assert tmp_path / "a" / "dist" / "quests" not in found
    assert tmp_path / "b" / "dist" / "quests" in found


def test_find_all_logs_include_directive_extends_ignore_list(tmp_path):
    (tmp_path / "shared-ignore.txt").write_text("dist\n")
    _make_log(tmp_path / "a" / "quests")
    (tmp_path / "a" / "quests" / CONFIG_FILENAME).write_text(
        "version: 1\nignore:\n  - '#include ../../shared-ignore.txt'\n"
    )
    _make_log(tmp_path / "a" / "dist" / "quests")

    found = find_all_logs(tmp_path)

    assert tmp_path / "a" / "dist" / "quests" not in found


def test_find_all_logs_broken_include_is_skipped_with_a_warning_not_aborted(tmp_path, capsys):
    good = _make_log(tmp_path / "a" / "quests")
    broken = _make_log(tmp_path / "b" / "quests")
    (broken / CONFIG_FILENAME).write_text("version: 1\nignore:\n  - '#include nope.txt'\n")

    found = find_all_logs(tmp_path)

    assert good in found
    assert broken in found  # still a log -- just contributes no extra pruning
    assert "nope.txt" in capsys.readouterr().err


# --- resolve_sweep_root ---------------------------------------------------------


def test_resolve_sweep_root_explicit_wins(tmp_path, monkeypatch):
    monkeypatch.delenv("QST_ROOT", raising=False)
    explicit = tmp_path / "explicit"
    explicit.mkdir()

    assert resolve_sweep_root(explicit=str(explicit)) == explicit


def test_resolve_sweep_root_uses_env_var(tmp_path, monkeypatch):
    env_root = tmp_path / "env-root"
    env_root.mkdir()
    monkeypatch.setenv("QST_ROOT", str(env_root))

    assert resolve_sweep_root(start=tmp_path) == env_root


def test_resolve_sweep_root_falls_back_to_git_root(tmp_path, monkeypatch):
    monkeypatch.delenv("QST_ROOT", raising=False)
    (tmp_path / ".git").mkdir()
    nested = tmp_path / "src" / "deep"
    nested.mkdir(parents=True)

    assert resolve_sweep_root(start=nested) == tmp_path


def test_resolve_sweep_root_falls_back_to_start_when_no_git_root(tmp_path, monkeypatch):
    monkeypatch.delenv("QST_ROOT", raising=False)
    lonely = tmp_path / "lonely"
    lonely.mkdir()

    assert resolve_sweep_root(start=lonely) == lonely


# --- resolve_mutation_target: cross-log id resolution ---------------------------


def test_resolve_mutation_target_finds_id_in_nearest_log(tmp_path, monkeypatch):
    monkeypatch.delenv("QUEST_LOG", raising=False)
    monkeypatch.delenv("QST_ROOT", raising=False)
    quests_dir = _make_log(tmp_path / "proj" / "quests")
    _make_quest_file(quests_dir, "QST-aaaaa")

    found = resolve_mutation_target("QST-aaaaa", start=tmp_path / "proj")

    assert found == (quests_dir, quests_dir / "QST-aaaaa--example.md")


def test_resolve_mutation_target_sweeps_when_not_in_nearest_log(tmp_path, monkeypatch):
    monkeypatch.delenv("QUEST_LOG", raising=False)
    monkeypatch.setenv("QST_ROOT", str(tmp_path))
    nearest = _make_log(tmp_path / "proj_a" / "quests")
    elsewhere = _make_log(tmp_path / "proj_b" / "quests")
    _make_quest_file(elsewhere, "QST-bbbbb")

    found = resolve_mutation_target("QST-bbbbb", start=tmp_path / "proj_a")

    assert found == (elsewhere, elsewhere / "QST-bbbbb--example.md")
    assert nearest != elsewhere  # sanity: really did cross a log boundary


def test_resolve_mutation_target_returns_none_when_nowhere(tmp_path, monkeypatch):
    monkeypatch.delenv("QUEST_LOG", raising=False)
    monkeypatch.setenv("QST_ROOT", str(tmp_path))
    _make_log(tmp_path / "proj" / "quests")

    assert resolve_mutation_target("QST-zzzzz", start=tmp_path / "proj") is None


def test_resolve_mutation_target_explicit_in_does_not_sweep_past_it(tmp_path, monkeypatch):
    monkeypatch.setenv("QST_ROOT", str(tmp_path))
    empty_log = _make_log(tmp_path / "proj_a" / "quests")
    elsewhere = _make_log(tmp_path / "proj_b" / "quests")
    _make_quest_file(elsewhere, "QST-ccccc")

    found = resolve_mutation_target("QST-ccccc", explicit_in=str(empty_log))

    assert found is None  # --in is a precise override, not a sweep starting point


# --- resolve_log_for_new: the ambiguous-destination guard -----------------------


def test_resolve_log_for_new_explicit_is_unchanged(tmp_path):
    explicit = _make_log(tmp_path / "explicit")

    assert resolve_log_for_new(explicit=str(explicit)) == explicit


def test_resolve_log_for_new_walk_up_is_unchanged(tmp_path, monkeypatch):
    monkeypatch.delenv("QUEST_LOG", raising=False)
    quests_dir = _make_log(tmp_path / "zone" / "quests")
    nested = tmp_path / "zone" / "src"
    nested.mkdir()

    assert resolve_log_for_new(start=nested) == quests_dir


def test_resolve_log_for_new_raises_on_ambiguous_destination(tmp_path, monkeypatch):
    monkeypatch.delenv("QUEST_LOG", raising=False)
    _make_log(tmp_path / "a" / "quests")
    _make_log(tmp_path / "b" / "quests")

    with pytest.raises(AmbiguousDestinationError):
        resolve_log_for_new(start=tmp_path)


def test_resolve_log_for_new_falls_through_with_a_single_sub_log(tmp_path, monkeypatch):
    monkeypatch.delenv("QUEST_LOG", raising=False)
    _make_log(tmp_path / "only" / "quests")

    with pytest.raises(QuestLogNotFoundError):
        resolve_log_for_new(start=tmp_path)  # not ambiguous, but still no log *here*
