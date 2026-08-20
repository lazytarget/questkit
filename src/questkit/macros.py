"""`{{ name }}` substitution for schema defaults and migration sources.

Plain substitution, no control flow, and no new dependency. Jinja2 was
rejected as a large dependency for string substitution into a Markdown
skeleton, and because `{% if %}` turns a body template into something you
debug. `{{ }}` is a strict subset of Jinja's syntax, so adopting Jinja later
costs nothing. `$PROJECT` was rejected because it reads as shell interpolation
in YAML, and the first thing anyone tries is `$HOME`.

This module ships with `quest migrate` (QST-lc3co), which is the first
consumer -- `--backfill reviewed={{ today }}`. The schema engine (QST-j68u5
rule 3) adds the remaining names and the single evaluation point for
defaults: after id generation, before first save, so `{{ id }}` and
`{{ slug }}` are always available.
"""

from __future__ import annotations

import os
import re

from .timeutil import today

_MACRO_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_.]*)\s*\}\}")


class UnknownMacroError(Exception):
    """Raised when a template names a macro that has no value in this context."""


def expand(template: str, context: dict[str, object]) -> str:
    """Substitute every `{{ name }}` in `template` from `context`.

    An unknown name is an error rather than an empty string: a default of
    `{{ projekt }}` silently expanding to nothing would write a blank field
    into every quest a log ever captures, and only be noticed by grep months
    later.
    """

    def _replace(match: re.Match) -> str:
        name = match.group(1)
        if name.startswith("env."):
            return os.environ.get(name[4:], "")
        if name == "today":
            return today()
        if name in context and context[name] is not None:
            return str(context[name])
        raise UnknownMacroError(
            f"unknown macro '{{{{ {name} }}}}' (known: "
            f"{', '.join(sorted({*context, 'today', 'env.<VAR>'}))})"
        )

    return _MACRO_RE.sub(_replace, template)


def has_macro(value: str) -> bool:
    return bool(_MACRO_RE.search(value))
