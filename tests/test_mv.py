"""Tests for `quest mv`: cross-log moves, git mv/rm+add mechanics, project drift, auto-commit."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from questkit.cli import main
from questkit.config import QuestLogConfig


def _git_init(repo_root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_root, check=True)


def _git_log(repo_root: Path) -> str:
    return subprocess.run(
        ["git", "log", "--oneline"], cwd=repo_root, check=True, capture_output=True, text=True
    ).stdout


def _git_status(repo_root: Path) -> str:
    return subprocess.run(
        ["git", "status", "--short"], cwd=repo_root, check=True, capture_output=True, text=True
    ).stdout


def _make_log(quests_dir: Path, project: str, git: str = "manual") -> None:
    quests_dir.mkdir(parents=True, exist_ok=True)
    QuestLogConfig(project=project, git=git).save(quests_dir)


@pytest.fixture(autouse=True)
def _no_quest_log_env(monkeypatch):
    monkeypatch.delenv("QUEST_LOG", raising=False)


def _new_quest(quests_dir: Path, title: str = "Example quest") -> str:
    assert main(["new", title, "--in", str(quests_dir)]) == 0
    (path,) = quests_dir.glob("QST-*.md")
    return path.name.split("--")[0]


def test_mv_same_repo_uses_git_mv_and_commits_as_one(tmp_path, capsys):
    repo = tmp_path / "repo"
    src = repo / "common" / "quests"
    dest = repo / "questkit" / "quests"
    _make_log(src, project="common")
    _make_log(dest, project="questkit", git="auto")
    _git_init(repo)
    quest_id = _new_quest(src)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=repo, check=True)
    capsys.readouterr()

    exit_code = main(["mv", quest_id, str(dest), "--in", str(src)])

    assert exit_code == 0
    assert not any(src.glob(f"{quest_id}*.md"))
    (moved,) = dest.glob(f"{quest_id}*.md")
    text = moved.read_text()
    assert "project: questkit" in text

    status = _git_status(repo)
    assert status == ""  # git:auto committed everything

    log = _git_log(repo)
    assert log.count("\n") == 2  # seed + one move commit, no stray second commit
    assert "move" in log.splitlines()[0]


def test_mv_same_repo_manual_stages_but_does_not_commit(tmp_path):
    repo = tmp_path / "repo"
    src = repo / "a" / "quests"
    dest = repo / "b" / "quests"
    _make_log(src, project="a")
    _make_log(dest, project="b", git="manual")
    _git_init(repo)
    quest_id = _new_quest(src)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=repo, check=True)

    assert main(["mv", quest_id, str(dest), "--in", str(src)]) == 0

    status = _git_status(repo)
    # old path staged as deleted (part of the rename), new path staged as added/modified
    assert "R  " in status or ("D  " in status and "A  " in status)
    log = _git_log(repo)
    assert log.count("\n") == 1  # only the seed commit -- move left uncommitted


def test_mv_cross_repo_commits_independently(tmp_path):
    src_repo = tmp_path / "src_repo"
    dest_repo = tmp_path / "dest_repo"
    src = src_repo / "quests"
    dest = dest_repo / "quests"
    _make_log(src, project="common", git="auto")
    _make_log(dest, project="system", git="auto")
    _git_init(src_repo)
    _git_init(dest_repo)
    quest_id = _new_quest(src)
    subprocess.run(["git", "add", "-A"], cwd=src_repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=src_repo, check=True)
    subprocess.run(["git", "add", "-A"], cwd=dest_repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=dest_repo, check=True)

    assert main(["mv", quest_id, str(dest), "--in", str(src)]) == 0

    assert not any(src.glob(f"{quest_id}*.md"))
    (moved,) = dest.glob(f"{quest_id}*.md")
    assert "project: system" in moved.read_text()

    assert _git_status(src_repo) == ""
    assert _git_status(dest_repo) == ""
    assert "move" in _git_log(src_repo).splitlines()[0]
    assert "adopt" in _git_log(dest_repo).splitlines()[0]


def test_mv_cross_repo_manual_leaves_both_sides_staged(tmp_path):
    src_repo = tmp_path / "src_repo"
    dest_repo = tmp_path / "dest_repo"
    src = src_repo / "quests"
    dest = dest_repo / "quests"
    _make_log(src, project="common", git="manual")
    _make_log(dest, project="system", git="manual")
    _git_init(src_repo)
    _git_init(dest_repo)
    quest_id = _new_quest(src)
    subprocess.run(["git", "add", "-A"], cwd=src_repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=src_repo, check=True)
    subprocess.run(["git", "add", "-A"], cwd=dest_repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=dest_repo, check=True)

    assert main(["mv", quest_id, str(dest), "--in", str(src)]) == 0

    assert "D  " in _git_status(src_repo)
    assert _git_status(dest_repo).strip() != ""
    assert _git_log(src_repo).count("\n") == 1
    assert _git_log(dest_repo).count("\n") == 1


def test_mv_without_git_is_a_plain_filesystem_move(tmp_path):
    src = tmp_path / "a" / "quests"
    dest = tmp_path / "b" / "quests"
    _make_log(src, project="a")
    _make_log(dest, project="b")
    quest_id = _new_quest(src)

    assert main(["mv", quest_id, str(dest), "--in", str(src)]) == 0

    assert not any(src.glob(f"{quest_id}*.md"))
    (moved,) = dest.glob(f"{quest_id}*.md")
    assert "project: b" in moved.read_text()


def test_mv_no_project_configured_on_dest_leaves_field_untouched(tmp_path, capsys):
    src = tmp_path / "a" / "quests"
    dest = tmp_path / "b" / "quests"
    _make_log(src, project="a")
    _make_log(dest, project=None)
    quest_id = _new_quest(src)
    capsys.readouterr()

    assert main(["mv", quest_id, str(dest), "--in", str(src)]) == 0

    (moved,) = dest.glob(f"{quest_id}*.md")
    assert "project: a" in moved.read_text()
    assert "declares no project" in capsys.readouterr().out


def test_mv_aborts_on_destination_filename_collision(tmp_path):
    src = tmp_path / "a" / "quests"
    dest = tmp_path / "b" / "quests"
    _make_log(src, project="a")
    _make_log(dest, project="b")
    quest_id = _new_quest(src)
    (existing_name,) = [p.name for p in src.glob(f"{quest_id}*.md")]
    (dest / existing_name).write_text("collision")

    assert main(["mv", quest_id, str(dest), "--in", str(src)]) == 1
    assert any(src.glob(f"{quest_id}*.md"))  # untouched


def test_mv_same_log_is_a_no_op_error(tmp_path):
    quests_dir = tmp_path / "quests"
    _make_log(quests_dir, project="a")
    quest_id = _new_quest(quests_dir)

    assert main(["mv", quest_id, str(quests_dir), "--in", str(quests_dir)]) == 1


def test_mv_unknown_destination_log_errors(tmp_path):
    src = tmp_path / "a" / "quests"
    _make_log(src, project="a")
    quest_id = _new_quest(src)
    not_a_log = tmp_path / "nowhere"
    not_a_log.mkdir()

    assert main(["mv", quest_id, str(not_a_log), "--in", str(src)]) == 1


def test_mv_bumps_modified(tmp_path, monkeypatch):
    monkeypatch.setattr("questkit.commands.mv.today", lambda: "2099-01-01")
    src = tmp_path / "a" / "quests"
    dest = tmp_path / "b" / "quests"
    _make_log(src, project="a")
    _make_log(dest, project="b")
    quest_id = _new_quest(src)

    assert main(["mv", quest_id, str(dest), "--in", str(src)]) == 0

    (moved,) = dest.glob(f"{quest_id}*.md")
    assert "modified: '2099-01-01'" in moved.read_text() or "modified: 2099-01-01" in moved.read_text()
