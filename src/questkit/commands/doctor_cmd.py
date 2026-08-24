"""`quest doctor [--root DIR ...] [--format text|json]` — read-only diagnosis
pass over the environment, quest logs, and questkit's own installs
(QST-whcdp).

Deliberately the environmental counterpart to `quest validate`: `validate`
checks one log's quest *content* against its schema; `doctor` checks
everything *around* the logs that `validate` never sees — duplicate ids
across logs, Syncthing conflict litter, orphaned files, broken configs,
stale hook pins, install sanity, env sanity, and generated-artifact drift.
Read-only throughout: it never writes a file, same posture as `validate`.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .. import schema
from ..config import CONFIG_FILENAME, ConfigVersionError, QuestLogConfig
from ..discovery import (
    DEFAULT_IGNORE_DIRS,
    QST_ROOT_ENV,
    QUEST_LOG_ENV,
    find_all_logs,
    resolve_sweep_roots,
)
from ..quest import count_sync_conflicts, glob_quests, load_frontmatter_only

# Broad enough to catch any log's `ID-xxxxx--slug.md` naming (id prefixes
# other than `QST-` are legal -- `config.prefix` is per-log), without
# matching arbitrary Markdown files that just happen to live near a log.
_QUEST_FILE_RE = re.compile(r"^[A-Z][A-Za-z0-9]*-[0-9a-z]{4,}(--.*)?\.md$")

_HOOK_IDS = {"quest-format", "quest-validate", "quest-bump-modified"}


@dataclass
class Finding:
    """One `doctor` problem -- shaped like `validate`'s JSON finding (QST-njwu7),
    so both commands' `--format json` output reads the same way to a caller."""

    check: str
    message: str
    path: str | None = None

    def as_dict(self) -> dict:
        return {"file": self.path, "id": None, "kind": "problem", "rule": self.check, "message": self.message}


def run(args: argparse.Namespace) -> int:
    roots = resolve_sweep_roots(explicit=getattr(args, "root", None))
    logs = _dedupe_paths([log for root in roots for log in find_all_logs(root)])

    findings: list[Finding] = []
    findings += _check_duplicate_ids(logs)
    findings += _check_sync_conflicts(logs)
    findings += _check_orphaned_files(roots, logs)
    findings += _check_broken_configs(logs)
    findings += _check_stale_hook_pins(roots)
    findings += _check_install_sanity()
    findings += _check_env_sanity()
    findings += _check_artifact_drift(logs)

    as_json = getattr(args, "format", "text") == "json"
    if as_json:
        print(
            json.dumps(
                {
                    "findings": [f.as_dict() for f in findings],
                    "summary": {"logs_checked": len(logs), "problems": len(findings)},
                },
                indent=2,
            )
        )
    else:
        if not findings:
            print(f"[quest doctor] {len(logs)} log(s) checked, no problems found")
        else:
            for f in findings:
                where = f" ({f.path})" if f.path else ""
                print(f"[quest doctor] [{f.check}] {f.message}{where}")
            print(f"[quest doctor] {len(logs)} log(s) checked, {len(findings)} problem(s) found")

    return 1 if findings else 0


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in paths:
        if path not in seen:
            seen.add(path)
            unique.append(path)
    return unique


# --- 1. duplicate ids across logs -------------------------------------------


def _check_duplicate_ids(logs: list[Path]) -> list[Finding]:
    by_id: dict[str, list[Path]] = {}
    for log in logs:
        config = _load_config_quietly(log)
        if config is None:
            continue
        for path in glob_quests(log, config.pattern):
            try:
                frontmatter = load_frontmatter_only(path)
            except Exception:
                continue
            quest_id = str(frontmatter.get("id") or path.stem.partition("--")[0])
            by_id.setdefault(quest_id, []).append(path)

    findings = []
    for quest_id, paths in sorted(by_id.items()):
        if len(paths) > 1:
            listing = ", ".join(str(p) for p in sorted(paths))
            findings.append(Finding("duplicate-id", f"id '{quest_id}' used by {len(paths)} files: {listing}"))
    return findings


# --- 2. Syncthing conflict copies present -----------------------------------


def _check_sync_conflicts(logs: list[Path]) -> list[Finding]:
    findings = []
    for log in logs:
        config = _load_config_quietly(log)
        if config is None:
            continue
        conflicts = count_sync_conflicts(log, config.pattern)
        if conflicts:
            findings.append(
                Finding(
                    "sync-conflict",
                    f"{conflicts} sync-conflict copies present -- resolve by hand",
                    str(log),
                )
            )
    return findings


# --- 3. orphaned quest files outside any log --------------------------------


def _check_orphaned_files(roots: list[Path], logs: list[Path]) -> list[Finding]:
    log_set = set(logs)
    seen: set[Path] = set()
    findings: list[Finding] = []
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            # `.stversions` is deliberately walked (unlike `find_all_logs`'s
            # sweep) -- an orphaned quest file left behind in a Syncthing
            # version archive is exactly the case this check exists to
            # surface (plan v3 §14).
            dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules", "__pycache__", ".venv", "venv", ".ruff_cache", ".pytest_cache")]
            current = Path(dirpath)
            if current in log_set:
                continue
            for name in filenames:
                if not _QUEST_FILE_RE.match(name):
                    continue
                path = current / name
                if path in seen:
                    continue
                seen.add(path)
                findings.append(Finding("orphaned-quest-file", "quest-shaped file outside any log", str(path)))
    return findings


# --- 4. broken log configs, aggregated --------------------------------------


def _check_broken_configs(logs: list[Path]) -> list[Finding]:
    findings = []
    for log in logs:
        try:
            QuestLogConfig.load(log)
        except (ConfigVersionError, schema.SchemaExtendsError, schema.SchemaConfigError, OSError) as exc:
            findings.append(Finding("broken-config", str(exc), str(log)))
    return findings


def _load_config_quietly(log: Path) -> QuestLogConfig | None:
    try:
        return QuestLogConfig.load(log)
    except (ConfigVersionError, schema.SchemaExtendsError, schema.SchemaConfigError, OSError):
        return None


# --- 5. stale hook pins ------------------------------------------------------


def _check_stale_hook_pins(roots: list[Path]) -> list[Finding]:
    from ruamel.yaml import YAML

    yaml = YAML(typ="safe")
    findings: list[Finding] = []
    seen: set[Path] = set()
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in DEFAULT_IGNORE_DIRS]
            if ".pre-commit-config.yaml" not in filenames:
                continue
            cfg_path = Path(dirpath) / ".pre-commit-config.yaml"
            if cfg_path in seen:
                continue
            seen.add(cfg_path)
            try:
                data = yaml.load(cfg_path.read_text(encoding="utf-8")) or {}
            except Exception:
                continue
            for repo in data.get("repos") or []:
                hook_ids = {h.get("id") for h in (repo.get("hooks") or [])}
                if not hook_ids & _HOOK_IDS:
                    continue
                repo_ref = repo.get("repo")
                rev = repo.get("rev")
                if not repo_ref or not rev or "://" in repo_ref or repo_ref.startswith("git@"):
                    continue  # not a local checkout this machine can compare against
                repo_path = Path(repo_ref).expanduser()
                if not repo_path.is_dir():
                    continue
                actual = _git_head(repo_path)
                if actual and actual != rev:
                    findings.append(
                        Finding(
                            "stale-hook-pin",
                            f"pinned rev '{rev}' does not match questkit HEAD '{actual}'",
                            str(cfg_path),
                        )
                    )
    return findings


def _git_head(repo_root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, check=True, capture_output=True, text=True
        )
    except (subprocess.CalledProcessError, OSError):
        return None
    return result.stdout.strip()


# --- 6. install sanity -------------------------------------------------------


def _check_install_sanity() -> list[Finding]:
    findings: list[Finding] = []
    findings += _check_editable_install()
    findings += _check_shared_venv_version_agreement()
    return findings


def _check_editable_install() -> list[Finding]:
    try:
        import importlib.metadata as importlib_metadata

        dist = importlib_metadata.distribution("questkit")
    except Exception:
        return [Finding("install", "questkit package metadata not found")]

    try:
        direct_url_text = dist.read_text("direct_url.json")
    except Exception:
        direct_url_text = None
    if not direct_url_text:
        return []
    try:
        data = json.loads(direct_url_text)
    except ValueError:
        return []
    editable = (data.get("dir_info") or {}).get("editable")
    url = data.get("url", "")
    if not editable or not url.startswith("file://"):
        return []
    install_path = Path(url[len("file://") :])
    if not install_path.exists():
        return [Finding("install", f"editable install path missing: {install_path}")]
    return []


def _check_shared_venv_version_agreement() -> list[Finding]:
    """The `quest` on PATH (a uv-tool/shared-venv install) vs this process's own version.

    Best-effort: a missing binary, a timeout, or an unparsable version string
    all degrade to "nothing to compare" rather than a false positive --
    this check exists for the fleet-drift case, not to police every dev box.
    """
    quest_bin = shutil.which("quest")
    if not quest_bin:
        return []
    try:
        result = subprocess.run([quest_bin, "--version"], capture_output=True, text=True, timeout=5)
        installed_version = result.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return []
    if not installed_version:
        return []

    from .. import __version__

    this_version = f"questkit {__version__}"
    if installed_version != this_version:
        return [
            Finding(
                "install",
                f"`quest` on PATH reports '{installed_version}', but this process's "
                f"questkit is '{this_version}'",
                quest_bin,
            )
        ]
    return []


# --- 7. env sanity ------------------------------------------------------------


def _check_env_sanity() -> list[Finding]:
    findings: list[Finding] = []
    quest_log = os.environ.get(QUEST_LOG_ENV)
    if quest_log:
        path = Path(quest_log).expanduser()
        if not (path / CONFIG_FILENAME).is_file():
            findings.append(Finding("env", f"{QUEST_LOG_ENV}='{quest_log}' is not a quest log (no {CONFIG_FILENAME})"))

    qst_root = os.environ.get(QST_ROOT_ENV)
    if qst_root:
        for part in qst_root.split(os.pathsep):
            if part and not Path(part).expanduser().is_dir():
                findings.append(Finding("env", f"{QST_ROOT_ENV} entry '{part}' is not a directory"))
    return findings


# --- 8. generated-artifact drift ----------------------------------------------


def _check_artifact_drift(logs: list[Path]) -> list[Finding]:
    """`_template.md`/`quests.base` older than the `.questkit.yaml` that
    generates them -- the direct case (extends-chain files are not walked;
    see the quest's own scope notes)."""
    findings = []
    for log in logs:
        config_path = log / CONFIG_FILENAME
        try:
            config_mtime = config_path.stat().st_mtime
        except OSError:
            continue
        for name, regen_hint in (
            ("_template.md", "quest init --template"),
            ("quests.base", "quest init --base"),
        ):
            artifact_path = log / name
            if artifact_path.is_file() and artifact_path.stat().st_mtime < config_mtime:
                findings.append(
                    Finding(
                        "artifact-drift",
                        f"{name} is older than {CONFIG_FILENAME} -- regenerate with `{regen_hint}`",
                        str(artifact_path),
                    )
                )
    return findings
