"""`quest mv` — move a quest to a different quest log."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from .. import gitutil
from ..config import QuestLogConfig
from ..discovery import resolve_log, resolve_mutation_target
from ..quest import Quest
from ..timeutil import today


def run(args: argparse.Namespace) -> int:
    found = resolve_mutation_target(args.id, explicit_in=args.in_dir)
    if found is None:
        print(f"[quest mv] no quest matching id '{args.id}' found")
        return 1
    src_dir, src_path = found

    dest_dir = resolve_log(explicit=args.dest)
    if dest_dir == src_dir:
        print(f"[quest mv] '{args.id}' is already in {dest_dir}")
        return 1

    dest_path = dest_dir / src_path.name
    if dest_path.exists():
        print(f"[quest mv] {dest_path} already exists, aborting")
        return 1

    src_config = QuestLogConfig.load(src_dir)
    dest_config = QuestLogConfig.load(dest_dir)
    src_root = gitutil.find_git_root(src_dir)
    dest_root = gitutil.find_git_root(dest_dir)
    same_repo = src_root is not None and src_root == dest_root

    _move_file(src_path, dest_path, src_root, dest_root, same_repo)

    quest = Quest.load(dest_path)
    old_project = quest.get("project")
    if dest_config.project and dest_config.project != old_project:
        quest.frontmatter["project"] = dest_config.project
        print(f"[quest mv] project: '{old_project or '(unset)'}' -> '{dest_config.project}'")
    elif not dest_config.project and old_project:
        print(
            f"[quest mv] {dest_dir} declares no project; left project='{old_project}' "
            "as-is -- update by hand if that's now stale"
        )
    quest.frontmatter["modified"] = today()
    quest.save()
    print(f"[quest mv] {src_path} -> {dest_path}")

    _commit(quest.get("id"), src_dir, dest_dir, src_path, dest_path, src_config, dest_config, same_repo)

    print("[quest mv] run 'quest validate' to catch any custom-field drift or now-broken hyperlinks/paths")
    return 0


def _move_file(src_path: Path, dest_path: Path, src_root, dest_root, same_repo: bool) -> None:
    if same_repo and gitutil.git_mv(src_root, src_path, dest_path):
        return
    shutil.move(str(src_path), str(dest_path))
    if src_root is not None:
        gitutil.stage(src_root, src_path)
    if dest_root is not None:
        gitutil.stage(dest_root, dest_path)


def _commit(quest_id, src_dir, dest_dir, src_path, dest_path, src_config, dest_config, same_repo) -> None:
    dest_root = gitutil.find_git_root(dest_dir)
    src_root = gitutil.find_git_root(src_dir)

    if same_repo:
        if dest_config.git == "auto":
            gitutil.auto_commit(
                dest_dir, [src_path, dest_path], f"quest({dest_dir.name}): move {quest_id} from {src_dir.name}"
            )
        elif dest_root is not None:
            gitutil.stage(dest_root, dest_path)  # keep the field edit staged alongside the already-staged rename
        return

    if dest_root is not None:
        if dest_config.git == "auto":
            gitutil.auto_commit(dest_dir, dest_path, f"quest({dest_dir.name}): adopt {quest_id} from {src_dir}")
        else:
            gitutil.stage(dest_root, dest_path)  # re-stage the frontmatter edit made after the initial add

    if src_root is not None and src_config.git == "auto":
        gitutil.auto_commit(src_dir, src_path, f"quest({src_dir.name}): move {quest_id} to {dest_dir}")
