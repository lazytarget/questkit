"""Command-line entry point for questkit."""

from __future__ import annotations

import argparse
import sys

from .commands import (
    deps_cmd,
    done_cmd,
    format_cmd,
    init_cmd,
    list_cmd,
    logs_cmd,
    migrate_cmd,
    mv_cmd,
    new_cmd,
    schema_cmd,
    set_cmd,
    show_cmd,
    validate_cmd,
)


def _add_list_options(parser: argparse.ArgumentParser) -> None:
    """Every flag `list` and its built-in-view aliases (`next`/`stale`/`blocked`)
    share -- a view is just a prefill over exactly this option set, so `quest
    next --where priority=high` composes rather than needing its own grammar.
    """
    parser.add_argument(
        "--where",
        dest="where",
        action="append",
        metavar="EXPR",
        help="repeatable filter: field=value / field~value / field:exists",
    )
    parser.add_argument(
        "-A", "--all-logs",
        dest="all_logs",
        action="store_true",
        help="aggregate quests from every log found downward from --root",
    )
    parser.add_argument(
        "--root",
        dest="root",
        action="append",
        help="repeatable; starting directory for -A (default: QST_ROOT, git root, or cwd)",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="silence the summary block on stderr",
    )
    parser.add_argument(
        "--format", dest="format", choices=["table", "json", "csv", "prompt"], default="table"
    )
    parser.add_argument(
        "--select",
        dest="select",
        metavar="a,b,c",
        help="restrict output to these fields, in order -- applies to every --format",
    )
    parser.add_argument(
        "--distinct",
        action="store_true",
        help="collapse rows identical across the --select'd fields (requires --select)",
    )
    parser.add_argument(
        "--count",
        action="store_true",
        help="print a bare integer; honors --where/--select/--distinct, ignores --limit/--offset",
    )
    parser.add_argument("--sort", dest="sort", metavar="FIELD[:asc|desc]")
    parser.add_argument("--limit", dest="limit", type=int)
    parser.add_argument("--offset", dest="offset", type=int)
    parser.add_argument("--out", dest="out", metavar="FILE", help="also write rendered output to FILE")
    parser.add_argument(
        "--in", dest="in_dirs", action="append", metavar="LOG", help="repeatable; name or path"
    )
    parser.add_argument(
        "--view",
        dest="view",
        metavar="NAME",
        help="a named view from the schema's views: map (default: 'default')",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="quest", description="File-based quest tracking.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_new = subparsers.add_parser("new", help="capture a new quest")
    p_new.add_argument("title")
    p_new.add_argument("--type", dest="type")
    p_new.add_argument("--tier", dest="tier")
    p_new.add_argument("--status", dest="status")
    p_new.add_argument("--priority", dest="priority")
    p_new.add_argument("--project", dest="project")
    p_new.add_argument("--description", dest="description")
    p_new.add_argument("--tag", dest="tags", action="append")
    p_new.add_argument(
        "--set",
        dest="sets",
        action="append",
        metavar="field=value",
        help="set any declared field; repeatable (argparse cannot grow a flag per custom field)",
    )
    p_new.add_argument("--in", dest="in_dir")
    p_new.add_argument("--edit", action="store_true")
    p_new.set_defaults(func=new_cmd.run)

    p_list = subparsers.add_parser("list", help="list quests")
    _add_list_options(p_list)
    p_list.set_defaults(func=list_cmd.run)

    # Built-in views as bare subcommands: each is `list` with its own view
    # preset via set_defaults, called *after* _add_list_options so it wins
    # over --view's own None default -- an explicit `--view NAME` on the
    # command line still overrides it, since argparse always prefers a value
    # actually given over any default. Config can override a built-in's
    # *definition* (schema.SchemaConfig.views), never its command name --
    # argparse is built before any log resolves, so the CLI's command list
    # can't depend on cwd.
    p_next = subparsers.add_parser("next", help="the single best quest to do next")
    _add_list_options(p_next)
    p_next.set_defaults(func=list_cmd.run, view="next")

    p_stale = subparsers.add_parser("stale", help="quests whose status has gone untouched")
    _add_list_options(p_stale)
    p_stale.set_defaults(func=list_cmd.run, view="stale")

    p_blocked = subparsers.add_parser("blocked", help="quests with an open dependency")
    _add_list_options(p_blocked)
    p_blocked.set_defaults(func=list_cmd.run, view="blocked")

    p_show = subparsers.add_parser("show", help="show a quest by id")
    p_show.add_argument("id")
    p_show.add_argument("--in", dest="in_dir")
    p_show.set_defaults(func=show_cmd.run)

    p_set = subparsers.add_parser("set", help="set one or more fields on a quest")
    p_set.add_argument("id")
    # nargs="*" rather than "+" so `quest set <id> --set f=v` reaches the
    # command and gets the message naming the positional form, instead of
    # argparse's "the following arguments are required: field=value".
    p_set.add_argument("assignments", nargs="*", metavar="field=value")
    p_set.add_argument(
        "--in",
        dest="in_dirs",
        action="append",
        metavar="LOG",
        help="repeatable; bounds the id search to these logs (name or path)",
    )
    # `set` takes positional assignments while `new` takes `--set`, and the
    # asymmetry has a cause: `new` has a positional title, so
    # `quest new "fix thing" type=bug` is genuinely ambiguous, while `set`'s
    # id + nargs="+" is not. Accepting `--set` here too would be a second
    # grammar for one operation, so it is a rejection that names the right
    # form rather than a silent alias.
    p_set.add_argument("--set", dest="rejected_set", action="append", help=argparse.SUPPRESS)
    p_set.set_defaults(func=set_cmd.run)

    p_done = subparsers.add_parser("done", help="mark a quest done")
    p_done.add_argument("id")
    p_done.add_argument("--in", dest="in_dirs", action="append", metavar="LOG")
    p_done.set_defaults(func=done_cmd.run)

    p_scrap = subparsers.add_parser("scrap", help="mark a quest scrapped")
    p_scrap.add_argument("id")
    p_scrap.add_argument("--in", dest="in_dirs", action="append", metavar="LOG")
    p_scrap.set_defaults(func=done_cmd.run_scrap)

    p_mv = subparsers.add_parser("mv", help="move a quest to a different quest log")
    p_mv.add_argument("id")
    p_mv.add_argument("dest", help="destination quests/ directory (must already be a quest log)")
    p_mv.add_argument("--in", dest="in_dir", help="restrict source lookup to this quest log")
    p_mv.set_defaults(func=mv_cmd.run)

    p_init = subparsers.add_parser("init", help="opt a directory into a quest log")
    p_init.add_argument("dir", nargs="?", default=None)
    p_init.add_argument("--base", action="store_true")
    p_init.add_argument("--hooks", action="store_true")
    p_init.add_argument("--project", dest="project")
    p_init.add_argument("--git", dest="git", choices=["auto", "manual"], default=None)
    p_init.set_defaults(func=init_cmd.run)

    p_validate = subparsers.add_parser("validate", help="validate quests against the schema")
    p_validate.add_argument("--in", dest="in_dir")
    p_validate.add_argument(
        "--notes",
        dest="notes",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="show informational notes (never affects the exit code)",
    )
    p_validate.set_defaults(func=validate_cmd.run)

    p_format = subparsers.add_parser(
        "format", help="reformat quest frontmatter to match the current normalization rules"
    )
    p_format.add_argument(
        "targets",
        nargs="*",
        metavar="PATH",
        help="quest files or log directories (default: the resolved log)",
    )
    p_format.add_argument("--in", dest="in_dir")
    p_format.add_argument(
        "--check",
        action="store_true",
        help="report what would change, write nothing, exit 1 if anything would",
    )
    p_format.add_argument(
        "--fill-defaults",
        dest="fill_defaults",
        action="store_true",
        help="backfill declared schema defaults into fields a quest is missing",
    )
    p_format.set_defaults(func=format_cmd.run)

    p_migrate = subparsers.add_parser("migrate", help="frontmatter-aware corpus migrations")
    p_migrate.add_argument(
        "--backfill",
        metavar="FIELD=SOURCE",
        help="set FIELD from SOURCE (a field, a {{ macro }}, or a literal) where FIELD is absent",
    )
    p_migrate.add_argument(
        "--rename-value",
        dest="rename_value",
        metavar="FIELD:old=new",
        help="rewrite one value of one field, never the body and never another field",
    )
    p_migrate.add_argument("--in", dest="in_dirs", action="append", metavar="LOG")
    p_migrate.add_argument(
        "-A", "--all-logs", dest="all_logs", action="store_true", help="every log under --root"
    )
    p_migrate.add_argument("--root", dest="root", action="append")
    p_migrate.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="print a per-file diff and write nothing",
    )
    p_migrate.add_argument(
        "--commit",
        action="store_true",
        help="commit per log afterwards; refuses on a dirty index",
    )
    p_migrate.set_defaults(func=migrate_cmd.run)

    p_logs = subparsers.add_parser("logs", help="inventory every quest log under a root")
    p_logs.add_argument("--root", dest="root", action="append", help="repeatable")
    p_logs.add_argument("--format", dest="format", choices=["table", "json"], default="table")
    p_logs.add_argument(
        "--verbose",
        action="store_true",
        help="table only: an extra line per log naming schema overrides and strict mode",
    )
    p_logs.set_defaults(func=logs_cmd.run)

    p_deps = subparsers.add_parser("deps", help="show a quest's dependency graph")
    p_deps.add_argument("id")
    p_deps.add_argument(
        "--blocks",
        action="store_true",
        help="walk the reverse direction: what this quest blocks, not what blocks it",
    )
    p_deps.add_argument(
        "--in", dest="in_dirs", action="append", metavar="LOG", help="repeatable; bounds the sweep"
    )
    p_deps.add_argument("--root", dest="root", action="append", help="repeatable")
    p_deps.set_defaults(func=deps_cmd.run)

    p_schema = subparsers.add_parser("schema", help="introspect the active schema (for agents)")
    p_schema.add_argument("kind", choices=["quest"])
    p_schema.add_argument("field", nargs="?", default=None)
    p_schema.add_argument("--format", dest="format", choices=["json", "table"], default="json")
    p_schema.add_argument("--in", dest="in_dir")
    p_schema.set_defaults(func=schema_cmd.run)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # top-level CLI error boundary: print, don't traceback
        print(f"[quest] error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
