"""Entry points invoked by pre-commit: `quest-validate` and `quest-bump-modified`."""

from __future__ import annotations

import sys
from pathlib import Path

from . import schema
from .quest import Quest, QuestFileError
from .timeutil import today


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
        errors = schema.validate_quest(quest)
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
        if quest.frontmatter.get("modified") != today_str:
            quest.frontmatter["modified"] = today_str
            quest.save()
    return 0


if __name__ == "__main__":
    sys.exit(validate_main())
