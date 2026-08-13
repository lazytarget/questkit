"""`quest init` — opt a directory into being (or extending) a quest log."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from ..config import CONFIG_FILENAME, QuestLogConfig, config_exists
from ..gitutil import find_git_root


def run(args: argparse.Namespace) -> int:
    target = _resolve_target(args.dir)
    created_dir = not target.exists()
    target.mkdir(parents=True, exist_ok=True)

    if config_exists(target):
        print(f"[quest init] {target}: already a quest log, leaving {CONFIG_FILENAME} untouched")
    else:
        QuestLogConfig(project=args.project, git=args.git or "manual").save(target)
        print(f"[quest init] {target}: wrote {CONFIG_FILENAME}")

    if created_dir:
        print(f"[quest init] {target}: created quests directory")

    if args.base:
        _init_base(target)
    if args.hooks:
        _init_hooks(target)

    return 0


def _resolve_target(dir_arg: str | None) -> Path:
    base = Path(dir_arg).expanduser().resolve() if dir_arg else Path.cwd()
    return base if base.name == "quests" else base / "quests"


def _init_base(target: Path) -> None:
    base_path = target / "quests.base"
    if base_path.exists():
        print(f"[quest init] {base_path}: already exists, skipping --base")
        return
    base_path.write_text(_BASE_TEMPLATE, encoding="utf-8")
    print(f"[quest init] {base_path}: wrote Obsidian Bases view")


def _init_hooks(target: Path) -> None:
    zone_root = find_git_root(target)
    if zone_root is None:
        print(f"[quest init] {target}: not inside a git repo, skipping --hooks")
        return

    pre_commit_config = zone_root / ".pre-commit-config.yaml"
    entry = _hook_repo_entry()

    if pre_commit_config.exists():
        text = pre_commit_config.read_text(encoding="utf-8")
        if "questkit" in text or "quest-validate" in text:
            print(f"[quest init] {pre_commit_config}: questkit hooks already present, skipping")
            return
        with pre_commit_config.open("a", encoding="utf-8") as handle:
            handle.write(entry)
        print(f"[quest init] {pre_commit_config}: appended questkit hooks")
    else:
        pre_commit_config.write_text(f"repos:\n{entry}", encoding="utf-8")
        print(f"[quest init] {pre_commit_config}: created with questkit hooks")

    try:
        subprocess.run(["pre-commit", "install"], cwd=zone_root, check=True, capture_output=True)
        print(f"[quest init] {zone_root}: pre-commit hook installed")
    except FileNotFoundError:
        print("[quest init] 'pre-commit' is not installed; hooks configured but not activated")
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode(errors="replace").strip() if exc.stderr else str(exc)
        print(f"[quest init] 'pre-commit install' failed: {stderr}")


def _hook_repo_entry() -> str:
    repo_root = _questkit_repo_root()
    if repo_root is None:
        repo_ref = "<path-to-your-questkit-checkout>"
        rev = "HEAD"
    else:
        repo_ref = str(repo_root)
        rev = _git_head(repo_root) or "HEAD"
        if rev == "HEAD":
            print(
                "[quest init] questkit has no commits yet; pinning to 'HEAD' for now -- "
                "re-run --hooks after committing questkit for a real pinned rev"
            )
    return (
        f"  - repo: {repo_ref}\n"
        f"    rev: {rev}\n"
        "    hooks:\n"
        "      - id: quest-validate\n"
        "      - id: quest-bump-modified\n"
    )


def _questkit_repo_root() -> Path | None:
    import questkit

    return find_git_root(Path(questkit.__file__).resolve().parent)


def _git_head(repo_root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError:
        return None
    return result.stdout.strip()


_BASE_TEMPLATE = """\
# Obsidian Bases view for this quest log. Bases is a fairly new Obsidian
# file format -- treat this as a starting point and adjust once opened.
views:
  - type: table
    name: Kanban
    groupBy: status
    order:
      - status
      - title
      - priority
      - type
      - project
  - type: table
    name: By priority
    order:
      - priority
      - title
      - status
      - type
    sort:
      - property: priority
"""
