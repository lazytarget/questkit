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
  4. the new `CHANGELOG.md` entry is committed on its own, so the tag holds its
     own changelog
  5. an annotated, signed tag (`vX.Y.Z`, message pulled from that version's
     new `CHANGELOG.md` section) is created on that commit
  6. the current branch and the tag are pushed together (`git push --atomic`, so
     a tag never reaches a remote without its commit) to every `--remote`, in the
     order given. There is no default for a repository with several remotes and no
     `origin`: where a release goes has to be named.

Refuses outright (never guesses) on a dirty working tree, an already-existing tag,
an unknown remote or a detached HEAD -- the same posture `quest commit`/`quest
migrate --commit` take (see `commands/commit_cmd.py`,
`commands/migrate_cmd.py`) -- all before anything is written.

If the changelog commit is refused (a hook), the file is put back as it was. If
the tag cannot be created (no signing key), the script's own commit is undone.
Once a push has succeeded the release is public and nothing is rolled back: a
failure on a later remote is reported with the exact commands that finish it.

`agentic: hitl`: prompts for confirmation before the commit/tag/push step unless
`--yes`; `--dry-run` prints the assembled changelog section and what it would
do, and stops before writing or mutating anything.
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


def resolve_remotes(repo_root: Path, requested: list[str] | None) -> list[str]:
    """The remotes to push to, each once, in the order given.

    With none named: `origin` if there is one, else the only remote. A repository
    with several remotes and no `origin` is refused rather than guessed at --
    pushing a release is outward-facing, and with two unsynced remotes the right
    answer is a decision, not a default.
    """
    available = _run(["git", "remote"], repo_root).stdout.split()
    if requested:
        unknown = [r for r in requested if r not in available]
        if unknown:
            raise ReleaseError(
                f"no git remote named {', '.join(repr(r) for r in unknown)}; "
                f"this repository has: {', '.join(available) or '(none)'}"
            )
        return list(dict.fromkeys(requested))
    if "origin" in available:
        return ["origin"]
    if len(available) == 1:
        return list(available)
    if not available:
        raise ReleaseError("this repository has no git remote to push the release to")
    raise ReleaseError(
        f"this repository has several remotes ({', '.join(available)}) and no 'origin': "
        "say where the release goes with --remote, once per remote "
        "(they are pushed in the order given)"
    )


def current_branch(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "symbolic-ref", "--quiet", "--short", "HEAD"],
        cwd=repo_root, capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise ReleaseError("HEAD is detached: check out the branch to release from first")
    return result.stdout.strip()


def _restore_changelog(repo_root: Path, was_tracked: bool) -> None:
    """Put CHANGELOG.md back as it was before the release touched it."""
    if was_tracked:
        subprocess.run(["git", "checkout", "HEAD", "--", "CHANGELOG.md"], cwd=repo_root, capture_output=True)
        return
    subprocess.run(
        ["git", "rm", "-f", "--cached", "--ignore-unmatch", "--", "CHANGELOG.md"],
        cwd=repo_root, capture_output=True,
    )
    (repo_root / "CHANGELOG.md").unlink(missing_ok=True)


def commit_changelog(repo_root: Path, version: str) -> str:
    """Commit CHANGELOG.md on its own and return the new commit id.

    The caller has already written the file onto a clean tree, so it is the only
    change. If the commit is refused (a pre-commit hook), the file is put back and
    the tree is clean again, so the next attempt is not tripped by this one.
    """
    was_tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", "CHANGELOG.md"],
        cwd=repo_root, capture_output=True,
    ).returncode == 0
    try:
        _run(["git", "add", "--", "CHANGELOG.md"], repo_root)
        _run(
            [
                "git", "commit",
                "-m", f"chore(release): changelog for {version}",
                "-m", "Written by scripts/release.py before the tag is created, so the tag holds its own changelog entry.",
            ],
            repo_root,
        )
    except ReleaseError:
        _restore_changelog(repo_root, was_tracked)
        raise
    return _run(["git", "rev-parse", "HEAD"], repo_root).stdout.strip()


_SIGNATURE_MARKERS = ("-----BEGIN SSH SIGNATURE-----", "-----BEGIN PGP SIGNATURE-----")


def create_tag(repo_root: Path, tag: str, message: str) -> None:
    """Create the annotated, signed tag, and make sure it really is signed.

    git exits 0 after some ssh signing errors (git 2.43 with a signing key that
    cannot be loaded prints the error and still creates an unsigned annotated tag),
    so the exit status proves nothing: the tag object itself must carry a signature
    block, or it is deleted and the release stops.
    """
    _run(["git", "tag", "-s", "-a", tag, "-m", message], repo_root)
    body = _run(["git", "cat-file", "tag", tag], repo_root).stdout
    if not any(marker in body for marker in _SIGNATURE_MARKERS):
        subprocess.run(["git", "tag", "-d", tag], cwd=repo_root, capture_output=True)
        raise ReleaseError(
            f"git created {tag} but did not sign it (is a signing key configured and "
            "readable?); the unsigned tag was deleted"
        )


def _undo_release_commit(repo_root: Path, previous_head: str, release_commit: str) -> None:
    """Take back the script's own commit, and only that commit.

    Used when the tag cannot be created. Guarded twice: it acts only if HEAD is
    still exactly the commit this run made, and the tree was clean before it, so
    the reset can lose nothing but that one commit.
    """
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, text=True).stdout.strip()
    if head == release_commit:
        subprocess.run(["git", "reset", "--hard", previous_head], cwd=repo_root, capture_output=True)


def push_release(repo_root: Path, branch: str, tag: str, remotes: list[str]) -> None:
    """Push the branch and the tag together to each remote, in order, stopping at
    the first failure.

    `--atomic`: either both refs land or neither does, so a remote never holds a
    tag whose commit is missing from its branch. The order is the caller's, so a
    private remote listed first fails before a public one is touched. A failure
    reports what was already pushed and the exact commands that finish the job.
    """
    pushed: list[str] = []
    for remote in remotes:
        result = subprocess.run(
            ["git", "push", "--atomic", remote, f"refs/heads/{branch}", f"refs/tags/{tag}"],
            cwd=repo_root, capture_output=True, text=True,
        )
        if result.returncode != 0:
            remaining = remotes[len(pushed):]
            finish = "\n".join(f"  git push --atomic {r} refs/heads/{branch} refs/tags/{tag}" for r in remaining)
            raise ReleaseError(
                f"push to '{remote}' failed:\n{result.stdout}{result.stderr}\n"
                f"already pushed to: {', '.join(pushed) or '(none)'}\n"
                f"to finish by hand, once the cause is fixed:\n{finish}"
            )
        pushed.append(remote)


# --- orchestration -----------------------------------------------------------------


def _confirm(tag: str, branch: str, remotes: list[str]) -> bool:
    reply = input(
        f"[release] commit the changelog, tag {tag}, and push {branch} and {tag} to "
        f"{', '.join(remotes)}? [y/N] "
    )
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

    remotes = resolve_remotes(repo_root, args.remote)
    branch = current_branch(repo_root)

    section = render_changelog_section(quests_dir, pyproject_version)
    print(section)

    if args.dry_run:
        print(
            f"[release] dry run -- would commit the changelog, tag {tag} and push "
            f"{branch} and {tag} to: {', '.join(remotes)}",
            file=sys.stderr,
        )
        return

    if not args.yes and not _confirm(tag, branch, remotes):
        raise ReleaseError("aborted -- nothing was changed")

    previous_head = _run(["git", "rev-parse", "HEAD"], repo_root).stdout.strip()
    write_changelog(repo_root / "CHANGELOG.md", pyproject_version, section)
    release_commit = commit_changelog(repo_root, pyproject_version)
    try:
        create_tag(repo_root, tag, section)
    except ReleaseError as exc:
        _undo_release_commit(repo_root, previous_head, release_commit)
        raise ReleaseError(f"{exc}\nthe changelog commit was undone; nothing was tagged or pushed") from exc
    push_release(repo_root, branch, tag, remotes)
    print(f"[release] committed the changelog, tagged {tag}, and pushed to: {', '.join(remotes)}")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--yes", action="store_true", help="skip the tag/push confirmation prompt")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="print the assembled changelog section; do not write CHANGELOG.md or tag/push",
    )
    parser.add_argument(
        "--remote", action="append", default=None, metavar="REMOTE",
        help="git remote to push the branch and tag to; repeat it for several, pushed in "
             "the order given (default: origin, or the only remote; refused if there are several)",
    )
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
