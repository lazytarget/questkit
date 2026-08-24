"""Tests for `scripts/release.py` (QST-cv23q): the tag-and-push release ritual.

Real git repos (`tmp_path`, actually `git init`-ed) exercise dirty-tree and
existing-tag detection for real; changelog assembly makes a real in-process
call into `quest list --format md` (QST-f6otu) against a fixture quest log.
Only the parts that would genuinely touch a remote -- `create_and_push_tag`
-- are stubbed, and only in the orchestration (`run`) tests.
"""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "release.py"
_spec = importlib.util.spec_from_file_location("questkit_release_script", _SCRIPT_PATH)
release = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = release
_spec.loader.exec_module(release)


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(["init"], repo)
    _git(["config", "user.email", "test@example.com"], repo)
    _git(["config", "user.name", "Test"], repo)
    (repo / "README.md").write_text("hi\n", encoding="utf-8")
    _git(["add", "README.md"], repo)
    _git(["commit", "-m", "init"], repo)
    return repo


def _write_pyproject(repo: Path, version: str) -> None:
    (repo / "pyproject.toml").write_text(
        f'[project]\nname = "questkit"\nversion = "{version}"\n', encoding="utf-8"
    )


def _args(repo: Path, **overrides) -> argparse.Namespace:
    defaults = dict(yes=True, dry_run=False, remote="origin", repo_root=repo, quests_dir=None)
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


# --- version agreement -------------------------------------------------------------


def test_read_pyproject_version_reads_project_table(tmp_path):
    _write_pyproject(tmp_path, "1.2.3")

    assert release.read_pyproject_version(tmp_path) == "1.2.3"


def test_read_pyproject_version_raises_without_version_key(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n', encoding="utf-8")

    with pytest.raises(release.ReleaseError):
        release.read_pyproject_version(tmp_path)


def test_check_version_agreement_passes_when_equal():
    release.check_version_agreement("0.4.0", "0.4.0")  # no raise


def test_check_version_agreement_raises_on_drift():
    with pytest.raises(release.ReleaseError, match=r"0\.4\.0.*0\.3\.0|0\.3\.0.*0\.4\.0"):
        release.check_version_agreement("0.4.0", "0.3.0")


# --- dirty tree / existing tag ------------------------------------------------------


def test_is_working_tree_dirty_false_on_clean_repo(tmp_path):
    repo = _init_repo(tmp_path)

    assert release.is_working_tree_dirty(repo) is False


def test_is_working_tree_dirty_true_with_untracked_file(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "scratch.txt").write_text("x", encoding="utf-8")

    assert release.is_working_tree_dirty(repo) is True


def test_is_working_tree_dirty_true_with_unstaged_edit(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "README.md").write_text("changed\n", encoding="utf-8")

    assert release.is_working_tree_dirty(repo) is True


def test_tag_exists_false_when_absent(tmp_path):
    repo = _init_repo(tmp_path)

    assert release.tag_exists(repo, "v9.9.9") is False


def test_tag_exists_true_after_tagging(tmp_path):
    repo = _init_repo(tmp_path)
    _git(["tag", "v1.0.0"], repo)

    assert release.tag_exists(repo, "v1.0.0") is True


# --- milestone completeness + changelog assembly (real `quest list`) ---------------


def _milestone_schema():
    return {"fields": {"milestone": {"type": "string"}}}


def test_offending_non_terminal_quests_lists_unfinished_ones(isolated, make_log, write_quest):
    log = make_log(isolated, schema=_milestone_schema())
    write_quest(log, "QST-aaaaa", title="Done one", status="done", type="feature", milestone="0.4.0")
    write_quest(log, "QST-bbbbb", title="Still open", status="todo", type="bug", milestone="0.4.0")
    write_quest(log, "QST-ccccc", title="Other milestone", status="todo", type="bug", milestone="0.5.0")

    offenders = release.offending_non_terminal_quests(log, "0.4.0")

    assert offenders == [{"id": "QST-bbbbb", "status": "todo"}]


def test_offending_non_terminal_quests_empty_when_all_terminal(isolated, make_log, write_quest):
    log = make_log(isolated, schema=_milestone_schema())
    write_quest(log, "QST-aaaaa", title="Done", status="done", type="feature", milestone="0.4.0")
    write_quest(log, "QST-bbbbb", title="Scrapped", status="scrapped", type="bug", milestone="0.4.0")

    assert release.offending_non_terminal_quests(log, "0.4.0") == []


def test_render_changelog_section_groups_by_type_category(isolated, make_log, write_quest):
    log = make_log(isolated, schema=_milestone_schema())
    write_quest(log, "QST-aaaaa", title="New thing", status="done", type="feature", milestone="0.4.0")
    write_quest(log, "QST-bbbbb", title="Squashed bug", status="done", type="bug", milestone="0.4.0")
    write_quest(log, "QST-ccccc", title="Tidy up", status="scrapped", type="chore", milestone="0.4.0")
    write_quest(log, "QST-ddddd", title="Still open", status="todo", type="feature", milestone="0.4.0")
    write_quest(log, "QST-eeeee", title="Other milestone", status="done", type="feature", milestone="0.5.0")

    section = release.render_changelog_section(log, "0.4.0")

    assert section.index("### Added") < section.index("### Fixed") < section.index("### Changed")
    assert "**QST-aaaaa** New thing" in section
    assert "**QST-bbbbb** Squashed bug" in section
    assert "**QST-ccccc** Tidy up" in section
    assert "QST-ddddd" not in section  # not terminal
    assert "QST-eeeee" not in section  # different milestone


def test_render_changelog_section_omits_empty_categories(isolated, make_log, write_quest):
    log = make_log(isolated, schema=_milestone_schema())
    write_quest(log, "QST-aaaaa", title="Only a feature", status="done", type="feature", milestone="0.4.0")

    section = release.render_changelog_section(log, "0.4.0")

    assert "### Added" in section
    assert "### Fixed" not in section
    assert "### Changed" not in section


def test_render_changelog_section_no_changes_placeholder(isolated, make_log):
    log = make_log(isolated, schema=_milestone_schema())

    section = release.render_changelog_section(log, "0.4.0")

    assert section == "_(no changes)_"


# --- CHANGELOG.md writing -----------------------------------------------------------


def test_write_changelog_creates_file_when_missing(tmp_path):
    path = tmp_path / "CHANGELOG.md"

    release.write_changelog(path, "0.1.0", "### Added\n\n- **QST-aaaaa** Thing", today=date(2026, 1, 1))

    text = path.read_text(encoding="utf-8")
    assert text.startswith("# Changelog\n\n")
    assert "## [0.1.0] — 2026-01-01" in text
    assert "### Added" in text


def test_write_changelog_inserts_new_section_above_existing(tmp_path):
    path = tmp_path / "CHANGELOG.md"
    path.write_text(
        "# Changelog\n\nSome preamble.\n\n## [0.2.0] — 2026-01-01\n\nold stuff\n",
        encoding="utf-8",
    )

    release.write_changelog(path, "0.3.0", "### Added\n\n- **QST-x** New", today=date(2026, 2, 1))

    text = path.read_text(encoding="utf-8")
    assert text.index("## [0.3.0]") < text.index("## [0.2.0]")
    assert "old stuff" in text
    assert "Some preamble." in text


# --- orchestration -------------------------------------------------------------------


def _seed_quest_log(repo: Path, make_log) -> Path:
    return make_log(repo, schema=_milestone_schema())


def test_run_refuses_on_version_drift(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    _write_pyproject(repo, "0.4.0")
    _git(["add", "pyproject.toml"], repo)
    _git(["commit", "-m", "bump"], repo)
    monkeypatch.setattr(release, "installed_version", lambda: "0.3.0")

    with pytest.raises(release.ReleaseError, match=r"0\.4\.0"):
        release.run(_args(repo))


def test_run_refuses_on_dirty_tree(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    _write_pyproject(repo, "0.4.0")
    _git(["add", "pyproject.toml"], repo)
    _git(["commit", "-m", "bump"], repo)
    monkeypatch.setattr(release, "installed_version", lambda: "0.4.0")
    (repo / "dirty.txt").write_text("x", encoding="utf-8")

    with pytest.raises(release.ReleaseError, match="dirty"):
        release.run(_args(repo))


def test_run_refuses_on_existing_tag(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    _write_pyproject(repo, "0.4.0")
    _git(["add", "pyproject.toml"], repo)
    _git(["commit", "-m", "bump"], repo)
    _git(["tag", "v0.4.0"], repo)
    monkeypatch.setattr(release, "installed_version", lambda: "0.4.0")

    with pytest.raises(release.ReleaseError, match=r"v0\.4\.0"):
        release.run(_args(repo))


def test_run_refuses_on_non_terminal_milestone_quests(tmp_path, monkeypatch, make_log):
    repo = _init_repo(tmp_path)
    _write_pyproject(repo, "0.4.0")
    quests_dir = _seed_quest_log(repo, make_log)
    _git(["add", "-A"], repo)
    _git(["commit", "-m", "bump + log"], repo)
    monkeypatch.setattr(release, "installed_version", lambda: "0.4.0")

    from questkit.cli import main as quest_main

    assert quest_main([
        "new", "Unfinished", "--in", str(quests_dir), "--type", "feature",
        "--status", "todo", "--set", "milestone=0.4.0",
    ]) == 0
    _git(["add", "-A"], repo)
    _git(["commit", "-m", "add quest"], repo)

    with pytest.raises(release.ReleaseError, match="non-terminal"):
        release.run(_args(repo))


def test_run_dry_run_prints_section_and_does_not_write_or_tag(tmp_path, monkeypatch, capsys, make_log):
    repo = _init_repo(tmp_path)
    _write_pyproject(repo, "0.4.0")
    quests_dir = _seed_quest_log(repo, make_log)
    _git(["add", "-A"], repo)
    _git(["commit", "-m", "bump + log"], repo)
    monkeypatch.setattr(release, "installed_version", lambda: "0.4.0")

    from questkit.cli import main as quest_main

    assert quest_main([
        "new", "Shipped", "--in", str(quests_dir), "--type", "feature",
        "--status", "done", "--set", "milestone=0.4.0",
    ]) == 0
    _git(["add", "-A"], repo)
    _git(["commit", "-m", "add quest"], repo)

    def _boom(*a, **k):
        raise AssertionError("create_and_push_tag must not be called on --dry-run")

    monkeypatch.setattr(release, "create_and_push_tag", _boom)

    release.run(_args(repo, dry_run=True))

    out = capsys.readouterr().out
    assert "### Added" in out
    assert "Shipped" in out
    assert not (repo / "CHANGELOG.md").exists()


def test_run_aborts_without_yes_when_user_declines(tmp_path, monkeypatch, make_log):
    repo = _init_repo(tmp_path)
    _write_pyproject(repo, "0.4.0")
    _seed_quest_log(repo, make_log)
    _git(["add", "-A"], repo)
    _git(["commit", "-m", "bump + log"], repo)
    monkeypatch.setattr(release, "installed_version", lambda: "0.4.0")
    monkeypatch.setattr(release, "_confirm", lambda tag: False)

    def _boom(*a, **k):
        raise AssertionError("create_and_push_tag must not be called when the user declines")

    monkeypatch.setattr(release, "create_and_push_tag", _boom)

    with pytest.raises(release.ReleaseError, match="aborted"):
        release.run(_args(repo, yes=False))

    assert not (repo / "CHANGELOG.md").exists()


def test_run_happy_path_writes_changelog_and_tags(tmp_path, monkeypatch, make_log):
    repo = _init_repo(tmp_path)
    _write_pyproject(repo, "0.4.0")
    quests_dir = _seed_quest_log(repo, make_log)
    _git(["add", "-A"], repo)
    _git(["commit", "-m", "bump + log"], repo)
    monkeypatch.setattr(release, "installed_version", lambda: "0.4.0")

    from questkit.cli import main as quest_main

    assert quest_main([
        "new", "Shipped feature", "--in", str(quests_dir), "--type", "feature",
        "--status", "done", "--set", "milestone=0.4.0",
    ]) == 0
    _git(["add", "-A"], repo)
    _git(["commit", "-m", "add quest"], repo)

    calls = []
    monkeypatch.setattr(
        release, "create_and_push_tag",
        lambda repo_root, tag, message, *, remote: calls.append((repo_root, tag, message, remote)),
    )

    release.run(_args(repo, yes=True, remote="upstream"))

    assert len(calls) == 1
    called_repo, tag, message, remote = calls[0]
    assert called_repo == repo
    assert tag == "v0.4.0"
    assert "Shipped feature" in message
    assert remote == "upstream"

    changelog = (repo / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [0.4.0]" in changelog
    assert "Shipped feature" in changelog


def test_main_reports_release_error_and_returns_1(tmp_path, monkeypatch, capsys):
    repo = _init_repo(tmp_path)
    _write_pyproject(repo, "0.4.0")
    monkeypatch.setattr(release, "installed_version", lambda: "0.3.0")

    code = release.main(["--repo-root", str(repo)])

    assert code == 1
    assert "0.4.0" in capsys.readouterr().err
