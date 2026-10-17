"""`quest format` — renormalize quest frontmatter, in a log or at named paths."""

from __future__ import annotations

import argparse
from pathlib import Path

from .. import macros
from ..config import CONFIG_FILENAME, ConfigVersionError, QuestLogConfig, config_exists
from ..discovery import resolve_log
from ..quest import Quest, QuestFileError, glob_quests
from ..schema import SchemaConfigError, SchemaExtendsError


def run(args: argparse.Namespace) -> int:
    check_only = getattr(args, "check", False)
    fill_defaults = getattr(args, "fill_defaults", False)
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

        config = _config_for(path)
        quest.reorder(config.schema)
        if fill_defaults:
            try:
                _fill_defaults(quest, config, path)
            except macros.UnknownMacroError as exc:
                print(f"[!] {path}: {exc}")
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
    return glob_quests(quests_dir, config.pattern)


def _dedupe(paths: list[Path]) -> list[Path]:
    """Overlapping targets (a file and its directory) must not be formatted twice."""
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in paths:
        if path not in seen:
            seen.add(path)
            unique.append(path)
    return unique


def _config_for(path: Path) -> QuestLogConfig:
    """The config for the log a quest file lives in, or the built-in default.

    A quest file always sits directly in its log directory, so `path.parent`
    is that log. Falls back to the defaults when it has no `.questkit.yaml`
    (or the config cannot be read) -- `quest format <a stray file>` should
    still normalize something sensible rather than crash, which is the same
    fallback `hooks._schema_for` already makes.
    """
    try:
        return QuestLogConfig.load(path.parent)
    except (OSError, ConfigVersionError, SchemaExtendsError, SchemaConfigError):
        return QuestLogConfig()


def _fill_defaults(quest: Quest, config: QuestLogConfig, path: Path) -> None:
    """Write every declared default into fields the quest is missing.

    A hard prerequisite for adopting any `required: true` field against a live
    corpus: the moment a log declares one, `quest validate` fails every quest
    that predates it and the pre-commit hook blocks every commit.

    Deliberately does not bump `modified` -- backfilling a field nobody asked
    about is not a content edit, and `--fill-defaults` across the corpus giving
    every quest a fresh `modified` is precisely the laundering `status_changed`
    exists to prevent.
    """
    defaults = config.schema.resolved_defaults(config.defaults)
    context = macros.context_for(quest, config, path)
    for name, raw in defaults.items():
        if not _is_blank(quest.frontmatter.get(name)):
            continue
        value = macros.expand(str(raw), context) if macros.has_macro(str(raw)) else raw
        quest.set(name, value)
    quest.reorder(config.schema)


def _is_blank(value) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def _would_change(quest: Quest) -> bool:
    """Whether `save()` would write, without writing.

    Rendering is the only honest predicate -- normalization is spread across
    three `_normalize_*` passes plus ruamel's own dump, so anything short of
    running them would drift from what `save()` actually produces.
    """
    return quest.render() != quest.path.read_text(encoding="utf-8")
