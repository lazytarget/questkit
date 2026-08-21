"""`quest init` — opt a directory into being (or extending) a quest log."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from ..config import CONFIG_FILENAME, QuestLogConfig, config_exists
from ..gitutil import find_git_root
from ..templates import generate_template


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

    _ensure_gitignore(target)

    if args.base:
        _init_base(target)
    if args.hooks:
        _init_hooks(target)
    if getattr(args, "template", False):
        _init_template(target)

    return 0


def _init_template(target: Path) -> None:
    """Regenerated every call -- a build artifact, like `quests.base`, not a
    hand-maintained file someone edits and then loses on the next `--template`."""
    config = QuestLogConfig.load(target)
    template_path = target / "_template.md"
    template_path.write_text(generate_template(config), encoding="utf-8")
    print(f"[quest init] {template_path}: wrote Obsidian capture template")


def _ensure_gitignore(target: Path) -> None:
    """`_validation.md` (`quest validate --report`) is derived state whose
    transport is Syncthing, not git -- and several real logs are their own
    git repos with no `.gitignore` at all, so without this it sits untracked
    forever, waiting for the first `git add -A`."""
    gitignore = target / ".gitignore"
    entry = "_validation.md"
    if gitignore.is_file():
        text = gitignore.read_text(encoding="utf-8")
        if entry in [line.strip() for line in text.splitlines()]:
            return
        needs_newline = bool(text) and not text.endswith("\n")
        with gitignore.open("a", encoding="utf-8") as handle:
            handle.write(("\n" if needs_newline else "") + f"{entry}\n")
    else:
        gitignore.write_text(f"{entry}\n", encoding="utf-8")
        print(f"[quest init] {gitignore}: created, ignoring {entry}")


def _resolve_target(dir_arg: str | None) -> Path:
    base = Path(dir_arg).expanduser().resolve() if dir_arg else Path.cwd()
    return base if base.name == "quests" else base / "quests"


_BASE_TEMPLATE_PATH = Path(__file__).resolve().parents[2] / "templates" / "quests.base"


def _init_base(target: Path) -> None:
    base_path = target / "quests.base"
    base_path.write_text(_BASE_TEMPLATE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
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
        "      - id: quest-format\n"
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
