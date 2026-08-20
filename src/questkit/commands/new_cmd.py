"""`quest new` — capture a new quest."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from ruamel.yaml.comments import CommentedMap

from .. import macros, schema
from ..config import QuestLogConfig
from ..discovery import resolve_log_for_new
from ..gitutil import auto_commit
from ..ids import generate_id
from ..quest import Quest
from ..template import render_body
from ..timeutil import today
from ..utils import slugify

# Shorthand flags for fields every schema has. Custom fields go through
# `--set`, because argparse is built before the log is resolved and therefore
# cannot grow a flag per declared field.
_SHORTHAND_FLAGS = ("type", "tier", "status", "priority", "description", "project")


def run(args: argparse.Namespace) -> int:
    quests_dir = resolve_log_for_new(explicit=args.in_dir)
    config = QuestLogConfig.load(quests_dir)

    quest_id = generate_id(quests_dir, prefix=config.prefix, length=config.id_length)
    filename = f"{quest_id}--{slugify(args.title)}.md"
    path = quests_dir / filename

    created = today()
    defaults = config.schema.resolved_defaults(config.defaults)
    # The log's `project:` is the default value for the `project` field --
    # `project` is identity (unique per log), so a log that declares one stamps
    # every quest captured in it. Lowest precedence of the defaults, since a
    # schema or `defaults:` naming `project` explicitly is a deliberate override.
    if config.project:
        defaults.setdefault("project", config.project)
    explicit = _explicit_assignments(args)
    status = explicit.get("status") or defaults.get("status") or schema.DEFAULT_STATUS

    frontmatter = CommentedMap()
    frontmatter["id"] = quest_id
    frontmatter["title"] = args.title
    if status != "draft":
        frontmatter["description"] = explicit.get("description") or args.title
    frontmatter["created"] = created
    frontmatter["modified"] = created
    frontmatter["status"] = status
    frontmatter["tags"] = list(args.tags or [])
    frontmatter["blocked_by"] = []
    frontmatter["aliases"] = [quest_id]

    quest = Quest(path=path, frontmatter=frontmatter, body=render_body(created))

    # One evaluation point for macros: after id generation, before first save.
    # `{{ id }}` and `{{ slug }}` are therefore always available and there are
    # no ordering surprises about which defaults can see which.
    context = macros.context_for(quest, config, path)
    try:
        _apply_defaults(quest, defaults, explicit, context, status)
    except macros.UnknownMacroError as exc:
        print(f"[quest] error: {exc}", file=sys.stderr)
        return 1

    _warn_uninitialized(quest, config, quest_id)
    quest.reorder(config.schema)
    quest.save()
    print(str(path))

    if config.git == "auto":
        auto_commit(quests_dir, path, f"quest({quests_dir.name}): new {quest_id} {args.title}")

    if args.edit:
        _open_editor(path)

    return 0


def _explicit_assignments(args: argparse.Namespace) -> dict:
    """Everything the caller stated outright, shorthand flags and `--set` alike.

    Merged into one map so precedence is stated once -- `--flag` >
    `fields.<n>.default` > `defaults.<n>` > built-in -- rather than
    re-derived per field.
    """
    explicit: dict = {}
    for name in _SHORTHAND_FLAGS:
        value = getattr(args, name, None)
        if value is not None:
            explicit[name] = value
    for assignment in getattr(args, "sets", None) or []:
        if "=" not in assignment:
            raise ValueError(f"malformed --set '{assignment}' (expected field=value)")
        key, _, value = assignment.partition("=")
        explicit[key.strip()] = value.strip()
    return explicit


def _apply_defaults(quest: Quest, defaults: dict, explicit: dict, context: dict, status: str) -> None:
    for name, raw in defaults.items():
        if name in ("status", "description"):
            continue  # already resolved above; description is status-dependent
        if name in explicit:
            continue
        value = macros.expand(str(raw), context) if macros.has_macro(str(raw)) else raw
        quest.set(name, value)
    for name, value in explicit.items():
        if name in ("status", "description"):
            continue
        quest.set(name, value)
    if status == "draft" and "description" in explicit:
        quest.set("description", explicit["description"])


def _warn_uninitialized(quest: Quest, config: QuestLogConfig, quest_id: str) -> None:
    """Name every declared custom field the new quest has no value for.

    Stays a warning rather than an error: a log declaring a field is saying
    "quests here should carry this", not "refuse to capture without it".
    `required: true` is the way to say the stronger thing, and `quest validate`
    enforces it.
    """
    for field_name in sorted(config.schema.fields):
        if quest.get(field_name) is None:
            quest.frontmatter[field_name] = None
            print(
                f"[warning] custom field '{field_name}' is uninitialized "
                f"(set with 'quest set {quest_id} {field_name}=...')",
                file=sys.stderr,
            )


def _open_editor(path: Path) -> None:
    editor = os.environ.get("EDITOR")
    if not editor:
        print("[quest] $EDITOR is not set; skipping --edit")
        return
    subprocess.run([editor, str(path)])
