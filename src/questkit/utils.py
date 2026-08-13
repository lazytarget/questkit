"""Small string helpers."""

from __future__ import annotations

import re
import unicodedata


def slugify(title: str) -> str:
    # NFKD decomposes accented Latin letters (å/ä/ö/é/ñ/ü/...) into a base
    # letter plus a combining mark; dropping non-ASCII bytes then removes
    # just the marks, leaving a readable transliteration (e.g. "på" -> "pa")
    # instead of silently deleting the letter (e.g. "på" -> "p").
    normalized = unicodedata.normalize("NFKD", title)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    slug = ascii_only.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-") or "untitled"
