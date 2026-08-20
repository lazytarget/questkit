"""`quest show` — print a quest's full contents by id."""

from __future__ import annotations

import argparse
import sys

from ..discovery import resolve_mutation_target
from ..quest import Quest


def run(args: argparse.Namespace) -> int:
    found = resolve_mutation_target(args.id, explicit_in=args.in_dir)
    if found is None:
        print(f"[quest] no quest matching id '{args.id}' found")
        return 1
    _quests_dir, path = found
    print(path.read_text(encoding="utf-8"))
    # Archival affects listing, never id resolution -- `show` finds an
    # archived quest exactly as it finds any other, just noted on stderr so a
    # human reading a piped stdout still learns why it wasn't in `list`.
    if Quest.load(path).get("archived"):
        print(f"[quest show] note: {args.id} is archived", file=sys.stderr)
    return 0
