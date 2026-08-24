"""Tests for QST-22gdn's `quest init --hooks` wiring of the `post-commit`
`quest-apply-trailers` hook, alongside the existing pre-commit hooks.
"""

from __future__ import annotations

import subprocess

from questkit.gitutil import git_hooks_dir


def _git_init(repo_root):
    subprocess.run(["git", "init", "-q"], cwd=repo_root, check=True)


def test_hooks_writes_a_post_commit_script_calling_quest_apply_trailers(isolated, run):
    _git_init(isolated)

    result = run("init", "--hooks")

    assert result.code == 0
    hooks_dir = git_hooks_dir(isolated)
    post_commit = hooks_dir / "post-commit"
    assert post_commit.is_file()
    assert "quest-apply-trailers" in post_commit.read_text()


def test_hooks_post_commit_script_is_executable(isolated, run):
    _git_init(isolated)

    run("init", "--hooks")

    post_commit = git_hooks_dir(isolated) / "post-commit"
    assert post_commit.stat().st_mode & 0o111


def test_hooks_is_idempotent_on_a_second_run(isolated, run):
    _git_init(isolated)
    run("init", "--hooks")
    post_commit = git_hooks_dir(isolated) / "post-commit"
    before = post_commit.read_text()

    result = run("init", "--hooks")

    assert result.code == 0
    assert post_commit.read_text() == before
    assert post_commit.read_text().count("quest-apply-trailers") == 1


def test_hooks_appends_to_an_existing_foreign_post_commit_hook(isolated, run):
    _git_init(isolated)
    hooks_dir = git_hooks_dir(isolated)
    hooks_dir.mkdir(parents=True, exist_ok=True)
    post_commit = hooks_dir / "post-commit"
    post_commit.write_text("#!/bin/sh\necho existing-hook\n")
    post_commit.chmod(0o755)

    result = run("init", "--hooks")

    assert result.code == 0
    text = post_commit.read_text()
    assert "existing-hook" in text
    assert "quest-apply-trailers" in text


def test_hooks_without_a_git_repo_skips_the_post_commit_hook(isolated, run):
    result = run("init", "--hooks")

    assert result.code == 0
    assert "not inside a git repo" in result.out
