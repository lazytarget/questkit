"""`quest logs` — inventory every quest log found under a root. Read-only."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from .. import schema
from ..config import ConfigVersionError, QuestLogConfig
from ..discovery import resolve_log_set, resolve_sweep_roots
from ..quest import Quest


@dataclass
class LogEntry:
    """One discovered log's identity, counts, and schema surface.

    A collision on `project:` is a hard error rather than a field here --
    `--in`'s name resolution (QST-fmk0p) assumes `project:` is identity, so a
    collision means that assumption is already false somewhere in the corpus,
    and `run()` reports it immediately rather than building a row for it.
    """

    quests_dir: Path
    project: str | None
    quests: int
    open: int
    archived: int
    git: str
    fields: tuple
    strict: bool
    field_order: tuple
    error: str | None = None


def run(args: argparse.Namespace) -> int:
    roots = resolve_sweep_roots(explicit=args.root)
    logs = resolve_log_set(all_logs=True, root=args.root)

    entries: list[LogEntry] = []
    warnings: list[str] = []
    seen_projects: dict[str, Path] = {}

    for quests_dir in logs:
        try:
            config = QuestLogConfig.load(quests_dir)
        except (ConfigVersionError, schema.SchemaExtendsError, schema.SchemaConfigError) as exc:
            warnings.append(f"{quests_dir}: {exc}")
            entries.append(
                LogEntry(
                    quests_dir=quests_dir,
                    project=None,
                    quests=0,
                    open=0,
                    archived=0,
                    git="?",
                    fields=(),
                    strict=True,
                    field_order=(),
                    error=str(exc),
                )
            )
            continue

        project = config.project
        if project:
            if project in seen_projects:
                other = seen_projects[project]
                print(
                    f"[quest logs] error: project '{project}' is declared by both "
                    f"{other} and {quests_dir} -- project: must be unique per log",
                    file=sys.stderr,
                )
                return 1
            seen_projects[project] = quests_dir

        paths = sorted(quests_dir.glob(config.pattern))
        quests = [Quest.load(p) for p in paths]
        terminal = config.schema.terminal_statuses
        open_count = sum(1 for q in quests if q.get("status") not in terminal)
        archived_count = sum(1 for q in quests if bool(q.get("archived")))

        entries.append(
            LogEntry(
                quests_dir=quests_dir,
                project=project,
                quests=len(quests),
                open=open_count,
                archived=archived_count,
                git=config.git,
                fields=tuple(sorted(config.schema.fields)),
                strict=config.schema.strict,
                field_order=config.schema.field_order,
            )
        )

    entries.sort(key=lambda e: e.project or "")

    if args.format == "json":
        print(json.dumps([_as_dict(e, roots) for e in entries], indent=2, ensure_ascii=False))
        return 0

    _print_table(entries, roots, verbose=args.verbose)
    for warning in warnings:
        print(f"[quest logs] warning: {warning}", file=sys.stderr)
    return 0


def _as_dict(entry: LogEntry, roots: list[Path]) -> dict:
    return {
        "project": entry.project,
        "path": _relative_path(entry.quests_dir, roots),
        "quests": entry.quests,
        "open": entry.open,
        "archived": entry.archived,
        "git": entry.git,
        "fields": list(entry.fields),
        "strict": entry.strict,
        "field_order": list(entry.field_order),
        **({"error": entry.error} if entry.error else {}),
    }


def _relative_path(quests_dir: Path, roots: list[Path]) -> str:
    for root in roots:
        try:
            return str(quests_dir.relative_to(root))
        except ValueError:
            continue
    return str(quests_dir)


def _print_table(entries: list[LogEntry], roots: list[Path], *, verbose: bool) -> None:
    header = f"{'PROJECT':<20} {'QUESTS':>6} {'OPEN':>6}  {'GIT':<7} PATH"
    print(header)

    total_quests = 0
    total_open = 0
    for entry in entries:
        project = entry.project or "-"
        path = _relative_path(entry.quests_dir, roots)
        if entry.error:
            print(f"{project:<20} {'?':>6} {'?':>6}  {'?':<7} {path}  [error: {entry.error}]")
            continue
        print(f"{project:<20} {entry.quests:>6} {entry.open:>6}  {entry.git:<7} {path}")
        if verbose:
            fields_desc = ", ".join(entry.fields) or "(none)"
            print(
                f"{'':<20} strict={entry.strict}  fields=[{fields_desc}]  "
                f"field_order={list(entry.field_order)}"
            )
        # A fully archived log is excluded from footer totals -- its work is
        # done, and counting it forever would make the totals line drift from
        # what is actually still moving.
        if entry.quests == 0 or entry.archived < entry.quests:
            total_quests += entry.quests
            total_open += entry.open

    roots_desc = ", ".join(str(r) for r in roots)
    plural = "" if len(entries) == 1 else "s"
    print(
        f"\n{len(entries)} log{plural}, {total_quests} quests ({total_open} open), "
        f"swept from {roots_desc}"
    )
