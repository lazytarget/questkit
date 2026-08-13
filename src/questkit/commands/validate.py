"""`quest validate` — check quests in a log against the schema."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from .. import schema
from ..config import CONFIG_FILENAME, ConfigVersionError, QuestLogConfig, config_exists
from ..discovery import resolve_log
from ..quest import Quest, QuestFileError, find_by_id

_WIKILINK_ID_RE = re.compile(r"\[\[(QST-[0-9a-z]{5})")


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
        errors.extend(_check_references(quest, quests_dir))
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


def _check_references(quest, quests_dir: Path) -> list[schema.ValidationError]:
    """`blocked_by` ids and body wikilinks must resolve within this log.

    Scoped to this one log deliberately -- questkit has no notion of a
    cross-log reference (see QST-whm2e's Log on the Obsidian vault-boundary
    limitation); a reference to another zone's quest can't be checked here
    and shouldn't be a wikilink in the first place.
    """
    errors: list[schema.ValidationError] = []
    own_id = quest.get("id")

    for ref_id in quest.frontmatter.get("blocked_by") or []:
        if find_by_id(quests_dir, ref_id) is None:
            errors.append(
                schema.ValidationError(
                    quest.path, f"blocked_by references '{ref_id}', not found in this log"
                )
            )

    seen: set[str] = set()
    for match in _WIKILINK_ID_RE.finditer(quest.body):
        ref_id = match.group(1)
        if ref_id == own_id or ref_id in seen:
            continue
        seen.add(ref_id)
        if find_by_id(quests_dir, ref_id) is None:
            errors.append(
                schema.ValidationError(
                    quest.path, f"backlink references '{ref_id}', not found in this log"
                )
            )

    return errors
