#!/usr/bin/env python3
"""`scripts/sensitive_scan.py` -- find names, employers and hosts you do not want published.

Credential scanners (gitleaks, detect-secrets, trufflehog) look for secrets by
shape and entropy. They cannot know that a client name or a relative's first
name is private. That needs a **deny-list**, and the deny-list is itself
sensitive, so it must never live in the repository it protects. Terms are read
from a private file outside the repo (default
``$XDG_CONFIG_HOME/questkit/sensitive-terms``, or the path in
``$SENSITIVE_TERMS_FILE``, or ``--terms-file``), plus ``--term`` / ``--pattern``
on the command line. Without any terms the hook modes pass with a notice, so
contributors who have no list are never blocked.

Terms file: one per line. ``#`` starts a comment. A line is a case-insensitive
regular expression; prefix it with ``lit:`` for a literal string.
``\\bacme\\b`` avoids matching "acmeist".

Modes::

    history   every commit on every ref (added lines and messages): which
              commits match, and how many would have to be rewritten
    tree      the current tree
    staged    staged added lines            (a pre-commit hook)
    push      commits about to be pushed    (a pre-push hook, reads stdin)

Exit status: 0 nothing found, 1 something found, 2 usage error.

Rewriting history changes the id of the first matching commit and of every
commit descended from it. ``history`` reports that count so the cost of a
redaction is known before it is paid.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

ZERO = "0" * 40


@dataclass(frozen=True)
class Term:
    label: str
    regex: re.Pattern[str]

    def search(self, text: str):
        return self.regex.search(text)


# --- terms ------------------------------------------------------------------------


def _literal(text: str) -> Term:
    return Term(text, re.compile(re.escape(text), re.IGNORECASE))


def _pattern(text: str) -> Term:
    return Term(text, re.compile(text, re.IGNORECASE))


def load_terms_file(path: Path) -> list[Term]:
    terms: list[Term] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("lit:"):
            terms.append(Term(line, re.compile(re.escape(line[4:]), re.IGNORECASE)))
        else:
            terms.append(_pattern(line))
    return terms


def default_terms_file() -> Path | None:
    env = os.environ.get("SENSITIVE_TERMS_FILE")
    if env:
        return Path(env).expanduser()
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    candidate = Path(base) / "questkit" / "sensitive-terms"
    return candidate if candidate.is_file() else None


def collect_terms(term: list[str], pattern: list[str], terms_file: str | None) -> list[Term]:
    terms: list[Term] = []
    path = Path(terms_file).expanduser() if terms_file else default_terms_file()
    if path is not None and path.is_file():
        terms.extend(load_terms_file(path))
    terms.extend(_literal(t) for t in term)
    terms.extend(_pattern(p) for p in pattern)
    return terms


# --- git helpers ----------------------------------------------------------------------


class GitError(Exception):
    """git exited non-zero; the message is its first line of stderr."""


def _first_line(text: str) -> str:
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return "git failed"


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        errors="replace",
    )
    if check and result.returncode != 0:
        raise GitError(_first_line(result.stderr))
    return result


def _git_lines(repo: Path, *args: str):
    """Stream a git command's stdout line by line (history can be large).

    A non-zero exit raises GitError once the output is exhausted: a scan that
    could not read the diff must not look like a scan that found nothing.
    """
    with tempfile.TemporaryFile("w+", errors="replace") as err:
        proc = subprocess.Popen(
            ["git", "-C", str(repo), *args],
            stdout=subprocess.PIPE,
            stderr=err,
            text=True,
            errors="replace",
        )
        assert proc.stdout is not None
        yield from proc.stdout
        proc.wait()
        if proc.returncode != 0:
            err.seek(0)
            raise GitError(_first_line(err.read()))


def _matching(terms: list[Term], text: str) -> set[str]:
    return {t.label for t in terms if t.search(text)}


def _added_lines(repo: Path, git_args: list[str]):
    """Yield (marker, path, new_line_number, text) for each added line in a patch.

    `marker` is the commit id when the patch comes from `git log -p`, else ''.
    """
    marker = ""
    path = ""
    lineno = 0
    for raw in _git_lines(repo, *git_args):
        line = raw.rstrip("\n")
        if line.startswith("\x01"):
            marker = line[1:]
            path = ""
        elif line.startswith("+++ "):
            path = line[6:] if line.startswith("+++ b/") else ""
        elif line.startswith("@@"):
            m = re.search(r"\+(\d+)", line)
            lineno = int(m.group(1)) if m else 0
        elif line.startswith("+"):
            yield marker, path, lineno, line[1:]
            lineno += 1


# --- scanning commits ----------------------------------------------------------------


@dataclass
class History:
    parents: dict[str, list[str]]
    meta: dict[str, tuple[str, str]]  # sha -> (date, subject)
    order: list[str]  # newest first (topological)
    matches: dict[str, set[str]]  # sha -> labels


def scan_history(repo: Path, revs: list[str], terms: list[Term]) -> History:
    parents: dict[str, list[str]] = {}
    order: list[str] = []
    for line in _git(repo, "rev-list", "--topo-order", "--parents", *revs).stdout.splitlines():
        sha, *rest = line.split()
        parents[sha] = rest
        order.append(sha)

    meta: dict[str, tuple[str, str]] = {}
    matches: dict[str, set[str]] = {}
    fmt = "--format=%H%x1f%ad%x1f%s%x1f%B%x1e"
    blob = _git(repo, "log", *revs, "--date=short", fmt).stdout
    for record in blob.split("\x1e"):
        record = record.strip("\n")
        if not record:
            continue
        sha, date, subject, body = record.split("\x1f", 3)
        meta[sha] = (date, subject)
        hit = _matching(terms, body)
        if hit:
            matches.setdefault(sha, set()).update(hit)

    for sha, _path, _n, text in _added_lines(
        repo, ["log", *revs, "-p", "-U0", "--no-color", "--no-ext-diff", "--format=%x01%H"]
    ):
        hit = _matching(terms, text)
        if hit and sha:
            matches.setdefault(sha, set()).update(hit)
    return History(parents, meta, order, matches)


def _descendants(parents: dict[str, list[str]]) -> dict[str, set[str]]:
    children: dict[str, list[str]] = {sha: [] for sha in parents}
    for sha, ps in parents.items():
        for p in ps:
            if p in children:
                children[p].append(sha)
    out: dict[str, set[str]] = {}
    for sha in parents:
        seen: set[str] = set()
        stack = list(children[sha])
        while stack:
            c = stack.pop()
            if c not in seen:
                seen.add(c)
                stack.extend(children[c])
        out[sha] = seen
    return out


def _squash_span(repo: Path, hist: History) -> int | None:
    matched = [s for s in reversed(hist.order) if s in hist.matches]  # oldest first
    if not matched:
        return None
    first, last = matched[0], matched[-1]
    if first == last:
        return 1
    related = _git(repo, "merge-base", "--is-ancestor", first, last, check=False)
    if related.returncode != 0:
        return None
    count = _git(repo, "rev-list", "--count", "--ancestry-path", f"{first}..{last}").stdout
    return int(count.strip()) + 1


def report_history(repo: Path, revs: list[str], terms: list[Term]) -> dict:
    hist = scan_history(repo, revs, terms)
    desc = _descendants(hist.parents)
    total = len(hist.parents)
    rewrite: set[str] = set()
    for sha in hist.matches:
        rewrite.add(sha)
        rewrite |= desc[sha]
    chronological = [s for s in reversed(hist.order) if s in hist.matches]

    per_term: dict[str, dict] = {}
    for sha in chronological:
        for label in sorted(hist.matches[sha]):
            entry = per_term.setdefault(label, {"commits": 0, "first": None})
            entry["commits"] += 1
            if entry["first"] is None:
                entry["first"] = sha

    return {
        "total_commits": total,
        "matches": [
            {
                "sha": sha,
                "date": hist.meta.get(sha, ("", ""))[0],
                "subject": hist.meta.get(sha, ("", ""))[1],
                "terms": sorted(hist.matches[sha]),
                "descendants": len(desc[sha]),
            }
            for sha in chronological
        ],
        "per_term": per_term,
        "rewrite_count": len(rewrite),
        "keep_count": total - len(rewrite),
        "squash_span": _squash_span(repo, hist),
    }


def _print_history(report: dict) -> None:
    total = report["total_commits"]
    matches = report["matches"]
    print(f"Matching commits: {len(matches)} of {total}")
    for m in matches:
        print(f"  {m['sha'][:7]} {m['date']} {m['subject']}  [{', '.join(m['terms'])}]")
    if not matches:
        return
    print("Per term:")
    for label, entry in report["per_term"].items():
        first = entry["first"]
        print(f"  {label}: {entry['commits']} commit(s), first {first[:7]}")
    print("Rewrite scope (the first match and every commit descended from it get new ids):")
    print(f"  would be rewritten: {report['rewrite_count']} of {total}")
    print(f"  keep their ids: {report['keep_count']}")
    span = report["squash_span"]
    shown = f"{span} commits" if span is not None else "n/a (matches on unrelated branches)"
    print(f"  squash span (first to last match): {shown}")


# --- modes ---------------------------------------------------------------------------


def cmd_history(args: argparse.Namespace, terms: list[Term]) -> int:
    report = report_history(args.repo, args.rev or ["--all"], terms)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _print_history(report)
    return 1 if report["matches"] else 0


def cmd_tree(args: argparse.Namespace, terms: list[Term]) -> int:
    found = 0
    files = _git(args.repo, "ls-files", "-z").stdout.split("\0")
    for name in filter(None, files):
        try:
            text = (args.repo / name).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            hit = _matching(terms, line)
            if hit:
                found += 1
                print(f"{name}:{number}  [{', '.join(sorted(hit))}]")
    print(f"{found} matching line(s) in the current tree")
    return 1 if found else 0


def cmd_staged(args: argparse.Namespace, terms: list[Term]) -> int:
    found = 0
    for _m, path, number, text in _added_lines(
        args.repo, ["diff", "--cached", "-U0", "--no-color", "--no-ext-diff"]
    ):
        hit = _matching(terms, text)
        if hit:
            found += 1
            print(f"{path}:{number}  [{', '.join(sorted(hit))}]")
    if found:
        print(f"sensitive-scan: {found} staged line(s) match your deny-list", file=sys.stderr)
    return 1 if found else 0


def _push_revs(repo: Path, local: str, remote: str) -> list[str] | None:
    if set(local) == {"0"}:
        return None  # branch deletion: nothing is being added
    if set(remote) == {"0"} or _git(repo, "cat-file", "-e", f"{remote}^{{commit}}", check=False).returncode:
        return [local, "--not", "--remotes"]
    return [f"{remote}..{local}"]


def _push_refs(args: argparse.Namespace) -> list[tuple[str, str]]:
    """(local, remote) pairs: from git's pre-push stdin, or, under the pre-commit
    framework (which does not forward stdin), from PRE_COMMIT_FROM_REF/TO_REF."""
    if getattr(args, "pre_commit", False):
        local = os.environ.get("PRE_COMMIT_TO_REF", "")
        if not local:
            return []
        return [(local, os.environ.get("PRE_COMMIT_FROM_REF") or ZERO)]
    pairs = []
    for line in sys.stdin.read().splitlines():
        parts = line.split()
        if len(parts) >= 4:
            pairs.append((parts[1], parts[3]))
    return pairs


def cmd_push(args: argparse.Namespace, terms: list[Term]) -> int:
    found = False
    for local, remote in _push_refs(args):
        revs = _push_revs(args.repo, local, remote)
        if revs is None:
            continue
        hist = scan_history(args.repo, revs, terms)
        for sha in reversed(hist.order):
            if sha in hist.matches:
                found = True
                date, subject = hist.meta.get(sha, ("", ""))
                print(f"  {sha[:7]} {date} {subject}  [{', '.join(sorted(hist.matches[sha]))}]")
    if found:
        print("sensitive-scan: the commits above match your deny-list; not pushing", file=sys.stderr)
    return 1 if found else 0


# --- cli -----------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    # The shared options are accepted before or after the mode, so both
    # `sensitive_scan.py --term x history` and `... history --term x` work.
    common = argparse.ArgumentParser(add_help=False, argument_default=argparse.SUPPRESS)
    common.add_argument("--repo", type=Path, help="repository (default: cwd)")
    common.add_argument("--term", action="append", help="literal term, case-insensitive")
    common.add_argument("--pattern", action="append", help="regular expression")
    common.add_argument(
        "--terms-file",
        help="deny-list file (default: $SENSITIVE_TERMS_FILE or ~/.config/questkit/sensitive-terms)",
    )
    parser = argparse.ArgumentParser(
        description="Scan git for names and hosts you want private.", parents=[common]
    )
    sub = parser.add_subparsers(dest="mode", required=True)
    hist = sub.add_parser("history", parents=[common], help="scan all commits and report the rewrite scope")
    hist.add_argument("--rev", action="append", help="revision(s) to scan (default: --all)")
    hist.add_argument("--json", action="store_true")
    hist.set_defaults(func=cmd_history, needs_terms=True)
    sub.add_parser("tree", parents=[common], help="scan the current tree").set_defaults(
        func=cmd_tree, needs_terms=True
    )
    sub.add_parser("staged", parents=[common], help="scan staged changes (pre-commit)").set_defaults(
        func=cmd_staged, needs_terms=False
    )
    push = sub.add_parser(
        "push", parents=[common], help="scan commits being pushed (pre-push, reads stdin)"
    )
    push.add_argument(
        "--pre-commit",
        action="store_true",
        help="take the range from PRE_COMMIT_FROM_REF/PRE_COMMIT_TO_REF instead of stdin",
    )
    push.set_defaults(func=cmd_push, needs_terms=False)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # Defaults are applied here, not via set_defaults, which would override a
    # value given before the mode name.
    args.repo = getattr(args, "repo", Path("."))
    terms_in = getattr(args, "term", [])
    patterns_in = getattr(args, "pattern", [])
    try:
        terms = collect_terms(terms_in, patterns_in, getattr(args, "terms_file", None))
    except re.error as exc:
        print(f"sensitive-scan: bad pattern: {exc}", file=sys.stderr)
        return 2
    if not terms:
        if args.needs_terms:
            print(
                "sensitive-scan: no terms configured. Use --term/--pattern, --terms-file, "
                "or create ~/.config/questkit/sensitive-terms",
                file=sys.stderr,
            )
            return 2
        print("sensitive-scan: no terms configured, skipping", file=sys.stderr)
        return 0
    try:
        _git(args.repo, "rev-parse", "--git-dir")  # fail early, with git's own words
        return args.func(args, terms)
    except GitError as exc:
        print(f"sensitive-scan: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:  # git itself is missing
        print(f"sensitive-scan: cannot run git: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
