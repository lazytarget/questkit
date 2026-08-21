"""Tests for QST-e6g6t's `quest commit`: exact tracked pathspec, deterministic
message, and hook-failure propagation.

Only the in-repo pieces are covered here -- the realm-01 systemd timer is
infrastructure outside this repository and is not testable from it (see the
quest's own Log).
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def _git_init(repo_root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_root, check=True)


def _git_log(repo_root: Path) -> str:
    return subprocess.run(
        ["git", "log", "--format=%s%n%b", "-1"], cwd=repo_root, capture_output=True, text=True
    ).stdout


def _seed(repo_root: Path) -> None:
    subprocess.run(["git", "add", "-A"], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=repo_root, check=True)


def test_commits_only_the_tracked_pathspec_ignoring_staged_unrelated_code(
    tmp_path, make_log, write_quest, run
):
    repo = tmp_path
    _git_init(repo)
    log = make_log(repo, project="proj", git="manual")
    write_quest(log, "QST-aaaaa", status="todo")
    (repo / "code.py").write_text("print(1)\n")
    _seed(repo)

    write_quest(log, "QST-bbbbb", status="todo")
    (repo / "code.py").write_text("print(2)\n")  # unrelated, staged code change
    subprocess.run(["git", "add", "code.py"], cwd=repo, check=True)

    result = run("commit", "--in", str(log))

    assert result.code == 0
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True
    ).stdout
    # the quest file was committed; the staged code change is still pending
    assert "QST-bbbbb" not in status
    assert "code.py" in status


def test_message_is_derived_from_the_frontmatter_diff(tmp_path, make_log, write_quest, run):
    repo = tmp_path
    _git_init(repo)
    log = make_log(repo, project="family", git="manual")
    write_quest(log, "QST-aaaaa", status="todo", title="Existing quest")
    _seed(repo)

    write_quest(log, "QST-bbbbb", status="todo", title="New quest")

    result = run("commit", "--in", str(log))

    assert result.code == 0
    message = _git_log(repo)
    assert "quest(family): add 1" in message
    assert "QST-bbbbb" in message
    assert "New quest" in message


def test_a_status_update_is_reported_as_a_transition(tmp_path, make_log, write_quest, run):
    repo = tmp_path
    _git_init(repo)
    log = make_log(repo, project="proj", git="manual")
    write_quest(log, "QST-aaaaa", status="todo")
    _seed(repo)

    path = next(log.glob("QST-*.md"))
    text = path.read_text().replace("status: todo", "status: done")
    path.write_text(text)

    result = run("commit", "--in", str(log))

    assert result.code == 0
    message = _git_log(repo)
    assert "update 1" in message
    assert "status: todo → done" in message


def test_nothing_to_commit_exits_zero_and_writes_no_empty_commit(tmp_path, make_log, write_quest, run):
    repo = tmp_path
    _git_init(repo)
    log = make_log(repo, project="proj", git="manual")
    write_quest(log, "QST-aaaaa", status="todo")
    _seed(repo)

    before = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True
    ).stdout

    result = run("commit", "--in", str(log))

    assert result.code == 0
    after = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True
    ).stdout
    assert before == after


def test_hook_failure_without_no_verify_exits_nonzero_and_prints_output(
    tmp_path, make_log, write_quest, run
):
    repo = tmp_path
    _git_init(repo)
    hooks_dir = repo / ".git" / "hooks"
    pre_commit = hooks_dir / "pre-commit"
    pre_commit.write_text("#!/bin/sh\necho 'rejected by hook' >&2\nexit 1\n")
    pre_commit.chmod(0o755)

    log = make_log(repo, project="proj", git="manual")
    write_quest(log, "QST-aaaaa", status="todo")

    result = run("commit", "--in", str(log))

    assert result.code == 1
    assert "rejected by hook" in result.err


def test_no_verify_bypasses_the_hook(tmp_path, make_log, write_quest, run):
    repo = tmp_path
    _git_init(repo)
    hooks_dir = repo / ".git" / "hooks"
    pre_commit = hooks_dir / "pre-commit"
    pre_commit.write_text("#!/bin/sh\nexit 1\n")
    pre_commit.chmod(0o755)

    log = make_log(repo, project="proj", git="manual")
    write_quest(log, "QST-aaaaa", status="todo")

    result = run("commit", "--in", str(log), "--no-verify")

    assert result.code == 0


def test_push_is_off_by_default_and_no_remote_is_needed(tmp_path, make_log, write_quest, run):
    repo = tmp_path
    _git_init(repo)
    log = make_log(repo, project="proj", git="manual")
    write_quest(log, "QST-aaaaa", status="todo")

    result = run("commit", "--in", str(log))

    assert result.code == 0
