"""Command-line entry point for questkit."""

from __future__ import annotations

import argparse
import sys

from .commands import (
    done_cmd,
    format_cmd,
    init_cmd,
    list_cmd,
    migrate_cmd,
    mv_cmd,
    new_cmd,
    schema_cmd,
    set_cmd,
    show_cmd,
    validate_cmd,
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
    p_new.add_argument("--in", dest="in_dir")
    p_new.add_argument("--edit", action="store_true")
    p_new.set_defaults(func=new_cmd.run)

    p_list = subparsers.add_parser("list", help="list quests")
    p_list.add_argument(
        "--where",
        dest="where",
        action="append",
        metavar="EXPR",
        help="repeatable filter: field=value / field~value / field:exists",
    )
    p_list.add_argument(
        "--all",
        dest="all_logs",
        action="store_true",
        help="aggregate quests from every log found downward from --root",
    )
    p_list.add_argument(
        "--root", dest="root", help="starting directory for --all (default: QST_ROOT, git root, or cwd)"
    )
    p_list.add_argument(
        "--format", dest="format", choices=["table", "json", "csv", "prompt"], default="table"
    )
    p_list.add_argument("--columns", dest="columns", help="comma-separated columns (table/csv only)")
    p_list.add_argument("--sort", dest="sort", metavar="FIELD[:asc|desc]")
    p_list.add_argument("--limit", dest="limit", type=int)
    p_list.add_argument("--offset", dest="offset", type=int)
    p_list.add_argument("--out", dest="out", metavar="FILE", help="also write rendered output to FILE")
    p_list.add_argument("--in", dest="in_dir")
    p_list.set_defaults(func=list_cmd.run)

    p_show = subparsers.add_parser("show", help="show a quest by id")
    p_show.add_argument("id")
    p_show.add_argument("--in", dest="in_dir")
    p_show.set_defaults(func=show_cmd.run)

    p_set = subparsers.add_parser("set", help="set one or more fields on a quest")
    p_set.add_argument("id")
    p_set.add_argument("assignments", nargs="+", metavar="field=value")
    p_set.add_argument("--in", dest="in_dir")
    p_set.set_defaults(func=set_cmd.run)

    p_done = subparsers.add_parser("done", help="mark a quest done")
    p_done.add_argument("id")
    p_done.add_argument("--in", dest="in_dir")
    p_done.set_defaults(func=done_cmd.run)

    p_scrap = subparsers.add_parser("scrap", help="mark a quest scrapped")
    p_scrap.add_argument("id")
    p_scrap.add_argument("--in", dest="in_dir")
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
    p_migrate.add_argument("--root", dest="root")
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
