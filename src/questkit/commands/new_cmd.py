"""`quest new` — capture a new quest, one at a time or as a YAML batch."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

from .. import macros, schema
from ..config import QuestLogConfig
from ..discovery import resolve_log_for_new
from ..gitutil import auto_commit
from ..ids import generate_id
from ..quest import Quest
from ..templates import render_body
from ..timeutil import today
from ..utils import slugify

# Shorthand flags for fields every schema has. Custom fields go through
# `--set`, because argparse is built before the log is resolved and therefore
# cannot grow a flag per declared field.
_SHORTHAND_FLAGS = ("type", "tier", "status", "priority", "description", "project")

_yaml = YAML(typ="safe")


@dataclass
class _NewSpec:
    """Everything one `quest new` invocation states, whether from CLI flags
    or one entry of a `--batch -` YAML list -- one shape, two sources."""

    title: str
    type: str | None = None
    tier: str | None = None
    status: str | None = None
    priority: str | None = None
    project: str | None = None
    description: str | None = None
    tags: list = field(default_factory=list)
    sets: list = field(default_factory=list)
    body: str | None = None


def run(args: argparse.Namespace) -> int:
    quests_dir = resolve_log_for_new(explicit=args.in_dir)
    config = QuestLogConfig.load(quests_dir)

    if getattr(args, "batch", None):
        if args.title is not None:
            print(
                "[quest] error: --batch takes no positional title -- put each "
                "quest's title inside its own batch entry",
                file=sys.stderr,
            )
            return 1
        return _run_batch(quests_dir, config, args)

    if args.title is None:
        print("[quest] error: a title is required (or use --batch -)", file=sys.stderr)
        return 1

    try:
        body = _read_body(args.body)
    except ValueError as exc:
        print(f"[quest] error: {exc}", file=sys.stderr)
        return 1

    spec = _NewSpec(
        title=args.title,
        type=args.type,
        tier=args.tier,
        status=args.status,
        priority=args.priority,
        project=args.project,
        description=args.description,
        tags=list(args.tags or []),
        sets=list(args.sets or []),
        body=body,
    )
    path = _create_quest(quests_dir, config, spec)
    if path is None:
        return 1
    print(str(path))

    if config.git == "auto":
        auto_commit(quests_dir, path, f"quest({quests_dir.name}): new {path.stem.partition('--')[0]} {args.title}")

    if args.edit:
        _open_editor(path)

    return 0


def _run_batch(quests_dir: Path, config: QuestLogConfig, args: argparse.Namespace) -> int:
    if args.batch != "-":
        print("[quest] error: --batch only supports '-' (read a YAML list from stdin)", file=sys.stderr)
        return 1

    try:
        entries = _yaml.load(sys.stdin.read()) or []
    except Exception as exc:  # ruamel's YAML errors are not one exception type
        print(f"[quest] error: --batch stdin is not valid YAML: {exc}", file=sys.stderr)
        return 1
    if not isinstance(entries, list):
        print("[quest] error: --batch stdin must be a YAML list of quest entries", file=sys.stderr)
        return 1

    paths: list[Path] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or "title" not in entry:
            print(f"[quest] error: batch entry {index} needs at least a 'title'", file=sys.stderr)
            return 1
        spec = _NewSpec(
            title=str(entry["title"]),
            type=entry.get("type"),
            tier=entry.get("tier"),
            status=entry.get("status"),
            priority=entry.get("priority"),
            project=entry.get("project"),
            description=entry.get("description"),
            tags=list(entry.get("tags") or []),
            sets=[f"{k}={v}" for k, v in (entry.get("set") or {}).items()],
            body=entry.get("body"),
        )
        path = _create_quest(quests_dir, config, spec)
        if path is None:
            return 1
        paths.append(path)

    for path in paths:
        print(path.stem.partition("--")[0])
        if config.git == "auto":
            auto_commit(quests_dir, path, f"quest({quests_dir.name}): new {path.stem.partition('--')[0]}")
    return 0


def _read_body(value: str | None) -> str | None:
    if value is None:
        return None
    if value == "-":
        return sys.stdin.read()
    return value


def _create_quest(quests_dir: Path, config: QuestLogConfig, spec: _NewSpec) -> Path | None:
    """Everything from id generation through save. Returns the new path, or
    `None` (having already printed why) on a strict-mode rejection."""
    quest_id = generate_id(quests_dir, prefix=config.prefix, length=config.id_length)
    filename = f"{quest_id}--{slugify(spec.title)}.md"
    path = quests_dir / filename

    created = today()
    defaults = config.schema.resolved_defaults(config.defaults)
    if config.project:
        defaults.setdefault("project", config.project)

    explicit = _explicit_assignments(spec)
    undeclared = _undeclared_set_names(spec, config.schema)
    if undeclared:
        valid = ", ".join(sorted(config.schema.declared_field_names))
        message = (
            f"--set names undeclared field(s) {sorted(undeclared)}; declared fields: {valid}"
        )
        if config.schema.strict:
            print(f"[quest] error: {message}", file=sys.stderr)
            return None
        print(f"[quest] warning: {message}", file=sys.stderr)

    status = explicit.get("status") or defaults.get("status") or schema.DEFAULT_STATUS

    frontmatter = CommentedMap()
    frontmatter["id"] = quest_id
    frontmatter["title"] = spec.title
    if status != "draft":
        frontmatter["description"] = explicit.get("description") or spec.title
    frontmatter["created"] = created
    frontmatter["modified"] = created
    frontmatter["status"] = status
    frontmatter["tags"] = list(spec.tags)
    frontmatter["blocked_by"] = []
    frontmatter["aliases"] = [quest_id]

    body = spec.body if spec.body is not None else render_body(created, quests_dir / "_template.md")
    quest = Quest(path=path, frontmatter=frontmatter, body=body)

    # One evaluation point for macros: after id generation, before first save.
    # `{{ id }}` and `{{ slug }}` are therefore always available and there are
    # no ordering surprises about which defaults can see which.
    context = macros.context_for(quest, config, path)
    try:
        _apply_defaults(quest, defaults, explicit, context, status)
    except macros.UnknownMacroError as exc:
        print(f"[quest] error: {exc}", file=sys.stderr)
        return None

    _warn_uninitialized(quest, config, quest_id)
    quest.reorder(config.schema)
    quest.save()
    return path


def _undeclared_set_names(spec: _NewSpec, schema_config) -> set[str]:
    """Which `--set` names (not shorthand flags) the schema does not know about.

    Only `--set` is checked -- the shorthand flags (`--type`/`--status`/etc.)
    always name core fields, so there is nothing for strict mode to catch
    there. Under `strict: true` this is a hard error naming the valid fields;
    under `strict: false` it is a warning, because a field that appears in no
    filter, fails no validation, and is only ever found by grep months later
    is exactly the failure mode `strict` exists to make loud.
    """
    names = set()
    for assignment in spec.sets:
        key, _, _ = assignment.partition("=")
        names.add(key.strip())
    return names - schema_config.declared_field_names


def _explicit_assignments(spec: _NewSpec) -> dict:
    """Everything the caller stated outright, shorthand flags and `--set` alike.

    Merged into one map so precedence is stated once -- `--flag` >
    `fields.<n>.default` > `defaults.<n>` > built-in -- rather than
    re-derived per field.
    """
    explicit: dict = {}
    for name in _SHORTHAND_FLAGS:
        value = getattr(spec, name, None)
        if value is not None:
            explicit[name] = value
    for assignment in spec.sets:
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
