"""`quest done` and `quest scrap` — sugar for the two terminal statuses.

Both read the log's declared `terminal_statuses` rather than a hardcoded
value. `quest done` writes the first entry, `quest scrap` the last, so a log
using `shipped`/`cancelled` gets the right word from the same command. A
hardcoded `completed` would break the first log that renames its vocabulary,
which is the whole point of having one.
"""

from __future__ import annotations

import argparse

from ..config import QuestLogConfig
from ..discovery import resolve_mutation_target
from . import set_cmd


def run(args: argparse.Namespace) -> int:
    return _terminate(args, index=0)


def run_scrap(args: argparse.Namespace) -> int:
    return _terminate(args, index=-1)


def _terminate(args: argparse.Namespace, index: int) -> int:
    """Resolve the target log's terminal vocabulary, then delegate to `quest set`.

    The target is resolved twice -- once here to read the log's schema, once
    inside `set_cmd` to write. Cheap (a glob and a small YAML load), and the
    alternative is threading a resolved target through `set_cmd`'s signature
    for one caller.
    """
    found = resolve_mutation_target(args.id, explicit_in=args.in_dirs)
    if found is None:
        print(f"[quest] no quest matching id '{args.id}' found")
        return 1
    quests_dir, _ = found

    terminal = QuestLogConfig.load(quests_dir).schema.terminal_statuses
    args.assignments = [f"status={terminal[index]}"]
    return set_cmd.run(args)
