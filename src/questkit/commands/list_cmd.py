"""`quest list` — list quests in a log, filterable by status/type/tag."""

from __future__ import annotations

import argparse

from ..config import QuestLogConfig
from ..discovery import resolve_log
from ..quest import Quest

DEFAULT_STATUSES = ("todo", "in-progress", "blocked")


def run(args: argparse.Namespace) -> int:
    quests_dir = resolve_log(explicit=args.in_dir)
    config = QuestLogConfig.load(quests_dir)
    statuses = _split_csv(args.status) or list(DEFAULT_STATUSES)
    types = _split_csv(args.type)
    tags = _split_csv(args.tag)

    rows = []
    for path in sorted(quests_dir.glob(config.pattern)):
        quest = Quest.load(path)
        fm = quest.frontmatter
        if statuses and fm.get("status") not in statuses:
            continue
        if types and fm.get("type") not in types:
            continue
        if tags and not (set(fm.get("tags") or []) & set(tags)):
            continue
        rows.append(quest)

    if not rows:
        print("(no matching quests)")
        return 0

    id_width = max(len(q.get("id", "")) for q in rows)
    for quest in rows:
        fm = quest.frontmatter
        print(
            f"{fm.get('id', ''):<{id_width}}  "
            f"{fm.get('status', ''):<12} "
            f"{fm.get('priority', ''):<9} "
            f"{fm.get('title', '')}"
        )
    return 0


def _split_csv(value):
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]
