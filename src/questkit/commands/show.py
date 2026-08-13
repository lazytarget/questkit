"""`quest show` — print a quest's full contents by id."""

from __future__ import annotations

import argparse

from ..discovery import resolve_mutation_target


def run(args: argparse.Namespace) -> int:
    found = resolve_mutation_target(args.id, explicit_in=args.in_dir)
    if found is None:
        print(f"[quest] no quest matching id '{args.id}' found")
        return 1
    _quests_dir, path = found
    print(path.read_text(encoding="utf-8"))
    return 0
