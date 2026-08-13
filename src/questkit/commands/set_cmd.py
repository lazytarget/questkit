"""`quest set` — update one or more frontmatter fields on a quest."""

from __future__ import annotations

import argparse

from ..config import QuestLogConfig
from ..discovery import resolve_mutation_target
from ..gitutil import auto_commit
from ..quest import Quest
from ..timeutil import today


def run(args: argparse.Namespace) -> int:
    found = resolve_mutation_target(args.id, explicit_in=args.in_dir)
    if found is None:
        print(f"[quest] no quest matching id '{args.id}' found")
        return 1
    quests_dir, path = found

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
