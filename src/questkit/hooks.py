"""Entry points invoked by pre-commit: `quest-format`, `quest-validate`, `quest-bump-modified`."""

from __future__ import annotations

import sys
from pathlib import Path

from . import schema
from .config import ConfigVersionError, QuestLogConfig
from .quest import Quest, QuestFileError
from .timeutil import today


def _schema_for(path: Path) -> schema.SchemaConfig:
    """Best-effort: the schema for the log a staged quest file lives in.

    A quest file always sits directly in its log directory (flat structure,
    no active/archive subdirs), so `path.parent` is that log's `quests/` dir.
    Falls back to the built-in defaults if it has no `.questkit.yaml` (or
    that config can't be read) -- the hook should still validate something
    sensible rather than crash on a stray input.
    """
    try:
        return QuestLogConfig.load(path.parent).schema
    except (OSError, ConfigVersionError, schema.SchemaExtendsError):
        return schema.SchemaConfig.default()


def format_main(argv: list[str] | None = None) -> int:
    """Pre-commit hook entry point: normalize each staged quest file's frontmatter formatting.

    Pure re-save, no field-value changes -- runs first, before `quest-validate`/
    `quest-bump-modified`, so those see already-normalized content (matching
    Obsidian's own frontmatter writer -- see `quest.py`'s `_normalize_*`
    functions) instead of re-litigating array/quote style on every commit.
    """
    paths = argv if argv is not None else sys.argv[1:]
    for raw_path in paths:
        path = Path(raw_path)
        try:
            before = path.read_text(encoding="utf-8")
            quest = Quest.load(path)
        except (OSError, QuestFileError) as exc:
            print(f"[!] {exc}")
            continue
        quest.save()
        after = path.read_text(encoding="utf-8")
        if after != before:
            print(f"[quest-format] {path}: reformatted")
    return 0


def validate_main(argv: list[str] | None = None) -> int:
    """Pre-commit hook entry point: validate each staged quest file path in argv."""
    paths = argv if argv is not None else sys.argv[1:]
    total_errors = 0
    for raw_path in paths:
        path = Path(raw_path)
        try:
            quest = Quest.load(path)
        except QuestFileError as exc:
            print(f"[!] {exc}")
            total_errors += 1
            continue
        errors = schema.validate_quest(quest, _schema_for(path))
        for error in errors:
            print(f"[!] {error}")
        total_errors += len(errors)
    return 1 if total_errors else 0


def bump_modified_main(argv: list[str] | None = None) -> int:
    """Pre-commit hook entry point: bump `modified` on each staged quest file to today."""
    paths = argv if argv is not None else sys.argv[1:]
    today_str = today()
    for raw_path in paths:
        path = Path(raw_path)
        try:
            quest = Quest.load(path)
        except QuestFileError as exc:
            print(f"[!] {exc}")
            continue
        # str()-compare: `modified` normalizes to a real `date` object on save
        # (see quest._normalize_date_fields), so a straight `!=` against the
        # plain ISO string here would always be true and rewrite -- and
        # re-save -- every staged file on every commit, changed or not.
        if str(quest.frontmatter.get("modified")) != today_str:
            quest.frontmatter["modified"] = today_str
            quest.save()
    return 0


if __name__ == "__main__":
    sys.exit(validate_main())
