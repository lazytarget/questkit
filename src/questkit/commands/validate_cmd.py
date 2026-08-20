"""`quest validate` — check quests in a log against the schema."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from .. import schema
from ..config import CONFIG_FILENAME, ConfigVersionError, QuestLogConfig, config_exists
from ..discovery import resolve_log
from ..quest import Quest, QuestFileError, find_by_id

_WIKILINK_ID_RE = re.compile(r"\[\[(QST-[0-9a-z]{5})")
_FENCED_CODE_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")


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

    _warn_validation_theater(config)

    checked = 0
    total_errors = 0
    total_notes = 0
    for path in sorted(quests_dir.glob(config.pattern)):
        checked += 1
        try:
            quest = Quest.load(path)
        except QuestFileError as exc:
            print(f"[!] {exc}")
            total_errors += 1
            continue

        errors = schema.validate_quest(quest, config.schema)
        errors.extend(_project_drift(quest, config))
        errors.extend(_check_references(quest, quests_dir))
        # Notes are a separate channel, not a severity flag on an error: they
        # never count toward the exit code, so anything routed here is
        # something a commit must not be blocked on. Slug drift is the first
        # such check; project-drift heuristics and orphan detection are the
        # obvious next ones.
        notes = schema.check_slug_drift(quest)

        total_errors += len(errors)
        total_notes += len(notes)

        shown = errors + (notes if args.notes else [])
        if shown:
            print(f"[!] {path}")
            for error in errors:
                print(f"      error: {error.message}")
            if args.notes:
                for note in notes:
                    print(f"      note: {note.message}")

    print(f"[quest validate] {_summary(checked, total_errors, total_notes)}")
    return 1 if total_errors else 0


def _warn_validation_theater(config: QuestLogConfig) -> None:
    """Flag `required: true` paired with a *static* default.

    A mandatory field that always gets the same value is a field nobody ever
    thinks about -- the check can never fail, so it enforces nothing. It stays
    legal rather than becoming an error, because a *computed* default that
    genuinely varies (`{{ env.USER }}` on `owner`) carries real information,
    and the config cannot tell the author's intent apart from the outside.
    """
    for name, spec in sorted(config.schema.fields.items()):
        if spec.required and spec.has_static_default:
            print(
                f"[quest validate] warning: field '{name}' is required with the static "
                f"default '{spec.default}', so the requirement can never fail -- "
                "validation theater. Use a macro default, or drop `required`.",
                file=sys.stderr,
            )


def _summary(checked: int, errors: int, notes: int) -> str:
    """Report both counts, so a clean-but-noted log does not read as failing.

    The old summary said "N error(s)" and nothing else, so a log with one
    drifted filename and no real problem looked broken.
    """
    if not errors and not notes:
        return f"{checked} quest(s) checked, no errors"
    return f"{checked} quest(s) checked, {errors} error(s), {notes} note(s)"


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

    # Code spans/blocks are illustrative, not live links -- e.g. a doc
    # showing `` [[QST-x7k2m]] `` as a syntax example, not a real reference.
    prose = _INLINE_CODE_RE.sub("", _FENCED_CODE_RE.sub("", quest.body))

    seen: set[str] = set()
    for match in _WIKILINK_ID_RE.finditer(prose):
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
