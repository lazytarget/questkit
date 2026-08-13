"""Command-line entry point for questkit."""

from __future__ import annotations

import argparse
import sys

from .commands import done, init, list_cmd, new, set_cmd, show, validate


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
    p_new.set_defaults(func=new.run)

    p_list = subparsers.add_parser("list", help="list quests")
    p_list.add_argument("--status", dest="status")
    p_list.add_argument("--type", dest="type")
    p_list.add_argument("--tag", dest="tag")
    p_list.add_argument("--in", dest="in_dir")
    p_list.set_defaults(func=list_cmd.run)

    p_show = subparsers.add_parser("show", help="show a quest by id")
    p_show.add_argument("id")
    p_show.add_argument("--in", dest="in_dir")
    p_show.set_defaults(func=show.run)

    p_set = subparsers.add_parser("set", help="set one or more fields on a quest")
    p_set.add_argument("id")
    p_set.add_argument("assignments", nargs="+", metavar="field=value")
    p_set.add_argument("--in", dest="in_dir")
    p_set.set_defaults(func=set_cmd.run)

    p_done = subparsers.add_parser("done", help="mark a quest completed")
    p_done.add_argument("id")
    p_done.add_argument("--in", dest="in_dir")
    p_done.set_defaults(func=done.run)

    p_init = subparsers.add_parser("init", help="opt a directory into a quest log")
    p_init.add_argument("dir", nargs="?", default=None)
    p_init.add_argument("--base", action="store_true")
    p_init.add_argument("--hooks", action="store_true")
    p_init.add_argument("--project", dest="project")
    p_init.add_argument("--git", dest="git", choices=["auto", "manual"], default=None)
    p_init.set_defaults(func=init.run)

    p_validate = subparsers.add_parser("validate", help="validate quests against the schema")
    p_validate.add_argument("--in", dest="in_dir")
    p_validate.set_defaults(func=validate.run)

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
