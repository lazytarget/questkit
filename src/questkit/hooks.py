"""Entry points invoked by pre-commit: `quest-format`, `quest-validate`, `quest-bump-modified`."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from . import schema
from .config import ConfigVersionError, QuestLogConfig
from .gitutil import find_git_root
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
            quest = Quest.load(path)
        except (OSError, QuestFileError) as exc:
            print(f"[!] {exc}")
            continue
        # `save()` reports whether it wrote, so the read-save-reread dance
        # this used to do is gone -- and the hook no longer touches the mtime
        # of every staged file on every commit.
        if quest.save():
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
    """Pre-commit hook entry point: bump `modified` on each staged quest file to
    today, and backfill `status_changed` when a raw text edit (Obsidian, or
    anything that isn't the CLI) changed `status` without updating it itself.
    """
    paths = argv if argv is not None else sys.argv[1:]
    today_str = today()
    for raw_path in paths:
        path = Path(raw_path)
        try:
            quest = Quest.load(path)
        except QuestFileError as exc:
            print(f"[!] {exc}")
            continue

        if _backfill_status_changed(quest, path, today_str):
            print(f"[quest-bump-modified] {path}: backfilled status_changed")

        # str()-compare: `modified` normalizes to a real `date` object on save
        # (see quest._normalize_date_fields), so a straight `!=` against the
        # plain ISO string here would always be true and rewrite -- and
        # re-save -- every staged file on every commit, changed or not.
        if str(quest.frontmatter.get("modified")) != today_str:
            quest.frontmatter["modified"] = today_str
        quest.save()
    return 0


def _backfill_status_changed(quest: Quest, path: Path, today_str: str) -> bool:
    """Catch a status transition made by a raw text edit rather than the CLI.

    `quest set`/`quest done`/etc. already stamp `status_changed` themselves
    the moment *they* change `status` (`set_cmd.run` diffs the assignment in
    memory) -- this only fires for the case they can't see: a file hand-
    edited (in Obsidian, or by anyone bypassing the CLI) and then staged for
    commit. Compares the staged content against what's actually committed at
    `HEAD`, not some earlier in-memory snapshot, so it catches the edit
    whether it happened five minutes or five days ago.

    Silently does nothing when there's no HEAD version to diff against (a
    brand-new quest has no prior status to have transitioned *from* -- the
    field being absent there is correct, not a bug to backfill) or the file
    isn't inside a git repo at all. Also leaves `status_changed` alone
    whenever *it* already differs from HEAD too -- that means something (the
    CLI in the same change, a `quest migrate --backfill`) already set it
    deliberately, and overwriting a deliberate value would fight it rather
    than help.
    """
    previous = _previous_quest(path)
    if previous is None:
        return False
    if quest.get("status") == previous.get("status"):
        return False
    if str(quest.get("status_changed")) != str(previous.get("status_changed")):
        return False
    quest.set("status_changed", today_str)
    return True


def _previous_quest(path: Path) -> Quest | None:
    """This file's content as committed at `HEAD`, or `None` when there's
    nothing to compare against (not a git repo, no commits yet, or this
    particular file is new -- `git show` fails for all three the same way)."""
    git_root = find_git_root(path.parent)
    if git_root is None:
        return None
    try:
        rel = path.resolve().relative_to(git_root)
    except ValueError:
        return None
    result = subprocess.run(
        ["git", "show", f"HEAD:{rel.as_posix()}"], cwd=git_root, capture_output=True
    )
    if result.returncode != 0:
        return None
    try:
        return Quest.from_text(path, result.stdout.decode("utf-8", errors="replace"))
    except QuestFileError:
        return None


if __name__ == "__main__":
    sys.exit(validate_main())
