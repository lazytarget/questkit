"""Resolve which quest log a command should operate on."""

from __future__ import annotations

import os
from pathlib import Path

from .config import CONFIG_FILENAME

QUEST_LOG_ENV = "QUEST_LOG"


class QuestLogNotFoundError(Exception):
    """Raised when no quest log can be resolved from any source."""


def resolve_log(explicit: str | None = None, start: Path | None = None) -> Path:
    """Resolve the `quests/` directory a command should operate on.

    Order: an explicit `--in` override, then walking up from `start`
    (default: cwd) looking for a `.questkit.yaml` marker -- either directly
    in an ancestor, or in that ancestor's `quests/` child -- then the
    `QUEST_LOG` environment variable, then an actionable error.
    """
    if explicit is not None:
        explicit_path = Path(explicit).expanduser().resolve()
        if (explicit_path / CONFIG_FILENAME).is_file():
            return explicit_path
        raise QuestLogNotFoundError(
            f"'{explicit_path}' is not a quest log (no {CONFIG_FILENAME} found). "
            f"Run 'quest init {explicit_path}' first."
        )

    found = _walk_up(start or Path.cwd())
    if found is not None:
        return found

    env_value = os.environ.get(QUEST_LOG_ENV)
    if env_value:
        env_path = Path(env_value).expanduser().resolve()
        if (env_path / CONFIG_FILENAME).is_file():
            return env_path
        raise QuestLogNotFoundError(
            f"QUEST_LOG='{env_path}' is not a quest log (no {CONFIG_FILENAME} found)."
        )

    raise QuestLogNotFoundError(
        "no quest log found: run 'quest init' here, or set QUEST_LOG to your central log."
    )


def _walk_up(start: Path) -> Path | None:
    current = start.resolve()
    while True:
        if (current / CONFIG_FILENAME).is_file():
            return current
        candidate = current / "quests"
        if (candidate / CONFIG_FILENAME).is_file():
            return candidate
        parent = current.parent
        if parent == current:
            return None
        current = parent
