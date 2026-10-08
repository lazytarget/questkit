"""Entry points invoked by git hooks: `quest-format`, `quest-validate`,
`quest-bump-modified` (pre-commit), and `quest-apply-trailers` (post-commit,
or timer-driven -- see QST-22gdn)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from . import schema
from .config import ConfigVersionError, QuestLogConfig
from .discovery import resolve_mutation_target
from .gitutil import find_git_root
from .quest import Quest, QuestFileError
from .timeutil import today


def _schema_for(path: Path) -> schema.SchemaConfig:
    """Best-effort: the schema for the log a staged quest file lives in.

    A quest file always sits directly in its log directory (flat structure,
    no active/archive subdirs), so `path.parent` is that log's `quests/` dir.
    Falls back to the built-in defaults if it has no `.questkit.yaml` (or
    that config can't be read) -- the hook should still validate something
    sensible rather than crash on a stray input.
    """
    try:
        return QuestLogConfig.load(path.parent).schema
    except (OSError, ConfigVersionError, schema.SchemaExtendsError):
        return schema.SchemaConfig.default()


def format_main(argv: list[str] | None = None) -> int:
    """Pre-commit hook entry point: normalize each staged quest file's frontmatter formatting.

    Pure re-save, no field-value changes -- runs first, before `quest-validate`/
    `quest-bump-modified`, so those see already-normalized content (matching
    Obsidian's own frontmatter writer -- see `quest.py`'s `_normalize_*`
    functions) instead of re-litigating array/quote style on every commit.
    """
    paths = argv if argv is not None else sys.argv[1:]
    for raw_path in paths:
        path = Path(raw_path)
        try:
            quest = Quest.load(path)
        except (OSError, QuestFileError) as exc:
            print(f"[!] {exc}")
            continue
        # `save()` reports whether it wrote, so the read-save-reread dance
        # this used to do is gone -- and the hook no longer touches the mtime
        # of every staged file on every commit.
        if quest.save():
            print(f"[quest-format] {path}: reformatted")
    return 0


def validate_main(argv: list[str] | None = None) -> int:
    """Pre-commit hook entry point: validate each staged quest file path in argv."""
    paths = argv if argv is not None else sys.argv[1:]
    total_errors = 0
    for raw_path in paths:
        path = Path(raw_path)
        try:
            quest = Quest.load(path)
        except QuestFileError as exc:
            print(f"[!] {exc}")
            total_errors += 1
            continue
        errors = schema.validate_quest(quest, _schema_for(path))
        for error in errors:
            print(f"[!] {error}")
        total_errors += len(errors)
    return 1 if total_errors else 0


def bump_modified_main(argv: list[str] | None = None) -> int:
    """Pre-commit hook entry point: bump `modified` on each staged quest file to
    today, and backfill `status_changed` when a raw text edit (Obsidian, or
    anything that isn't the CLI) changed `status` without updating it itself.
    """
    paths = argv if argv is not None else sys.argv[1:]
    today_str = today()
    for raw_path in paths:
        path = Path(raw_path)
        try:
            quest = Quest.load(path)
        except QuestFileError as exc:
            print(f"[!] {exc}")
            continue

        # Only a file whose content differs from HEAD is being edited; bumping
        # the rest would re-date the whole corpus on `--all-files` (QST-reakz).
        # A brand-new quest has no HEAD version and counts as changed.
        if not _differs_from_head(path):
            continue

        backfilled = _backfill_status_changed(quest, path, today_str)
        if backfilled:
            print(f"[quest-bump-modified] {path}: backfilled status_changed")

        # str()-compare: `modified` normalizes to a real `date` object on save
        # (see quest._normalize_date_fields), so a straight `!=` against the
        # plain ISO string here would always be true and rewrite -- and
        # re-save -- every staged file on every commit, changed or not.
        old_modified = str(quest.frontmatter.get("modified"))
        bumped = old_modified != today_str
        if bumped:
            quest.frontmatter["modified"] = today_str
            print(
                f"[quest-bump-modified] {path.name}: modified {old_modified} \u2192 {today_str}"
            )
        quest.save()

        if bumped or backfilled:
            # pre-commit fails a hook that leaves *unstaged* changes, whatever
            # its exit code. Staging our own edit lets the hook pass and puts
            # the bump in the same commit.
            _stage(path)
    return 0


def _git_root_and_rel(path: Path) -> tuple[Path, Path] | None:
    git_root = find_git_root(path.parent)
    if git_root is None:
        return None
    try:
        return git_root, path.resolve().relative_to(git_root)
    except ValueError:
        return None


def _head_bytes(path: Path) -> bytes | None:
    """This file's content as committed at `HEAD`, or `None` when there is
    nothing to compare against (not a git repo, no commits yet, or a new file)."""
    located = _git_root_and_rel(path)
    if located is None:
        return None
    git_root, rel = located
    result = subprocess.run(
        ["git", "show", f"HEAD:{rel.as_posix()}"], cwd=git_root, capture_output=True
    )
    return result.stdout if result.returncode == 0 else None


def _differs_from_head(path: Path) -> bool:
    head = _head_bytes(path)
    return head is None or head != path.read_bytes()


def _stage(path: Path) -> None:
    located = _git_root_and_rel(path)
    if located is None:
        return
    git_root, rel = located
    subprocess.run(["git", "add", "--", rel.as_posix()], cwd=git_root, capture_output=True)


def _backfill_status_changed(quest: Quest, path: Path, today_str: str) -> bool:
    """Catch a status transition made by a raw text edit rather than the CLI.

    `quest set`/`quest done`/etc. already stamp `status_changed` themselves
    the moment *they* change `status` (`set_cmd.run` diffs the assignment in
    memory) -- this only fires for the case they can't see: a file hand-
    edited (in Obsidian, or by anyone bypassing the CLI) and then staged for
    commit. Compares the staged content against what's actually committed at
    `HEAD`, not some earlier in-memory snapshot, so it catches the edit
    whether it happened five minutes or five days ago.

    Silently does nothing when there's no HEAD version to diff against (a
    brand-new quest has no prior status to have transitioned *from* -- the
    field being absent there is correct, not a bug to backfill) or the file
    isn't inside a git repo at all. Also leaves `status_changed` alone
    whenever *it* already differs from HEAD too -- that means something (the
    CLI in the same change, a `quest migrate --backfill`) already set it
    deliberately, and overwriting a deliberate value would fight it rather
    than help.
    """
    previous = _previous_quest(path)
    if previous is None:
        return False
    if quest.get("status") == previous.get("status"):
        return False
    if str(quest.get("status_changed")) != str(previous.get("status_changed")):
        return False
    quest.set("status_changed", today_str)
    return True


def _previous_quest(path: Path) -> Quest | None:
    """This file's content as committed at `HEAD`, or `None` when there's
    nothing to compare against (not a git repo, no commits yet, or this
    particular file is new -- `git show` fails for all three the same way)."""
    head = _head_bytes(path)
    if head is None:
        return None
    try:
        return Quest.from_text(path, head.decode("utf-8", errors="replace"))
    except QuestFileError:
        return None


def apply_trailers_main(argv: list[str] | None = None) -> int:
    """`quest-apply-trailers` (QST-22gdn): read `Quest:` git trailers off one
    or more commits and transition (or Log-mention) the quest(s) they name.

    Trailer forms (parsed with `git interpret-trailers --parse`, never prose
    regex, so this matches git's own understanding of what a trailer is)::

        Quest: QST-x7k2m done      # token = the literal status name -> transition
        Quest: QST-x7k2m           # bare mention -> `## Log` append only

    The **fixed key** is always `Quest:`. The **token is the exact status
    value** written to `status:` -- validated against the *target* log's own
    declared `statuses` (a schema-overridden vocabulary writes its own words,
    e.g. `Quest: QST-x shipped`). No verb mapping, no `status=X` form.

    Callers: a `post-commit` hook wired by `quest init --hooks` (no args --
    defaults to `HEAD`, i.e. the commit that was just made), and/or a
    timer/cron sweep that passes an explicit commit or range
    (`quest-apply-trailers HEAD~5..HEAD`) -- so this never assumes it's only
    ever invoked once per commit.

    Stateless idempotency, deliberately no synced state file: a transition to
    the status the quest already holds is a no-op, and a bare-mention `## Log`
    append dedupes on the commit's short sha already appearing in the quest's
    body -- so re-running the same commit (a re-triggered hook, an overlapping
    timer window) never double-applies or double-logs it.

    An unknown quest id, or a status token outside the target log's declared
    vocabulary, is a **warning** (printed, skipped) rather than a hard error --
    a code-repo commit should never be blocked by a typo'd or stale trailer
    (this hook cannot know whether the id will exist tomorrow after a
    Syncthing sync), and it's a `post-commit` hook besides: git does not treat
    its exit code as commit-blocking anyway.
    """
    refs = list(argv) if argv else ["HEAD"]
    cwd = Path.cwd()
    for sha in _resolve_commits(refs, cwd):
        _apply_commit_trailers(sha, cwd)
    return 0


def _resolve_commits(refs: list[str], cwd: Path) -> list[str]:
    """Each ref in `refs` -> one or more full commit shas.

    A `..`-containing ref is a range, expanded via `git rev-list` (the timer's
    use case: sweep everything since the last run). Anything else is a single
    commit-ish, resolved via `git rev-parse` (the hook's use case: `HEAD`).
    A ref that fails to resolve (bad range, repo with no commits yet) is
    silently skipped rather than raising -- a hook must never crash a commit.
    """
    shas: list[str] = []
    for ref in refs:
        args = ["git", "rev-list", ref] if ".." in ref else ["git", "rev-parse", ref]
        result = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
        if result.returncode != 0:
            continue
        shas.extend(line.strip() for line in result.stdout.splitlines() if line.strip())
    return shas


def _apply_commit_trailers(sha: str, cwd: Path) -> None:
    message = subprocess.run(
        ["git", "log", "-1", "--format=%B", sha], cwd=cwd, capture_output=True, text=True
    ).stdout
    short_sha = subprocess.run(
        ["git", "rev-parse", "--short", sha], cwd=cwd, capture_output=True, text=True
    ).stdout.strip() or sha[:7]

    for quest_id, token in _parse_quest_trailers(message, cwd):
        _apply_one_trailer(quest_id, token, short_sha, cwd)


def _parse_quest_trailers(message: str, cwd: Path) -> list[tuple[str, str | None]]:
    """The `Quest:` trailers in `message`, as `(quest_id, status_token_or_None)`.

    Delegates trailer detection entirely to `git interpret-trailers --parse`
    -- it alone decides what counts as the trailing key/value paragraph, so
    this never has to reimplement (or diverge from) git's own trailer rules.
    """
    result = subprocess.run(
        ["git", "interpret-trailers", "--parse"],
        input=message,
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    trailers: list[tuple[str, str | None]] = []
    for line in result.stdout.splitlines():
        key, sep, value = line.partition(":")
        if not sep or key.strip() != "Quest":
            continue
        parts = value.strip().split(None, 1)
        if not parts:
            continue
        quest_id = parts[0]
        token = parts[1].strip() if len(parts) > 1 else None
        trailers.append((quest_id, token or None))
    return trailers


def _apply_one_trailer(quest_id: str, token: str | None, short_sha: str, cwd: Path) -> None:
    found = resolve_mutation_target(quest_id, start=cwd)
    if found is None:
        print(f"[quest-apply-trailers] {short_sha}: unknown quest id '{quest_id}', skipping")
        return
    _quests_dir, path = found
    try:
        quest = Quest.load(path)
    except QuestFileError as exc:
        print(f"[quest-apply-trailers] {short_sha}: {exc}")
        return

    if token is None:
        _apply_mention(quest, short_sha)
        return

    statuses = _schema_for(path).statuses
    if token not in statuses:
        print(
            f"[quest-apply-trailers] {short_sha}: '{token}' is not a declared status for "
            f"{quest_id} (expected one of: {', '.join(statuses)}), skipping"
        )
        return

    if quest.get("status") == token:
        return  # already in this status -- no-op, stateless idempotency

    today_str = today()
    quest.set("status", token)
    quest.set("status_changed", today_str)
    quest.frontmatter["modified"] = today_str
    quest.save()
    print(f"[quest-apply-trailers] {quest_id}: status -> {token} ({short_sha})")


def _apply_mention(quest: Quest, short_sha: str) -> None:
    """`## Log` append for a bare (no status token) `Quest:` mention.

    Dedupes on the short sha already appearing anywhere in the body -- the
    only idempotency check available without a synced state file (QST-22gdn).
    """
    if short_sha in quest.body:
        return
    quest.append_log(f"mentioned in commit {short_sha}", today())
    quest.save()


if __name__ == "__main__":
    sys.exit(validate_main())
