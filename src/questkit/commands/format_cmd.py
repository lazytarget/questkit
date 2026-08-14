"""`quest format` — reformat every quest in a log to the current normalization rules."""

from __future__ import annotations

import argparse

from ..config import CONFIG_FILENAME, ConfigVersionError, QuestLogConfig, config_exists
from ..discovery import resolve_log
from ..quest import Quest, QuestFileError


def run(args: argparse.Namespace) -> int:
    quests_dir = resolve_log(explicit=args.in_dir)
    if not config_exists(quests_dir):
        print(f"[quest format] {quests_dir}: no {CONFIG_FILENAME} found")
        return 1

    try:
        config = QuestLogConfig.load(quests_dir)
    except ConfigVersionError as exc:
        print(f"[quest format] {exc}")
        return 1

    checked = 0
    changed = 0
    for path in sorted(quests_dir.glob(config.pattern)):
        checked += 1
        try:
            before = path.read_text(encoding="utf-8")
            quest = Quest.load(path)
        except QuestFileError as exc:
            print(f"[!] {exc}")
            continue

        quest.save()
        after = path.read_text(encoding="utf-8")
        if after != before:
            changed += 1
            print(f"[quest format] {path}: reformatted")

    print(f"[quest format] {checked} quest(s) checked, {changed} reformatted")
    return 0
