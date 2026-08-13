"""`quest show` — print a quest's full contents by id."""

from __future__ import annotations

import argparse

from ..discovery import resolve_log
from ..quest import find_by_id


def run(args: argparse.Namespace) -> int:
    quests_dir = resolve_log(explicit=args.in_dir)
    path = find_by_id(quests_dir, args.id)
    if path is None:
        print(f"[quest] no quest matching id '{args.id}' found in {quests_dir}")
        return 1
    print(path.read_text(encoding="utf-8"))
    return 0
