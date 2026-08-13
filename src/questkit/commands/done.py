"""`quest done` — sugar for `quest set <id> status=completed`."""

from __future__ import annotations

import argparse

from . import set_cmd


def run(args: argparse.Namespace) -> int:
    args.assignments = ["status=completed"]
    return set_cmd.run(args)
