"""`quest migrate` — frontmatter-aware corpus migrations.

Two verbs, one per migration shape that actually mutates files. The decider
is not convenience, it is that `sed` is unsafe here: quest bodies and
`description:` values contain the words being renamed in ordinary prose.
Verified in questkit's own log on 2026-08-19:

    QST-bmzl2:114  - [ ] Every quest ... is completed or explicitly scrapped
    QST-whm2e:65   ... Completed quests stay exactly where they were created

A line-oriented substitution corrupts both. Only a frontmatter-aware tool can
rename a *value of a field* without touching prose that happens to use the
same word -- and questkit is the only thing that parses this
format.

Deliberately absent: schema *file* migration, rollback (git is the undo), and
any automatic migration on load. Migrations are always explicit.
"""

from __future__ import annotations

import argparse
import copy
import difflib
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .. import macros, schema
from ..config import ConfigVersionError, QuestLogConfig
from ..discovery import resolve_log_set
from ..gitutil import find_git_root
from ..quest import Quest, QuestFileError, glob_quests


class MigrationError(Exception):
    """Raised for a malformed verb, or a refusal to proceed."""


@dataclass
class LogOutcome:
    """What one migration did to one log."""

    quests_dir: Path
    project: str
    changed: list[Path] = field(default_factory=list)
    skipped: int = 0


def run(args: argparse.Namespace) -> int:
    try:
        mutate = _build_mutation(args)
        if args.commit and args.dry_run:
            raise MigrationError("--commit and --dry-run are mutually exclusive")
        logs = resolve_log_set(in_dirs=args.in_dirs, all_logs=args.all_logs, root=args.root)
        if args.commit:
            _refuse_on_dirty_index(logs)
    except MigrationError as exc:
        print(f"[quest migrate] {exc}")
        return 1

    outcomes: list[LogOutcome] = []
    for quests_dir in logs:
        try:
            outcome = _migrate_log(quests_dir, mutate, dry_run=args.dry_run)
        except (ConfigVersionError, schema.SchemaExtendsError) as exc:
            print(f"[quest migrate] skipping {quests_dir}: {exc}", file=sys.stderr)
            continue
        outcomes.append(outcome)

    if args.commit:
        _commit_each_log(outcomes, args)

    _print_summary(outcomes, dry_run=args.dry_run)
    return 0


# --- the two verbs ---------------------------------------------------------------


def _build_mutation(args: argparse.Namespace):
    """Turn the CLI verb into a `(quest, context) -> bool` mutation.

    Returning a closure keeps the traversal, dry-run rendering, summary and
    commit logic identical for every verb -- a verb only decides whether one
    quest's frontmatter changes.
    """
    if args.backfill and args.rename_value:
        raise MigrationError("pass one verb at a time: --backfill or --rename-value")
    if args.backfill:
        return _backfill(args.backfill)
    if args.rename_value:
        return _rename_value(args.rename_value)
    raise MigrationError("no migration requested (expected --backfill or --rename-value)")


def _backfill(expr: str):
    """`FIELD=SOURCE` — set FIELD from SOURCE only where FIELD is absent.

    SOURCE is another field name, a `{{ macro }}`, or a literal. Never
    overwrites an existing value: a backfill that could clobber is a
    different, far more dangerous operation, and this one has to be safe to
    re-run across 129 files in logs other people share.
    """
    field_name, sep, source = expr.partition("=")
    field_name, source = field_name.strip(), source.strip()
    if not sep or not field_name or not source:
        raise MigrationError(f"malformed --backfill '{expr}' (expected FIELD=SOURCE)")

    def _apply(quest: Quest, context: dict) -> bool:
        if not _is_absent(quest.frontmatter.get(field_name)):
            return False
        if macros.has_macro(source):
            value = macros.expand(source, context)
        elif source in context["known_fields"]:
            # A field reference. Resolved against the log's field vocabulary
            # rather than against this one file, so a quest that happens to
            # lack the source field is *skipped* rather than having the
            # literal string "created" written into it.
            if _is_absent(quest.frontmatter.get(source)):
                return False
            # Deep-copied, not referenced. Assigning the source field's own
            # object makes it appear twice in one document, and ruamel then
            # emits a YAML anchor/alias pair -- the real corpus dry-run
            # produced `status_changed: *id001`. That round-trips fine through
            # a YAML parser and is useless to everything else: Obsidian's
            # Properties panel, `grep`, and a human reading the file. For a
            # list value it is worse than cosmetic, since the two fields would
            # then share one mutable object.
            value = copy.deepcopy(quest.frontmatter[source])
        else:
            value = source
        # `Quest.set` places a newly-introduced key at its conventional
        # position rather than appending it -- the same rule `quest set` uses.
        quest.set(field_name, value)
        return True

    return _apply


def _rename_value(expr: str):
    """`FIELD:old=new` — rewrite one value of one field, and nothing else.

    Handles a list-valued field by rewriting the matching member in place, so
    renaming one tag does not collapse the list.
    """
    field_name, sep, rest = expr.partition(":")
    old, eq, new = rest.partition("=")
    field_name, old, new = field_name.strip(), old.strip(), new.strip()
    if not (sep and eq and field_name and old and new):
        raise MigrationError(f"malformed --rename-value '{expr}' (expected FIELD:old=new)")

    def _apply(quest: Quest, _context: dict) -> bool:
        current = quest.frontmatter.get(field_name)
        if isinstance(current, list):
            hits = [index for index, item in enumerate(current) if str(item) == old]
            for index in hits:
                current[index] = new
            return bool(hits)
        if current is not None and str(current) == old:
            quest.frontmatter[field_name] = new
            return True
        return False

    return _apply


def _known_fields(quests_dir: Path, config: QuestLogConfig, paths: list[Path]) -> set[str]:
    """Every field name this log uses, for telling a field reference from a literal.

    `--backfill status_changed=created` means "copy the `created` field";
    `--backfill owner=peter` means "the literal string peter". Nothing in the
    syntax distinguishes them, so the decision is made **once per log** from
    the log's actual field vocabulary -- the core required fields, its
    schema's declared fields, and the union of keys present in its quests.

    Per-log rather than per-file on purpose. Deciding per file would make the
    same command mean different things in two quests in the same directory:
    a quest missing `created` would get the literal string "created" written
    into it while its neighbour got a real date. A genuinely ambiguous case
    remains (wanting the literal string "created" in a log that has a
    `created` field), and it loses to the field reference -- the summary
    reports what changed, and the operation has `--dry-run`.
    """
    names = set(schema.CORE_FIELDS) | set(config.schema.fields)
    for path in paths:
        try:
            names |= set(Quest.load(path).frontmatter.keys())
        except (OSError, QuestFileError):
            continue
    return names


def _is_absent(value) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


# --- traversal -------------------------------------------------------------------


def _migrate_log(quests_dir: Path, mutate, *, dry_run: bool) -> LogOutcome:
    config = QuestLogConfig.load(quests_dir)
    project = config.project or quests_dir.name
    outcome = LogOutcome(quests_dir=quests_dir, project=project)
    paths = glob_quests(quests_dir, config.pattern)
    known_fields = _known_fields(quests_dir, config, paths)

    for path in paths:
        try:
            quest = Quest.load(path)
        except (OSError, QuestFileError) as exc:
            print(f"[!] {exc}")
            outcome.skipped += 1
            continue

        before = path.read_text(encoding="utf-8")
        context = {
            "project": project,
            "log": quests_dir.name,
            "id": quest.get("id"),
            "title": quest.get("title"),
            "owner": quest.get("owner"),
            "slug": path.stem.partition("--")[2],
            "known_fields": known_fields,
        }

        try:
            touched = mutate(quest, context)
        except macros.UnknownMacroError as exc:
            raise MigrationError(str(exc)) from exc

        if not touched:
            outcome.skipped += 1
            continue

        # Deliberately no `modified` bump and no `status_changed` write. A
        # migration is not a content edit, and renaming `completed` to `done`
        # is the same status under a new name rather than a transition -- so
        # neither of the loop-closure signals v3 exists to create may be
        # laundered by the migration that introduces them.
        after = quest.render()
        if after == before:
            outcome.skipped += 1
            continue

        if dry_run:
            _print_diff(path, before, after)
            outcome.changed.append(path)
            continue

        if quest.save():
            outcome.changed.append(path)
        else:  # pragma: no cover - render() already proved a difference
            outcome.skipped += 1

    return outcome


def _print_diff(path: Path, before: str, after: str) -> None:
    diff = difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile=f"a/{path.name}",
        tofile=f"b/{path.name}",
        n=1,
    )
    print("".join(diff), end="")


# --- git -------------------------------------------------------------------------


def _refuse_on_dirty_index(logs: list[Path]) -> None:
    """A dirty index makes a migration-only commit impossible, so refuse before writing.

    Not a warning: with staged changes there is no way to produce a commit
    containing only the migration, and a migration touching 129 files across
    7 repositories is the last place to discover that after the fact. Checked
    before any mutation for the same reason.
    """
    for repo_root in _repos_for(logs):
        staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        if staged.stdout.strip():
            raise MigrationError(
                f"{repo_root}: index is dirty ({staged.stdout.split()[0]} and possibly more "
                "staged). Commit or unstage first -- a migration commit must contain only "
                "the migration."
            )


def _repos_for(logs: list[Path]) -> list[Path]:
    roots: list[Path] = []
    for quests_dir in logs:
        root = find_git_root(quests_dir)
        if root is not None and root not in roots:
            roots.append(root)
    return roots


def _commit_each_log(outcomes: list[LogOutcome], args: argparse.Namespace) -> None:
    """One commit per log, in that log's own repo.

    This is the first command that writes to multiple repositories in a
    single invocation, which is exactly why `--commit` is opt-in.

    `--no-verify`: a migration is deliberately not a content edit (see the
    module docstring's field-preservation rule), and a per-file pre-commit
    hook can't tell "a trusted, deterministic rewrite of every value in one
    field" apart from "a hand edit" -- it only sees a diff. Found concretely:
    `quest-bump-modified`'s own status-transition backfill (QST-3h09k) reads
    a `--rename-value status:completed=done` migration's diff exactly like a
    missed manual transition and stamps `status_changed` to today, silently
    undoing the very invariant this function exists to guarantee. `quest
    migrate` already writes fully normalized, schema-shape-preserving
    content via `Quest.save()` before this ever runs -- rerunning
    `quest-format`/`quest-validate` here is redundant, not a safety net
    being removed.
    """
    verb = "backfill" if args.backfill else "rename-value"
    detail = args.backfill or args.rename_value
    for outcome in outcomes:
        if not outcome.changed:
            continue
        repo_root = find_git_root(outcome.quests_dir)
        if repo_root is None:
            print(
                f"[quest migrate] {outcome.quests_dir} is not inside a git repo, skipping commit"
            )
            continue
        rels = [str(p.relative_to(repo_root)) for p in outcome.changed]
        message = (
            f"quest({outcome.project}): migrate — {verb} {detail} ({len(outcome.changed)} files)"
        )
        try:
            subprocess.run(["git", "add", "--", *rels], cwd=repo_root, check=True, capture_output=True)
            subprocess.run(
                ["git", "commit", "--no-verify", "-m", message, "--", *rels],
                cwd=repo_root,
                check=True,
                capture_output=True,
            )
            print(f"[quest migrate] {outcome.project}: committed {len(outcome.changed)} file(s)")
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode(errors="replace").strip() if exc.stderr else str(exc)
            print(f"[quest migrate] {outcome.project}: commit failed: {stderr}")


# --- summary ---------------------------------------------------------------------


def _print_summary(outcomes: list[LogOutcome], *, dry_run: bool) -> None:
    total_changed = sum(len(o.changed) for o in outcomes)
    total_skipped = sum(o.skipped for o in outcomes)
    prefix = "[quest migrate] would change" if dry_run else "[quest migrate]"
    logs_word = "log" if len(outcomes) == 1 else "logs"

    for outcome in outcomes:
        if outcome.changed:
            print(f"[quest migrate] {outcome.project}: {len(outcome.changed)} file(s)")

    print(
        f"{prefix} {len(outcomes)} {logs_word} swept, "
        f"{total_changed} changed, {total_skipped} skipped"
    )
