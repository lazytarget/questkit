"""`quest new` — capture a new quest."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

from ruamel.yaml.comments import CommentedMap

from .. import schema
from ..config import QuestLogConfig
from ..discovery import resolve_log
from ..gitutil import auto_commit
from ..ids import generate_id
from ..quest import Quest
from ..template import render_body
from ..timeutil import today
from ..utils import slugify


def run(args: argparse.Namespace) -> int:
    quests_dir = resolve_log(explicit=args.in_dir)
    config = QuestLogConfig.load(quests_dir)

    quest_id = generate_id(quests_dir, prefix=config.prefix, length=config.id_length)
    filename = f"{quest_id}--{slugify(args.title)}.md"
    path = quests_dir / filename

    created = today()
    status = args.status or config.defaults.get("status", schema.DEFAULT_STATUS)

    frontmatter = CommentedMap()
    frontmatter["id"] = quest_id
    frontmatter["title"] = args.title
    if status != "draft":
        frontmatter["description"] = args.description or args.title
    frontmatter["created"] = created
    frontmatter["modified"] = created
    frontmatter["type"] = args.type or config.defaults.get("type", schema.DEFAULT_TYPE)
    if args.tier:
        frontmatter["tier"] = args.tier
    frontmatter["status"] = status
    frontmatter["priority"] = args.priority or config.defaults.get("priority", schema.DEFAULT_PRIORITY)
    project = args.project or config.project
    if project:
        frontmatter["project"] = project
    frontmatter["tags"] = list(args.tags or [])
    frontmatter["aliases"] = [quest_id]

    quest = Quest(path=path, frontmatter=frontmatter, body=render_body(created))
    quest.save()
    print(str(path))

    if config.git == "auto":
        auto_commit(quests_dir, path, f"quest({quests_dir.name}): new {quest_id} {args.title}")

    if args.edit:
        _open_editor(path)

    return 0


def _open_editor(path: Path) -> None:
    editor = os.environ.get("EDITOR")
    if not editor:
        print("[quest] $EDITOR is not set; skipping --edit")
        return
    subprocess.run([editor, str(path)])
