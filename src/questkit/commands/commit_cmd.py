"""`quest commit [--in LOG ...] [--no-verify] [--push]` — the commit convention,
in the app instead of duplicated across a systemd unit, a Home Assistant
`shell_command`, and fingers.

Stages and commits exactly the log's `tracked:` pathspec via `git commit --
<pathspec>`, which ignores the index -- so it cannot sweep in a user's
staged, unrelated code changes even if `git add -A` already ran. The message
is derived deterministically from the frontmatter diff; there is no model in
this path.
"""

from __future__ import annotations

import argparse
import contextlib
import fnmatch
import subprocess
import sys
from pathlib import Path

from ..config import QuestLogConfig
from ..discovery import resolve_log_set
from ..gitutil import find_git_root
from ..quest import Quest, QuestFileError


def run(args: argparse.Namespace) -> int:
    logs = resolve_log_set(in_dirs=args.in_dirs, all_logs=args.all_logs, root=args.root)
    exit_code = 0
    for quests_dir in logs:
        config = QuestLogConfig.load(quests_dir)
        if commit_one(quests_dir, config, no_verify=args.no_verify, push=args.push) != 0:
            exit_code = 1
    return exit_code


def commit_one(
    quests_dir: Path, config: QuestLogConfig, *, no_verify: bool = False, push: bool = False
) -> int:
    git_root = find_git_root(quests_dir)
    if git_root is None:
        print(f"[quest commit] {quests_dir} is not inside a git repo, skipping", file=sys.stderr)
        return 0

    quests_rel = quests_dir.relative_to(git_root)
    # A literal (non-glob) pathspec that matches nothing at all -- e.g. no
    # `_template.md` yet -- is a hard `git commit` error, unlike `git add`.
    # A glob always resolves fine with zero matches, so only literals need
    # the existence check.
    pathspecs = [
        str(quests_rel / entry)
        for entry in config.resolved_tracked()
        if any(c in entry for c in "*?[") or (quests_dir / entry).exists()
    ]

    changed = _changed_paths(git_root, pathspecs)
    if not changed:
        print(f"[quest commit] {quests_dir}: nothing to commit")
        return 0

    message = _build_message(git_root, quests_dir, config, changed)

    # A pathspec matching nothing (e.g. no `_template.md` yet) is not fatal here.
    with contextlib.suppress(subprocess.CalledProcessError):
        _run(["git", "add", "--", *pathspecs], git_root)

    commit_args = ["git", "commit", "-m", message]
    if no_verify:
        commit_args.append("--no-verify")
    commit_args += ["--", *pathspecs]
    try:
        _run(commit_args, git_root)
    except subprocess.CalledProcessError as exc:
        output = (exc.stdout or b"").decode(errors="replace") + (exc.stderr or b"").decode(errors="replace")
        print(f"[quest commit] {quests_dir}: commit failed\n{output}", file=sys.stderr)
        return 1

    project = config.project or quests_dir.name
    print(f"[quest commit] {quests_dir}: committed ({project})")

    if push:
        try:
            _run(["git", "push"], git_root)
        except subprocess.CalledProcessError as exc:
            output = (exc.stdout or b"").decode(errors="replace") + (exc.stderr or b"").decode(errors="replace")
            print(f"[quest commit] {quests_dir}: push failed\n{output}", file=sys.stderr)
            return 1
    return 0


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True)


def _changed_paths(git_root: Path, pathspecs: list[str]) -> list[tuple[str, str]]:
    """`(status_code, relpath)` for every path in the pathspec with a real
    change -- staged, unstaged or untracked alike."""
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all", "--", *pathspecs],
        cwd=git_root,
        capture_output=True,
    )
    changed = []
    for line in result.stdout.decode(errors="replace").splitlines():
        if not line:
            continue
        code, _, relpath = line[:2], line[2:3], line[3:]
        changed.append((code.strip() or "??", relpath))
    return changed


def _build_message(
    git_root: Path, quests_dir: Path, config: QuestLogConfig, changed: list[tuple[str, str]]
) -> str:
    project = config.project or quests_dir.name
    added: list[str] = []
    updated: list[str] = []
    removed: list[str] = []

    for code, relpath in changed:
        path = git_root / relpath
        if not _looks_like_a_quest(config, path):
            continue
        if code in ("??", "A"):
            title = _read_field(path, "title") or path.name
            quest_id = _read_field(path, "id") or path.stem.partition("--")[0]
            added.append(f"+ {quest_id}  {title}")
        elif code == "D":
            quest_id = path.stem.partition("--")[0]
            removed.append(f"- {quest_id}  removed")
        else:
            quest_id = _read_field(path, "id") or path.stem.partition("--")[0]
            old_status = _read_head_field(git_root, relpath, "status")
            new_status = _read_field(path, "status")
            if old_status is not None and new_status is not None and old_status != new_status:
                updated.append(f"~ {quest_id}  status: {old_status} → {new_status}")
            else:
                updated.append(f"~ {quest_id}  updated")

    parts = []
    if added:
        parts.append(f"add {len(added)}")
    if updated:
        parts.append(f"update {len(updated)}")
    if removed:
        parts.append(f"remove {len(removed)}")
    header = f"quest({project}): " + (", ".join(parts) if parts else "update config")

    body_lines = added + updated + removed
    if not body_lines:
        return header
    return header + "\n\n" + "\n".join(body_lines)


def _looks_like_a_quest(config: QuestLogConfig, path: Path) -> bool:
    return fnmatch.fnmatch(path.name, config.pattern)


def _read_field(path: Path, name: str):
    if not path.is_file():
        return None
    try:
        return Quest.load(path).get(name)
    except QuestFileError:
        return None


def _read_head_field(git_root: Path, relpath: str, name: str):
    result = subprocess.run(
        ["git", "show", f"HEAD:{relpath}"], cwd=git_root, capture_output=True
    )
    if result.returncode != 0:
        return None
    try:
        historical = Quest.from_text(git_root / relpath, result.stdout.decode(errors="replace"))
    except QuestFileError:
        return None
    return historical.get(name)
