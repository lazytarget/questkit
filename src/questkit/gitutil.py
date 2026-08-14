"""Shared git helpers: locating a repo root, staging, and optional auto-commit."""

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


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True)


def git_mv(repo_root: Path, src: Path, dest: Path) -> bool:
    """`git mv` src -> dest (both absolute, inside repo_root). Returns success.

    Fails (returning False rather than raising) when e.g. `src` isn't tracked
    yet -- a quest created but never committed in a `git: manual` log. The
    caller falls back to a plain filesystem move in that case.
    """
    try:
        _run(["git", "mv", "--", str(src.relative_to(repo_root)), str(dest.relative_to(repo_root))], repo_root)
        return True
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode(errors="replace").strip() if exc.stderr else str(exc)
        print(f"[quest] git mv failed, falling back to a plain move: {stderr}")
        return False


def stage(repo_root: Path, path: Path) -> None:
    """`git add` a single path (also correctly stages an already-removed path as a deletion)."""
    rel = path.relative_to(repo_root)
    try:
        _run(["git", "add", "--", str(rel)], repo_root)
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode(errors="replace").strip() if exc.stderr else str(exc)
        print(f"[quest] git add {rel} failed: {stderr}")


def auto_commit(quests_dir: Path, paths: Path | list[Path], message: str) -> None:
    """Stage and commit one or more paths, restricted to those paths only.

    Multiple paths matter for a same-repo `quest mv`: the old path (a
    deletion) and the new path (the moved-and-possibly-edited file) must be
    committed together, or a pathspec-restricted commit silently leaves the
    old path's deletion staged but uncommitted.
    """
    git_root = find_git_root(quests_dir)
    if git_root is None:
        print(f"[quest] git: auto is set but {quests_dir} is not inside a git repo, skipping commit")
        return
    path_list = [paths] if isinstance(paths, Path) else list(paths)
    rels = [str(p.relative_to(git_root)) for p in path_list]
    # A path already gone from the working tree (e.g. the old side of a `git
    # mv` that already ran, or a prior `stage()` call) can't be re-added --
    # `git add` on a pathspec with nothing to match errors out. Its removal
    # is already staged, so it only needs to appear in the commit pathspec.
    existing_rels = [str(p.relative_to(git_root)) for p in path_list if p.exists()]
    try:
        if existing_rels:
            _run(["git", "add", "--", *existing_rels], git_root)
        _run(["git", "commit", "-m", message, "--", *rels], git_root)
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode(errors="replace").strip() if exc.stderr else str(exc)
        print(f"[quest] auto-commit skipped: {stderr}")
