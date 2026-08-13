"""Centralizes date generation so tests can monkeypatch it in one place."""

from __future__ import annotations

from datetime import date


def today() -> str:
    return date.today().isoformat()
