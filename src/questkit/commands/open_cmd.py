"""`quest open` — the `gh --web` analog: launch a quest in Obsidian.

Resolution matches `quest show`/`quest edit` exactly (`resolve_mutation_target`).
Obsidian is launched via its `obsidian://open?path=<absolute path>` URI
scheme through the platform opener (`open` on macOS, `xdg-open` on Linux,
`os.startfile` on Windows) -- Obsidian itself resolves which open vault (if
any) contains that absolute path, so no vault name needs to be known or
guessed here. When a path lies inside more than one open vault (a
realm-root vault and a nested per-zone vault both open on it), Obsidian
picks whichever vault claims the longest/most specific matching root --
in practice the more deeply nested vault wins, since its root is a more
specific prefix of the path.

Fallback order when there is no opener, or Obsidian is not installed/no
vault is open on the path: `$EDITOR` (`--editor` requests this outright,
skipping Obsidian entirely), then printing the path for the user to open
by hand.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import urllib.parse
from pathlib import Path

from ..discovery import resolve_mutation_target
from ..editing import open_in_editor


def build_obsidian_uri(path: Path) -> str:
    """The `obsidian://open?path=<absolute path>` URI for `path`."""
    return "obsidian://open?" + urllib.parse.urlencode({"path": str(path)})


def _launch_in_obsidian(path: Path) -> bool:
    """Best-effort: hand the obsidian:// URI to the platform opener.

    Returns whether it appears to have launched -- `False` (never raising)
    whenever there's no opener, or the process can't even start, so the
    caller falls back to `$EDITOR`.
    """
    uri = build_obsidian_uri(path)
    if sys.platform == "win32":
        try:
            import os

            os.startfile(uri)  # type: ignore[attr-defined]
            return True
        except OSError:
            return False

    opener = "open" if sys.platform == "darwin" else "xdg-open"
    try:
        subprocess.run([opener, uri], check=True, capture_output=True)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def run(args: argparse.Namespace) -> int:
    found = resolve_mutation_target(args.id, explicit_in=args.in_dir)
    if found is None:
        print(f"[quest] no quest matching id '{args.id}' found")
        return 1
    _quests_dir, path = found

    if not args.editor and _launch_in_obsidian(path):
        return 0

    if open_in_editor(path):
        return 0

    print(str(path))
    return 0
