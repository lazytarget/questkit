"""Quest ID generation."""

from __future__ import annotations

import secrets
import string
from pathlib import Path

_ALPHABET = string.digits + string.ascii_lowercase  # base36


def generate_id(quests_dir: Path, prefix: str = "QST-", length: int = 5, attempts: int = 50) -> str:
    """Generate a random base36 quest id, retrying on same-directory collision.

    Cross-device collisions can't be prevented here -- there is no safe home
    for a global counter in an offline-capable, multi-device system -- this
    only guards against a same-directory clash at creation time.
    """
    for _ in range(attempts):
        candidate = "".join(secrets.choice(_ALPHABET) for _ in range(length))
        full_id = f"{prefix}{candidate}"
        if not any(quests_dir.glob(f"{full_id}*.md")):
            return full_id
    raise RuntimeError(
        f"could not generate a unique quest id after {attempts} attempts; "
        "consider increasing id_length in .questkit.yaml"
    )
