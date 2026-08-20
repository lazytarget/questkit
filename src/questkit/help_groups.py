"""Grouped `--help` rendering for questkit's ~20 top-level subcommands.

`argparse` renders subcommands as one flat, insertion-ordered list -- fine at
10 commands, a wall at 20+, and the reader who suffers most is an agent
reading `quest --help` cold. Every command stays reachable exactly as
before (no renaming, no nesting, no per-group `--help`); only the rendering
of the top-level `--help` groups them, the same shape `git help -a` uses.
"""

from __future__ import annotations

import argparse

GROUP_ORDER = ("Capture", "Query", "Modify", "Logs", "Maintain", "Introspect")


class GroupedSubparsers:
    """Wraps an argparse subparsers action, requiring `group=` on every command.

    Use `.add(name, group=..., help=...)` in place of the action's own
    `.add_parser(...)` everywhere. `.validate()` -- called once, right after
    every command is registered -- raises if any command was added without
    going through `.add(...)`, so a subparser can never render silently
    ungrouped.
    """

    def __init__(self, subparsers_action: argparse._SubParsersAction) -> None:
        self._action = subparsers_action
        self._groups: dict[str, str] = {}
        self._views: set[str] = set()

    def add(
        self, name: str, *, group: str, help: str, view: bool = False
    ) -> argparse.ArgumentParser:
        if group not in GROUP_ORDER:
            raise ValueError(f"'{group}' is not a known help group ({', '.join(GROUP_ORDER)})")
        self._groups[name] = group
        if view:
            self._views.add(name)
        return self._action.add_parser(name, help=help)

    def validate(self) -> None:
        missing = [name for name in self._action.choices if name not in self._groups]
        if missing:
            raise RuntimeError(
                f"subcommand(s) {missing} registered with no help group -- every command "
                "must go through GroupedSubparsers.add(..., group=...), never the raw "
                "subparsers action, or it renders silently ungrouped in --help"
            )

    def formatter_class(self) -> type[argparse.HelpFormatter]:
        """A `HelpFormatter` subclass rendering this action's subcommands
        grouped, instead of the default flat insertion-ordered list."""
        groups, views = dict(self._groups), set(self._views)
        target_action = self._action

        class _GroupedHelpFormatter(argparse.HelpFormatter):
            def _format_action(self, action: argparse.Action) -> str:
                if action is not target_action:
                    return super()._format_action(action)
                subactions = list(action._get_subactions())
                pieces = []
                for group in GROUP_ORDER:
                    entries = [a for a in subactions if groups.get(a.dest) == group]
                    if not entries:
                        continue
                    pieces.append(f"\n{group}\n")
                    for sub in entries:
                        text = super(_GroupedHelpFormatter, self)._format_action(sub)
                        if sub.dest in views:
                            text = text.rstrip("\n") + "  (view)\n"
                        pieces.append(text)
                return "".join(pieces)

        return _GroupedHelpFormatter
