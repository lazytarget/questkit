"""`quest set` — update one or more frontmatter fields on a quest."""

from __future__ import annotations

import argparse

from ..config import QuestLogConfig
from ..discovery import resolve_log
from ..gitutil import auto_commit
from ..quest import Quest, find_by_id
from ..timeutil import today


def run(args: argparse.Namespace) -> int:
    quests_dir = resolve_log(explicit=args.in_dir)
    path = find_by_id(quests_dir, args.id)
    if path is None:
        print(f"[quest] no quest matching id '{args.id}' found in {quests_dir}")
        return 1

    quest = Quest.load(path)
    for assignment in args.assignments:
        if "=" not in assignment:
            print(f"[quest] ignoring malformed assignment '{assignment}' (expected field=value)")
            continue
        key, _, value = assignment.partition("=")
        quest.frontmatter[key.strip()] = _coerce(key.strip(), value.strip())

    quest.frontmatter["modified"] = today()
    quest.save()
    print(str(path))

    config = QuestLogConfig.load(quests_dir)
    if config.git == "auto":
        auto_commit(quests_dir, path, f"quest({quests_dir.name}): update {quest.get('id')}")

    return 0


def _coerce(key, value):
    if key == "tags":
        return [v.strip() for v in value.split(",") if v.strip()]
    return value
