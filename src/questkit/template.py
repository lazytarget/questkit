"""Default Markdown body skeleton for a freshly created quest."""

from __future__ import annotations


def render_body(created: str) -> str:
    return (
        "## Description\n\n"
        "## Acceptance Criteria\n\n"
        "- [ ] ...\n\n"
        "## Log\n\n"
        f"- {created}: captured\n"
    )
