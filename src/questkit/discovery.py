"""Resolve which quest log(s) a command should operate on."""

from __future__ import annotations

import fnmatch
import os
import sys
from pathlib import Path

from . import schema
from .config import CONFIG_FILENAME, ConfigVersionError, IgnoreConfigError, QuestLogConfig
from .gitutil import find_git_root
from .quest import find_by_id

QUEST_LOG_ENV = "QUEST_LOG"
QST_ROOT_ENV = "QST_ROOT"

# Baseline directory-name/glob patterns pruned during a cross-log sweep, an explicit named
# default list, not a dot-prefix heuristic. A log's own `.questkit.yaml` `ignore:`
# entries (see QuestLogConfig.resolved_ignores) extend this for its own subtree.
DEFAULT_IGNORE_DIRS = (
    ".git",
    ".stversions",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
)


class QuestLogNotFoundError(Exception):
    """Raised when no quest log can be resolved from any source."""


class AmbiguousDestinationError(QuestLogNotFoundError):
    """Raised when `quest new` can't tell which of several sub-logs to target."""


def resolve_log(explicit: str | None = None, start: Path | None = None) -> Path:
    """Resolve the `quests/` directory a command should operate on.

    Order: an explicit `--in` override (by name or by path -- see
    `resolve_by_name_or_path`), then walking up from `start` (default: cwd)
    looking for a `.questkit.yaml` marker -- either directly in an ancestor,
    or in that ancestor's `quests/` child -- then the `QUEST_LOG` environment
    variable, then an actionable error.

    An explicit value that resolves to more than one log (a directory holding
    several) is an `AmbiguousDestinationError` here -- this function always
    returns exactly one log, for the single-target commands (`show`, `set`,
    `done`, `mv`, `schema`, `new`, ...). A caller that wants every log beneath
    a directory (`list`, `logs`) calls `resolve_by_name_or_path` directly.
    """
    if explicit is not None:
        candidates = resolve_by_name_or_path(explicit, start=start)
        if len(candidates) > 1:
            raise AmbiguousDestinationError(
                f"'{explicit}' resolves to multiple quest logs: "
                f"{[str(p) for p in candidates]}. Specify one directly with --in <DIR>."
            )
        return candidates[0]

    found = _walk_up(start or Path.cwd())
    if found is not None:
        return found

    env_value = os.environ.get(QUEST_LOG_ENV)
    if env_value:
        env_path = Path(env_value).expanduser().resolve()
        if (env_path / CONFIG_FILENAME).is_file():
            return env_path
        raise QuestLogNotFoundError(
            f"QUEST_LOG='{env_path}' is not a quest log (no {CONFIG_FILENAME} found)."
        )

    raise QuestLogNotFoundError(
        "no quest log found: run 'quest init' here, or set QUEST_LOG to your central log."
    )


def resolve_by_name_or_path(
    value: str, root: Path | list[Path] | None = None, start: Path | None = None
) -> list[Path]:
    """One `--in` value -> the log(s) it names, by project name or by path.

    **One rule:** a value containing a `/` or `\\`, or naming a directory
    that exists on disk, is a **path**. Anything else is a **project name**,
    matched against each discovered log's `project:` under the sweep root(s)
    (`root` -- a single `Path` or a list, defaulting to
    `resolve_sweep_roots()`). Disk existence wins the tie: a directory named
    the same as a project resolves as the path, so an existing script never
    breaks the day a project name happens to collide with a real directory.

    A path that **is** a log resolves to just itself. A path that is **not**
    a log, but has logs somewhere beneath it, expands to all of them --
    `--in projects/app` behaves like
    `--in projects/app/quests`, and `--in .` from the top
    of a tree is honestly equivalent to `-A`. Callers that need exactly one log
    (write commands) reject more than one result themselves --
    `resolve_by_name_or_path` never picks for them.
    """
    if _looks_like_a_path(value):
        target = Path(value).expanduser().resolve()
        found = find_all_logs(target) if target.is_dir() else []
        if found:
            return found
        raise QuestLogNotFoundError(
            f"'{target}' is not a quest log (no {CONFIG_FILENAME} found). "
            f"Run 'quest init {target}' first."
        )

    roots = _as_root_list(root, start)
    logs = _dedupe_paths([log for r in roots for log in find_all_logs(r)])
    matches = [log for log in logs if _project_of(log) == value]
    if not matches:
        known = sorted(
            {(_project_of(log), log) for log in logs if _project_of(log) is not None}
        )
        listing = ", ".join(f"{name} ({path})" for name, path in known) or "(no named logs found)"
        roots_desc = ", ".join(str(r) for r in roots)
        raise QuestLogNotFoundError(
            f"no log named '{value}' under {roots_desc}. Known projects: {listing}. "
            "(The resolution set is device-dependent: a log not synced to this device "
            "cannot resolve here, even if its name is correct.)"
        )
    if len(matches) > 1:
        raise QuestLogNotFoundError(
            f"project name '{value}' matches {len(matches)} logs (a git worktree "
            f"checkout of the same project is the usual cause): {_listing(matches)}. "
            "Name one by path instead: --in <path>"
        )
    return matches


def _listing(paths: list[Path]) -> str:
    return "; ".join(str(p) for p in paths)


def project_collisions(logs: list[Path]) -> dict[str, list[Path]]:
    """`project:` names declared by more than one of `logs` -> those logs.

    Only named logs can collide; a log with no `project:` is never in a group.
    """
    by_project: dict[str, list[Path]] = {}
    for log in logs:
        project = _project_of(log)
        if project:
            by_project.setdefault(project, []).append(log)
    return {name: group for name, group in by_project.items() if len(group) > 1}


def project_labels(logs: list[Path]) -> dict[Path, str]:
    """A display label per log, unique across `logs`.

    The `project:` name (or the directory name for a nameless log), except
    where several logs share one name: those get `name (tail)`, where `tail`
    is the shortest trailing path that tells them apart -- so two checkouts of
    one project are never grouped under one indistinguishable header.
    """
    labels = {log: _project_of(log) or log.name for log in logs}
    for name, group in project_collisions(logs).items():
        depth = 2
        while depth < max(len(g.parts) for g in group):
            tails = {g: "/".join(g.parts[-depth:]) for g in group}
            if len(set(tails.values())) == len(group):
                break
            depth += 1
        for g in group:
            labels[g] = f"{name} ({'/'.join(g.parts[-depth:])})"
    return labels


def warn_project_collisions(logs: list[Path], prog: str) -> None:
    """Print one stderr warning per colliding project name, listing every log.

    Enumeration (`logs`, `list -A`, `doctor`, ...) warns and carries on; only
    single-log resolution refuses to guess (see `resolve_by_name_or_path`).
    """
    for name, group in sorted(project_collisions(logs).items()):
        print(
            f"[{prog}] warning: project '{name}' is declared by {len(group)} logs: "
            f"{_listing(group)} -- disambiguate with --in <path>",
            file=sys.stderr,
        )


def _as_root_list(root: Path | list[Path] | None, start: Path | None) -> list[Path]:
    if root is None:
        return resolve_sweep_roots(start=start)
    if isinstance(root, list):
        return root
    return [root]


def _looks_like_a_path(value: str) -> bool:
    return "/" in value or "\\" in value or Path(value).expanduser().is_dir()


def _project_of(quests_dir: Path) -> str | None:
    try:
        return QuestLogConfig.load(quests_dir).project
    except (OSError, ConfigVersionError, schema.SchemaExtendsError, schema.SchemaConfigError):
        return None


def _walk_up(start: Path) -> Path | None:
    current = start.resolve()
    while True:
        if (current / CONFIG_FILENAME).is_file():
            return current
        candidate = current / "quests"
        if (candidate / CONFIG_FILENAME).is_file():
            return candidate
        parent = current.parent
        if parent == current:
            return None
        current = parent


def resolve_log_for_new(explicit: str | None = None, start: Path | None = None) -> Path:
    """Like `resolve_log`, but guards against an ambiguous capture destination.

    Only `new` needs this -- `init` already takes an explicit target (or
    deterministically defaults to `./quests`), so it never relies on
    discovery. If no ancestor log is found via walk-up and 2+ quest logs
    exist somewhere downward from `start`, fail fast instead of silently
    falling back to `QUEST_LOG`: that fallback is fine with zero or one
    candidate, but silently picking one of several would be a real hazard.
    """
    if explicit is not None:
        return resolve_log(explicit=explicit)

    start = (start or Path.cwd()).resolve()
    found = _walk_up(start)
    if found is not None:
        return found

    siblings = find_all_logs(start)
    if len(siblings) > 1:
        raise AmbiguousDestinationError(
            "Ambiguous destination. Multiple quest logs found in subdirectories. "
            "Specify target with --in <DIR>."
        )
    return resolve_log(start=start)


def resolve_sweep_roots(
    explicit: list[str] | None = None, start: Path | None = None
) -> list[Path]:
    r"""Every root a cross-log sweep should start from, de-duplicated.

    Repeatable `--root`, else `QST_ROOT`, else the git root, else `start`/cwd.
    `QST_ROOT` splits on `os.pathsep` -- not `:`, since the Makefile targets
    Windows and `C:\` would shred a colon split.
    """
    if explicit:
        return _dedupe_paths([Path(v).expanduser().resolve() for v in explicit])
    env_value = os.environ.get(QST_ROOT_ENV)
    if env_value:
        parts = [v for v in env_value.split(os.pathsep) if v]
        if parts:
            return _dedupe_paths([Path(v).expanduser().resolve() for v in parts])
    start = (start or Path.cwd()).resolve()
    return [find_git_root(start) or start]


def resolve_sweep_root(explicit: str | None = None, start: Path | None = None) -> Path:
    """Single-root convenience wrapper around `resolve_sweep_roots`."""
    return resolve_sweep_roots(explicit=[explicit] if explicit else None, start=start)[0]


def resolve_log_set(
    in_dirs: list[str] | None = None,
    all_logs: bool = False,
    root: list[str] | None = None,
    start: Path | None = None,
) -> list[Path]:
    """The set of logs a command should operate on, from one of three sources.

    Explicit `--in` (repeatable, names or paths) wins, then `--all-logs`
    sweeping downward from the resolved root(s), then the default walk-up to
    a single log. One function rather than each command choosing between
    `resolve_log` and `find_all_logs` + `resolve_sweep_root` -- which is how
    those two paths drifted apart in the first place.

    `root` is itself repeatable (`--root` can be given more than once) and
    resolved paths are de-duplicated throughout: overlapping `--in` values,
    and overlapping `--root`s, would otherwise emit the same quest twice, and
    duplicate ids in a JSON export are a silent data bug.
    """
    if in_dirs:
        roots = resolve_sweep_roots(explicit=root, start=start)
        found: list[Path] = []
        for value in in_dirs:
            found.extend(resolve_by_name_or_path(value, root=roots, start=start))
        return _dedupe_paths(found)
    if all_logs:
        roots = resolve_sweep_roots(explicit=root, start=start)
        return _dedupe_paths([log for r in roots for log in find_all_logs(r)])
    return [resolve_log(start=start)]


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in paths:
        if path not in seen:
            seen.add(path)
            unique.append(path)
    return unique


def resolve_mutation_target(
    quest_id: str, explicit_in: str | list[str] | None = None, start: Path | None = None
) -> tuple[Path, Path] | None:
    """Find the (log dir, quest file) for a global quest id.

    An explicit `--in` (repeatable -- a single string or a list, names or
    paths) is a precise override, exactly as everywhere else in questkit:
    it's a bounded search set, and a miss there is a miss -- no silent sweep
    past it. Otherwise, the nearest log (today's walk-up) is checked first;
    if the id isn't there, every other log under `resolve_sweep_root()` is
    swept until it turns up somewhere.
    """
    if explicit_in is not None:
        values = [explicit_in] if isinstance(explicit_in, str) else explicit_in
        candidates = _dedupe_paths(
            [log for value in values for log in resolve_by_name_or_path(value, start=start)]
        )
        return _single_hit(quest_id, [(d, find_by_id(d, quest_id)) for d in candidates])

    start = (start or Path.cwd()).resolve()
    nearest = _walk_up(start)
    if nearest is not None:
        hit = find_by_id(nearest, quest_id)
        if hit is not None:
            return nearest, hit

    root = resolve_sweep_root(start=start)
    return _single_hit(
        quest_id, [(log, find_by_id(log, quest_id)) for log in find_all_logs(root) if log != nearest]
    )


def _single_hit(
    quest_id: str, probes: list[tuple[Path, Path | None]]
) -> tuple[Path, Path] | None:
    """The one (log, file) holding `quest_id`; two or more is an error, never a pick."""
    hits = [(log, path) for log, path in probes if path is not None]
    if len(hits) > 1:
        raise QuestLogNotFoundError(
            f"id '{quest_id}' exists in {len(hits)} logs: {_listing([p for _, p in hits])}. "
            "Name one by path instead: --in <path>"
        )
    return hits[0] if hits else None


def find_all_logs(root: Path) -> list[Path]:
    """Every directory containing `.questkit.yaml`, by recursive descent from root.

    Pruning starts from `DEFAULT_IGNORE_DIRS`. A log's own `ignore:` config
    extends the active prune set for its own project -- in practice that
    means its *parent* directory's tree too (the common shape is
    `project/quests/.questkit.yaml` declaring ignores for sibling dirs like
    `project/dist`), not just descendants of the log directory itself. A
    one-level lookahead at each directory catches a `quests`-shaped child's
    config before deciding whether to prune its siblings, so declaration
    order (e.g. `dist` sorting before `quests`) doesn't matter.
    """
    root = root.resolve()
    logs: list[Path] = []
    _find_logs(root, list(DEFAULT_IGNORE_DIRS), logs, {})
    return sorted(logs)


def _find_logs(
    directory: Path, ignore_patterns: list[str], logs: list[Path], ignore_cache: dict
) -> None:
    if (directory / CONFIG_FILENAME).is_file():
        logs.append(directory)
        ignore_patterns = ignore_patterns + _cached_local_ignores(directory, ignore_cache)

    try:
        entries = sorted(e for e in directory.iterdir() if e.is_dir() and not e.is_symlink())
    except OSError:
        return

    for entry in entries:
        if (entry / CONFIG_FILENAME).is_file():
            ignore_patterns = ignore_patterns + _cached_local_ignores(entry, ignore_cache)

    for entry in entries:
        if _is_ignored(entry.name, ignore_patterns):
            continue
        _find_logs(entry, ignore_patterns, logs, ignore_cache)


def _cached_local_ignores(quests_dir: Path, cache: dict) -> list[str]:
    if quests_dir not in cache:
        cache[quests_dir] = _local_ignores(quests_dir)
    return cache[quests_dir]


def _local_ignores(quests_dir: Path) -> list[str]:
    """Best-effort: a log's own extra ignore patterns for its own subtree.

    A broken config *anywhere* encountered during a broad cross-log sweep
    (future config version, broken schema `extends`, broken `ignore:`
    `#include`) shouldn't abort the whole sweep -- that one log just
    contributes no extra pruning. It's not swallowed silently, though: a
    warning is printed so the misconfiguration stays visible.
    """
    try:
        return QuestLogConfig.load(quests_dir).resolved_ignores(quests_dir)
    except (OSError, ConfigVersionError, schema.SchemaExtendsError, IgnoreConfigError) as exc:
        print(f"[quest] warning: {quests_dir}: {exc}", file=sys.stderr)
        return []


def _is_ignored(name: str, patterns: list[str]) -> bool:
    for raw in patterns:
        pattern = raw.strip()
        if pattern.startswith("**/"):
            pattern = pattern[3:]
        pattern = pattern.rstrip("/")
        if fnmatch.fnmatch(name, pattern):
            return True
    return False
