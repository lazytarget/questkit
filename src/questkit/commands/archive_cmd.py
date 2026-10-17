"""`quest archive`/`unarchive` (per quest) and `archive-log`/`unarchive-log` (bulk).

`archived` answers a retention question, orthogonal to `status`: a `done`
quest in a wound-up project is archived and not scrapped. Per-quest commands
are sugar over `quest set`, exactly like `quest done`. `archive-log` sets no
log-level state -- it is purely a bulk `quest archive` over every quest in
the resolved log, so "how many are archived" always derives from the files
themselves and can never drift from a stored flag.
"""

from __future__ import annotations

import argparse

from ..config import QuestLogConfig
from ..discovery import resolve_log
from ..quest import Quest, glob_quests
from ..timeutil import today
from . import set_cmd


def run_archive(args: argparse.Namespace) -> int:
    args.assignments = ["archived=true"]
    return set_cmd.run(args)


def run_unarchive(args: argparse.Namespace) -> int:
    args.assignments = ["archived=false"]
    return set_cmd.run(args)


def run_archive_log(args: argparse.Namespace) -> int:
    return _bulk(args, value=True, verb="archive-log")


def run_unarchive_log(args: argparse.Namespace) -> int:
    return _bulk(args, value=False, verb="unarchive-log")


def _bulk(args: argparse.Namespace, value: bool, verb: str) -> int:
    quests_dir = resolve_log(explicit=args.log)
    config = QuestLogConfig.load(quests_dir)

    changed = 0
    for path in glob_quests(quests_dir, config.pattern):
        quest = Quest.load(path)
        # Idempotent: a quest already at the target state is left untouched,
        # including its `modified` -- re-running `archive-log` on a log with
        # some quests captured afterward must not bump every file's date.
        if bool(quest.get("archived")) == value:
            continue
        quest.set("archived", value)
        quest.frontmatter["modified"] = today()
        quest.save()
        changed += 1

    plural = "" if changed == 1 else "s"
    print(f"[quest {verb}] {quests_dir}: {changed} quest{plural} changed")
    return 0
