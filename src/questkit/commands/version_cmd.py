"""`quest version` — print the installed questkit version.

A real subcommand rather than only a `--version` flag: agents and scripts
that already treat every questkit action as `quest <verb>` (per `quest
schema quest`'s own introspection philosophy) shouldn't need a special case
for this one fact. `--version` stays too, as the flag every CLI user reaches
for first -- both print exactly the same string, from the same source.
"""

from __future__ import annotations

import argparse

from .. import __version__


def run(args: argparse.Namespace) -> int:
    print(f"questkit {__version__}")
    return 0
