"""`quest format` — renormalize quest frontmatter, in a log or at named paths."""

from __future__ import annotations

import argparse
from pathlib import Path

from ..config import CONFIG_FILENAME, ConfigVersionError, QuestLogConfig, config_exists
from ..discovery import resolve_log
from ..quest import Quest, QuestFileError


def run(args: argparse.Namespace) -> int:
    check_only = getattr(args, "check", False)
    try:
        paths = _resolve_targets(getattr(args, "targets", None), args.in_dir)
    except TargetError as exc:
        print(f"[quest format] {exc}")
        return 1

    checked = 0
    changed = 0
    for path in paths:
        checked += 1
        try:
            quest = Quest.load(path)
        except (OSError, QuestFileError) as exc:
            print(f"[!] {exc}")
            continue

        if check_only:
            if _would_change(quest):
                changed += 1
                print(f"[quest format] {path}: would reformat")
            continue

        if quest.save():
            changed += 1
            print(f"[quest format] {path}: reformatted")

    if check_only:
        print(f"[quest format] {checked} quest(s) checked, {changed} would be reformatted")
        return 1 if changed else 0

    print(f"[quest format] {checked} quest(s) checked, {changed} reformatted")
    return 0


class TargetError(Exception):
    """Raised when an explicit `quest format` target cannot be turned into quest files."""


def _resolve_targets(targets: list[str] | None, in_dir: str | None) -> list[Path]:
    """Expand the positional targets into quest file paths, or fall back to the log.

    A directory target must resolve **that directory's** config and glob
    **its** `pattern`: `pattern`/`prefix`/`id_length` are per-log settings, so
    a hardcoded `QST-*.md` would silently format nothing in a log that renamed
    its prefix -- and report "0 quest(s) checked" as if the log were clean.
    """
    if not targets:
        quests_dir = resolve_log(explicit=in_dir)
        if not config_exists(quests_dir):
            raise TargetError(f"{quests_dir}: no {CONFIG_FILENAME} found")
        return _glob_log(quests_dir)

    paths: list[Path] = []
    for raw in targets:
        path = Path(raw).expanduser().resolve()
        if path.is_dir():
            paths.extend(_glob_log(path))
        elif path.is_file():
            paths.append(path)
        else:
            raise TargetError(f"{path}: no such file or directory")
    return _dedupe(paths)


def _glob_log(quests_dir: Path) -> list[Path]:
    if not config_exists(quests_dir):
        raise TargetError(f"{quests_dir}: no {CONFIG_FILENAME} found")
    try:
        config = QuestLogConfig.load(quests_dir)
    except ConfigVersionError as exc:
        raise TargetError(str(exc)) from exc
    return sorted(quests_dir.glob(config.pattern))


def _dedupe(paths: list[Path]) -> list[Path]:
    """Overlapping targets (a file and its directory) must not be formatted twice."""
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in paths:
        if path not in seen:
            seen.add(path)
            unique.append(path)
    return unique


def _would_change(quest: Quest) -> bool:
    """Whether `save()` would write, without writing.

    Rendering is the only honest predicate -- normalization is spread across
    three `_normalize_*` passes plus ruamel's own dump, so anything short of
    running them would drift from what `save()` actually produces.
    """
    return quest.render() != quest.path.read_text(encoding="utf-8")
