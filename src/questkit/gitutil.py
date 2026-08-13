"""Shared git helpers: locating a repo root and optional auto-commit."""

from __future__ import annotations

import subprocess
from pathlib import Path


def find_git_root(start: Path) -> Path | None:
    current = start.resolve()
    while True:
        if (current / ".git").exists():
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent


def auto_commit(quests_dir: Path, path: Path, message: str) -> None:
    git_root = find_git_root(quests_dir)
    if git_root is None:
        print(f"[quest] git: auto is set but {quests_dir} is not inside a git repo, skipping commit")
        return
    rel = path.relative_to(git_root)
    try:
        subprocess.run(["git", "add", "--", str(rel)], cwd=git_root, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", message, "--", str(rel)],
            cwd=git_root,
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode(errors="replace").strip() if exc.stderr else str(exc)
        print(f"[quest] auto-commit skipped: {stderr}")
