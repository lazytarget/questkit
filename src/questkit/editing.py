"""Shared `$EDITOR` invocation, used by `quest new --edit` and `quest edit`."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def open_in_editor(path: Path) -> bool:
    """Open `path` in `$EDITOR`, blocking until it exits.

    Returns whether the editor was actually launched -- `False` (having
    already printed why) when `$EDITOR` is unset, so a caller that only
    needs to re-normalize the file after a real edit knows to skip that too.
    """
    editor = os.environ.get("EDITOR")
    if not editor:
        print("[quest] $EDITOR is not set; skipping --edit")
        return False
    subprocess.run([editor, str(path)])
    return True
