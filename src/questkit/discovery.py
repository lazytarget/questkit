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

# Baseline directory-name/glob patterns pruned during a cross-log sweep, mirroring
# 99-system/metadata/frontmatter.schema.yaml's `skip_dirs` -- an explicit named
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
    value: str, root: Path | None = None, start: Path | None = None
) -> list[Path]:
    """One `--in` value -> the log(s) it names, by project name or by path.

    **One rule:** a value containing a `/` or `\\`, or naming a directory
    that exists on disk, is a **path**. Anything else is a **project name**,
    matched against each discovered log's `project:` under the sweep root
    (`root`, or `resolve_sweep_root()` if not given). Disk existence wins the
    tie: a directory named the same as a project resolves as the path, so an
    existing script never breaks the day a project name happens to collide
    with a real directory.

    A path that **is** a log resolves to just itself. A path that is **not**
    a log, but has logs somewhere beneath it, expands to all of them --
    `--in 02-projects/grocy-ecosystem` behaves like
    `--in 02-projects/grocy-ecosystem/quests`, and `--in .` from the Realm
    root is honestly equivalent to `-A`. Callers that need exactly one log
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

    sweep_root = root if root is not None else resolve_sweep_root(start=start)
    logs = find_all_logs(sweep_root)
    matches = [log for log in logs if _project_of(log) == value]
    if not matches:
        known = sorted(
            {(_project_of(log), log) for log in logs if _project_of(log) is not None}
        )
        listing = ", ".join(f"{name} ({path})" for name, path in known) or "(no named logs found)"
        raise QuestLogNotFoundError(
            f"no log named '{value}' under {sweep_root}. Known projects: {listing}. "
            "(The resolution set is device-dependent: a log not synced to this device "
            "cannot resolve here, even if its name is correct.)"
        )
    if len(matches) > 1:
        raise QuestLogNotFoundError(
            f"project name '{value}' matches multiple logs: {[str(m) for m in matches]} -- "
            "each log's project: must be unique; fix the duplicate and retry"
        )
    return matches


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


def resolve_sweep_root(explicit: str | None = None, start: Path | None = None) -> Path:
    """The root a cross-log sweep starts from.

    Explicit override, else `QST_ROOT`, else the git root, else `start`/cwd --
    "sweeps downward from QST_ROOT (or the Git root)", with a cwd fallback so
    standalone (non-Realm) use still works.
    """
    if explicit:
        return Path(explicit).expanduser().resolve()
    env_value = os.environ.get(QST_ROOT_ENV)
    if env_value:
        return Path(env_value).expanduser().resolve()
    start = (start or Path.cwd()).resolve()
    return find_git_root(start) or start


def resolve_log_set(
    in_dirs: list[str] | None = None,
    all_logs: bool = False,
    root: str | None = None,
    start: Path | None = None,
) -> list[Path]:
    """The set of logs a command should operate on, from one of three sources.

    Explicit `--in` (repeatable) wins, then `--all-logs` sweeping downward
    from the resolved root, then the default walk-up to a single log. One
    function rather than each command choosing between `resolve_log` and
    `find_all_logs` + `resolve_sweep_root` -- which is how those two paths
    drifted apart in the first place.

    Resolved paths are de-duplicated: overlapping `--in` values, and (once
    `--root` is repeatable) nested roots, would otherwise emit the same quest
    twice, and duplicate ids in a JSON export are a silent data bug.

    Lands with `quest migrate`, its first consumer. QST-iqwjm extends it with
    project-name resolution (QST-fmk0p), repeatable `--root`, and the summary
    block that reports the resolved scope.
    """
    if in_dirs:
        sweep_root = resolve_sweep_root(explicit=root, start=start)
        found: list[Path] = []
        for value in in_dirs:
            found.extend(resolve_by_name_or_path(value, root=sweep_root))
        return _dedupe_paths(found)
    if all_logs:
        return find_all_logs(resolve_sweep_root(explicit=root, start=start))
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
    quest_id: str, explicit_in: str | None = None, start: Path | None = None
) -> tuple[Path, Path] | None:
    """Find the (log dir, quest file) for a global quest id.

    An explicit `--in` is a precise override, exactly as everywhere else in
    questkit: it's the only place searched, and a miss there is a miss -- no
    silent sweep past it. Otherwise, the nearest log (today's walk-up) is
    checked first; if the id isn't there, every other log under
    `resolve_sweep_root()` is swept until it turns up somewhere.
    """
    if explicit_in is not None:
        quests_dir = resolve_log(explicit=explicit_in)
        hit = find_by_id(quests_dir, quest_id)
        return (quests_dir, hit) if hit is not None else None

    start = (start or Path.cwd()).resolve()
    nearest = _walk_up(start)
    if nearest is not None:
        hit = find_by_id(nearest, quest_id)
        if hit is not None:
            return nearest, hit

    root = resolve_sweep_root(start=start)
    for log in find_all_logs(root):
        if log == nearest:
            continue
        hit = find_by_id(log, quest_id)
        if hit is not None:
            return log, hit
    return None


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
