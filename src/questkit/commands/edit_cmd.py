"""`quest edit` — open the resolved quest file in `$EDITOR`.

Parity with `quest new --edit`: same `$EDITOR` invocation (`editing.py`),
same id resolution as `quest show` (`resolve_mutation_target`). Unlike
`new`, there is no fresh file to normalize on the way in, so the file is
re-saved through `Quest.save()` after the editor exits, to normalize
whatever a human just hand-edited -- the same guarantee every other write
path already gives.
"""

from __future__ import annotations

import argparse

from ..discovery import resolve_mutation_target
from ..editing import open_in_editor
from ..quest import Quest


def run(args: argparse.Namespace) -> int:
    found = resolve_mutation_target(args.id, explicit_in=args.in_dir)
    if found is None:
        print(f"[quest] no quest matching id '{args.id}' found")
        return 1
    _quests_dir, path = found
    if open_in_editor(path):
        Quest.load(path).save()
    return 0
