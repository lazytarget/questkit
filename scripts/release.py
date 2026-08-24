#!/usr/bin/env python3
"""`scripts/release.py` — the release ritual, so it's not five hand-typed steps.

QST-cv23q: cutting `v0.3.0` was bump `pyproject.toml`, reinstall the editable
venv (or `questkit.__version__` goes stale against it — a real bug this same
session hit), update `CHANGELOG.md`, `git tag -a vX.Y.Z -m ...`, `git push
<remote> vX.Y.Z`, each easy to get wrong or skip under scoping pressure.

A script under `scripts/`, deliberately **not** a CLI verb (`quest release`)
-- release conventions differ too much across teams for the core tool to own
one; this one is questkit's own, scoped to this repo's own `quests/` log and
`CHANGELOG.md`. Converged with the R&D review (2026-08-22, R&D REL-2):

  1. every `milestone: <version>` quest must be terminal (done/scrapped)
     before anything else happens
  2. the `CHANGELOG.md` section is assembled from
     `quest list --where "milestone=X;status=done,scrapped" --format md`
     (QST-f6otu), grouped release-drafter-style by `type`:
     feature -> Added, bug -> Fixed, chore/task/epic -> Changed
  3. `pyproject.toml`'s `version` and the installed `questkit.__version__`
     must actually agree -- the exact drift this session hit
  4. an annotated, signed tag (`vX.Y.Z`, message pulled from that version's
     new `CHANGELOG.md` section) is created and pushed

Refuses outright (never guesses) on a dirty working tree or an
already-existing tag -- the same posture `quest commit`/`quest migrate
--commit` take (see `commands/commit_cmd.py`, `commands/migrate_cmd.py`).

`agentic: hitl`: prompts for confirmation before the tag/push step unless
`--yes`; `--dry-run` prints the assembled changelog section and stops before
writing or mutating anything.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import io
import json
import subprocess
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# feature -> Added, bug -> Fixed, chore/task -> Changed (release-drafter-style
# category mapping from `type`, per QST-cv23q's converged scope). `epic` has
# no dedicated bucket in the spec's mapping; it joins "Changed" rather than
# being silently dropped from the changelog.
CATEGORY_TYPES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Added", ("feature",)),
    ("Fixed", ("bug",)),
    ("Changed", ("chore", "task", "epic")),
)

TERMINAL_STATUSES = ("done", "scrapped")


class ReleaseError(Exception):
    """A refuse-before-mutating condition: printed and exits 1, no traceback."""


# --- version agreement -----------------------------------------------------------


def read_pyproject_version(repo_root: Path) -> str:
    data = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    try:
        return data["project"]["version"]
    except KeyError as exc:
        raise ReleaseError(f"{repo_root / 'pyproject.toml'} has no [project].version") from exc


def installed_version() -> str:
    """The installed package's own idea of its version -- `questkit.__version__`.

    A thin, separately-monkeypatchable wrapper: importing `questkit` here
    (rather than inlining `questkit.__version__` at every call site) is what
    lets a test simulate the exact drift this whole quest is about, without
    needing a second real install.
    """
    import questkit

    return questkit.__version__


def check_version_agreement(pyproject_version: str, installed: str) -> None:
    if pyproject_version != installed:
        raise ReleaseError(
            f"pyproject.toml declares version {pyproject_version!r} but the installed "
            f"questkit.__version__ is {installed!r} -- reinstall the editable venv "
            "(`pip install -e .`) before releasing"
        )


# --- git refuse-before-mutating checks --------------------------------------------


def is_working_tree_dirty(repo_root: Path) -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return bool(result.stdout.strip())


def tag_exists(repo_root: Path, tag: str) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/tags/{tag}"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


# --- milestone readiness + changelog assembly (via `quest list`) -----------------


def _quest_list(argv: list[str]) -> str:
    """Run `quest list <argv>` in-process and return its stdout.

    In-process (`questkit.cli.main`), not a `quest` subprocess: a stale
    globally-installed `quest` on PATH is exactly the kind of drift this
    script exists to catch, not something it should silently depend on for
    its own changelog assembly. This always runs the same code this script
    itself was invoked with.
    """
    from questkit.cli import main as quest_main

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = quest_main(argv)
    if code != 0:
        raise ReleaseError(f"`quest {' '.join(argv)}` failed (exit {code})")
    return buf.getvalue()


def offending_non_terminal_quests(quests_dir: Path, version: str) -> list[dict]:
    """Every `milestone: <version>` quest not in a terminal status.

    `status:exists` is required alongside `milestone=X` -- otherwise the
    default view's own `status=todo,in-progress` filter (a default, not a
    lock, but only overridden by a --where that itself names `status`) would
    silently hide the very done/scrapped/parked quests this check needs to
    see, defeating the whole point of the completeness check.
    """
    out = _quest_list(
        [
            "list", "--in", str(quests_dir),
            "--where", f"milestone={version};status:exists",
            "--format", "json", "--quiet",
        ]
    )
    rows = json.loads(out or "[]")
    return [
        {"id": row.get("id"), "status": row.get("status")}
        for row in rows
        if row.get("status") not in TERMINAL_STATUSES
    ]


def render_changelog_section(quests_dir: Path, version: str) -> str:
    """The `## [X.Y.Z]` body: `### Added`/`Fixed`/`Changed`, each a `--format md`
    bullet list (QST-f6otu) -- empty categories are omitted outright rather
    than printed with no bullets under them.
    """
    parts: list[str] = []
    for category, types in CATEGORY_TYPES:
        types_expr = ",".join(types)
        body = _quest_list(
            [
                "list", "--in", str(quests_dir),
                "--where", f"milestone={version};status=done,scrapped;type={types_expr}",
                "--select", "id,title", "--sort", "id", "--format", "md", "--quiet",
            ]
        ).strip()
        if body and body != "(no matching quests)":
            parts.append(f"### {category}\n\n{body}")
    return "\n\n".join(parts) if parts else "_(no changes)_"


# --- CHANGELOG.md -----------------------------------------------------------------


def write_changelog(changelog_path: Path, version: str, section: str, *, today: dt.date | None = None) -> None:
    """Prepend a new `## [X.Y.Z] — YYYY-MM-DD` entry above the first existing one.

    Creates the file (with the standard preamble) if it doesn't exist yet,
    rather than assuming every repo already has one.
    """
    heading = f"## [{version}] — {(today or dt.date.today()).isoformat()}\n\n{section}\n"

    if not changelog_path.exists():
        changelog_path.write_text(f"# Changelog\n\n{heading}", encoding="utf-8")
        return

    text = changelog_path.read_text(encoding="utf-8")
    marker = "\n## ["
    idx = text.find(marker)
    if idx == -1:
        new_text = text.rstrip("\n") + "\n\n" + heading
    else:
        insert_at = idx + 1  # right at the "## [" that starts the first existing entry
        new_text = text[:insert_at] + heading + "\n" + text[insert_at:]
    changelog_path.write_text(new_text, encoding="utf-8")


# --- tag + push --------------------------------------------------------------------


def _run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess:
    result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise ReleaseError(f"`{' '.join(argv)}` failed:\n{result.stdout}{result.stderr}")
    return result


def create_and_push_tag(repo_root: Path, tag: str, message: str, *, remote: str = "origin") -> None:
    _run(["git", "tag", "-s", "-a", tag, "-m", message], repo_root)
    _run(["git", "push", remote, tag], repo_root)


# --- orchestration -----------------------------------------------------------------


def _confirm(tag: str) -> bool:
    reply = input(f"[release] create and push tag {tag}? [y/N] ")
    return reply.strip().lower() in ("y", "yes")


def run(args: argparse.Namespace) -> None:
    repo_root: Path = args.repo_root
    quests_dir: Path = args.quests_dir or (repo_root / "quests")

    pyproject_version = read_pyproject_version(repo_root)
    check_version_agreement(pyproject_version, installed_version())

    if is_working_tree_dirty(repo_root):
        raise ReleaseError(
            f"{repo_root}: working tree is dirty. Commit or stash first -- a release "
            "must tag a clean tree."
        )

    tag = f"v{pyproject_version}"
    if tag_exists(repo_root, tag):
        raise ReleaseError(f"tag {tag} already exists")

    offenders = offending_non_terminal_quests(quests_dir, pyproject_version)
    if offenders:
        listing = "\n".join(f"  - {o['id']} ({o['status']})" for o in offenders)
        raise ReleaseError(
            f"milestone {pyproject_version} has {len(offenders)} non-terminal quest(s) -- "
            f"finish or scrap them before releasing:\n{listing}"
        )

    section = render_changelog_section(quests_dir, pyproject_version)
    print(section)

    if args.dry_run:
        print(f"[release] dry run -- would tag {tag} and push to {args.remote}", file=sys.stderr)
        return

    if not args.yes and not _confirm(tag):
        raise ReleaseError("aborted -- tag not created")

    write_changelog(repo_root / "CHANGELOG.md", pyproject_version, section)
    create_and_push_tag(repo_root, tag, section, remote=args.remote)
    print(f"[release] tagged and pushed {tag}")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--yes", action="store_true", help="skip the tag/push confirmation prompt")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="print the assembled changelog section; do not write CHANGELOG.md or tag/push",
    )
    parser.add_argument("--remote", default="origin", help="git remote to push the tag to (default: origin)")
    parser.add_argument(
        "--repo-root", type=Path, default=REPO_ROOT,
        help="override the repo root (mainly for testing)",
    )
    parser.add_argument(
        "--quests-dir", type=Path, default=None,
        help="override the quest log directory (default: <repo-root>/quests)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        run(args)
    except ReleaseError as exc:
        print(f"[release] {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
