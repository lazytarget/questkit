"""`quest validate` — check quests in a log against the schema."""

from __future__ import annotations

import argparse

from .. import schema
from ..config import CONFIG_FILENAME, ConfigVersionError, QuestLogConfig, config_exists
from ..discovery import resolve_log
from ..quest import Quest, QuestFileError


def run(args: argparse.Namespace) -> int:
    quests_dir = resolve_log(explicit=args.in_dir)
    if not config_exists(quests_dir):
        print(f"[quest validate] {quests_dir}: no {CONFIG_FILENAME} found")
        return 1

    try:
        config = QuestLogConfig.load(quests_dir)
    except ConfigVersionError as exc:
        print(f"[quest validate] {exc}")
        return 1

    checked = 0
    total_errors = 0
    for path in sorted(quests_dir.glob(config.pattern)):
        checked += 1
        try:
            quest = Quest.load(path)
        except QuestFileError as exc:
            print(f"[!] {exc}")
            total_errors += 1
            continue

        errors = schema.validate_quest(quest)
        errors.extend(_project_drift(quest, config))
        if errors:
            print(f"[!] {path}")
            for error in errors:
                print(f"      error: {error.message}")
            total_errors += len(errors)

    if total_errors == 0:
        print(f"[quest validate] {checked} quest(s) checked, no errors")
        return 0

    print(f"[quest validate] {checked} quest(s) checked, {total_errors} error(s)")
    return 1


def _project_drift(quest, config: QuestLogConfig) -> list[schema.ValidationError]:
    if not config.project:
        return []
    quest_project = quest.get("project")
    if quest_project and quest_project != config.project:
        return [
            schema.ValidationError(
                quest.path,
                f"project '{quest_project}' disagrees with this log's declared project "
                f"'{config.project}' (drift)",
            )
        ]
    return []
