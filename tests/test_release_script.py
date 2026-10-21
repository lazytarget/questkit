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
import shutil
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
    _git(["config", "commit.gpgsign", "false"], repo)  # never inherit a machine's signing setup
    (repo / "README.md").write_text("hi\n", encoding="utf-8")
    _git(["add", "README.md"], repo)
    _git(["commit", "-m", "init"], repo)
    return repo


def _write_pyproject(repo: Path, version: str) -> None:
    (repo / "pyproject.toml").write_text(
        f'[project]\nname = "questkit"\nversion = "{version}"\n', encoding="utf-8"
    )


def _args(repo: Path, **overrides) -> argparse.Namespace:
    defaults = dict(yes=True, dry_run=False, remote=["origin"], repo_root=repo, quests_dir=None)
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


# --- helpers for real repositories, bare remotes and signing ------------------------


def _out(args: list[str], cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def _head(repo: Path) -> str:
    return _out(["rev-parse", "HEAD"], repo)


def _branch(repo: Path) -> str:
    return _out(["branch", "--show-current"], repo)


def _add_remote(repo: Path, tmp_path: Path, name: str = "origin") -> Path:
    bare = tmp_path / f"{name}.git"
    _git(["init", "--bare", str(bare)], tmp_path)
    _git(["remote", "add", name, str(bare)], repo)
    return bare


def _remote_ref(bare: Path, ref: str) -> str | None:
    result = subprocess.run(
        ["git", "--git-dir", str(bare), "rev-parse", "--verify", "--quiet", ref],
        capture_output=True, text=True,
    )
    return result.stdout.strip() or None


def _refuse_pushes(bare: Path) -> None:
    hook = bare / "hooks" / "pre-receive"
    hook.parent.mkdir(exist_ok=True)
    hook.write_text("#!/bin/sh\necho 'no pushes today' >&2\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)


def _refuse_commits(repo: Path) -> None:
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\necho 'hook says no' >&2\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)


needs_ssh_keygen = pytest.mark.skipif(shutil.which("ssh-keygen") is None, reason="needs ssh-keygen to sign a tag")


def _signing(repo: Path, tmp_path: Path, *, working: bool = True) -> None:
    """Sign tags with a throwaway ssh key, or point at a key that does not exist."""
    key = tmp_path / "sign_key"
    if working and not key.exists():
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
    _git(["config", "gpg.format", "ssh"], repo)
    _git(["config", "user.signingkey", str(key) if working else str(tmp_path / "no-such-key")], repo)


def _release_repo(tmp_path, monkeypatch, make_log, *, remotes=("origin",), signing=True) -> Path:
    """A repo ready to release 0.4.0: one finished milestone quest, a clean tree."""
    repo = _init_repo(tmp_path)
    _write_pyproject(repo, "0.4.0")
    quests_dir = _seed_quest_log(repo, make_log)
    _git(["add", "-A"], repo)
    _git(["commit", "-m", "bump + log"], repo)
    for name in remotes:
        _add_remote(repo, tmp_path, name)
    _signing(repo, tmp_path, working=signing)
    monkeypatch.setattr(release, "installed_version", lambda: "0.4.0")

    from questkit.cli import main as quest_main

    assert quest_main([
        "new", "Shipped feature", "--in", str(quests_dir), "--type", "feature",
        "--status", "done", "--set", "milestone=0.4.0",
    ]) == 0
    _git(["add", "-A"], repo)
    _git(["commit", "-m", "add quest"], repo)
    return repo


# --- which remotes -----------------------------------------------------------------


def test_resolve_remotes_keeps_the_explicit_remotes_in_the_order_given(tmp_path):
    repo = _init_repo(tmp_path)
    _add_remote(repo, tmp_path, "alpha")
    _add_remote(repo, tmp_path, "beta")

    assert release.resolve_remotes(repo, ["beta", "alpha"]) == ["beta", "alpha"]


def test_resolve_remotes_names_the_unknown_remote_and_the_real_ones(tmp_path):
    repo = _init_repo(tmp_path)
    _add_remote(repo, tmp_path, "alpha")

    with pytest.raises(release.ReleaseError) as exc:
        release.resolve_remotes(repo, ["nope"])

    assert "'nope'" in str(exc.value)
    assert "alpha" in str(exc.value)


def test_resolve_remotes_asks_for_each_remote_once(tmp_path):
    repo = _init_repo(tmp_path)
    _add_remote(repo, tmp_path, "alpha")

    assert release.resolve_remotes(repo, ["alpha", "alpha"]) == ["alpha"]


def test_resolve_remotes_defaults_to_origin(tmp_path):
    repo = _init_repo(tmp_path)
    _add_remote(repo, tmp_path, "origin")
    _add_remote(repo, tmp_path, "other")

    assert release.resolve_remotes(repo, None) == ["origin"]


def test_resolve_remotes_defaults_to_the_only_remote_when_there_is_no_origin(tmp_path):
    repo = _init_repo(tmp_path)
    _add_remote(repo, tmp_path, "gitea")

    assert release.resolve_remotes(repo, None) == ["gitea"]


def test_resolve_remotes_refuses_to_pick_between_several_remotes(tmp_path):
    """Pushing a release is outward-facing: with two remotes and no origin, the
    caller has to say where it goes."""
    repo = _init_repo(tmp_path)
    _add_remote(repo, tmp_path, "gitea")
    _add_remote(repo, tmp_path, "github")

    with pytest.raises(release.ReleaseError, match="--remote") as exc:
        release.resolve_remotes(repo, None)

    assert "gitea" in str(exc.value) and "github" in str(exc.value)


def test_resolve_remotes_refuses_a_repository_with_no_remote(tmp_path):
    repo = _init_repo(tmp_path)

    with pytest.raises(release.ReleaseError, match="no git remote"):
        release.resolve_remotes(repo, None)


def test_current_branch_names_the_checked_out_branch(tmp_path):
    repo = _init_repo(tmp_path)
    _git(["checkout", "-q", "-b", "release-branch"], repo)

    assert release.current_branch(repo) == "release-branch"


def test_current_branch_refuses_a_detached_head(tmp_path):
    repo = _init_repo(tmp_path)
    _git(["checkout", "-q", "--detach"], repo)

    with pytest.raises(release.ReleaseError, match="detached"):
        release.current_branch(repo)


# --- committing the changelog ------------------------------------------------------


def test_commit_changelog_commits_only_the_changelog(tmp_path):
    repo = _init_repo(tmp_path)
    before = _head(repo)
    (repo / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")

    sha = release.commit_changelog(repo, "0.4.0")

    assert sha == _head(repo)
    assert _out(["rev-parse", "HEAD~1"], repo) == before
    assert _out(["show", "--name-only", "--format=", "HEAD"], repo) == "CHANGELOG.md"
    assert _out(["log", "-1", "--format=%s"], repo) == "chore(release): changelog for 0.4.0"
    assert _out(["status", "--porcelain"], repo) == ""


def test_commit_changelog_restores_an_existing_file_when_the_commit_is_refused(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "CHANGELOG.md").write_text("old\n", encoding="utf-8")
    _git(["add", "CHANGELOG.md"], repo)
    _git(["commit", "-m", "add changelog"], repo)
    before = _head(repo)
    (repo / "CHANGELOG.md").write_text("new\n", encoding="utf-8")
    _refuse_commits(repo)

    with pytest.raises(release.ReleaseError, match="hook says no"):
        release.commit_changelog(repo, "0.4.0")

    assert (repo / "CHANGELOG.md").read_text(encoding="utf-8") == "old\n"
    assert _head(repo) == before
    assert _out(["status", "--porcelain"], repo) == ""


def test_commit_changelog_removes_a_file_it_created_when_the_commit_is_refused(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "CHANGELOG.md").write_text("brand new\n", encoding="utf-8")
    _refuse_commits(repo)

    with pytest.raises(release.ReleaseError):
        release.commit_changelog(repo, "0.4.0")

    assert not (repo / "CHANGELOG.md").exists()
    assert _out(["status", "--porcelain"], repo) == ""


# --- creating the tag ----------------------------------------------------------------


@needs_ssh_keygen
def test_create_tag_makes_a_signed_annotated_tag(tmp_path):
    repo = _init_repo(tmp_path)
    _signing(repo, tmp_path)

    release.create_tag(repo, "v1.0.0", "the message")

    assert _out(["cat-file", "-t", "v1.0.0"], repo) == "tag"
    assert "SSH SIGNATURE" in _out(["cat-file", "-p", "v1.0.0"], repo)


@needs_ssh_keygen
def test_create_tag_leaves_no_tag_when_the_signing_key_cannot_be_read(tmp_path):
    """Whatever the git version does: 2.43 prints 'Couldn't load public key' and exits 0
    with an UNSIGNED tag (the guard catches that), while 2.55 refuses to create it."""
    repo = _init_repo(tmp_path)
    _signing(repo, tmp_path, working=False)

    with pytest.raises(release.ReleaseError):
        release.create_tag(repo, "v1.0.0", "the message")

    assert not release.tag_exists(repo, "v1.0.0")


def test_create_tag_deletes_an_unsigned_tag_that_git_reported_as_created(tmp_path, monkeypatch):
    """The guard's own branch, forced on any git version: git exits 0 but the tag
    object carries no signature."""
    repo = _init_repo(tmp_path)
    real_run = release._run

    def unsigned(argv, cwd):
        if argv[:4] == ["git", "tag", "-s", "-a"]:
            argv = ["git", "tag", "-a", *argv[4:]]  # the same tag, without -s
        return real_run(argv, cwd)

    monkeypatch.setattr(release, "_run", unsigned)

    with pytest.raises(release.ReleaseError, match="did not sign"):
        release.create_tag(repo, "v1.0.0", "the message")

    assert not release.tag_exists(repo, "v1.0.0")


# --- pushing the release -----------------------------------------------------------


def _tagged_repo(tmp_path: Path, *remotes: str) -> tuple[Path, str]:
    repo = _init_repo(tmp_path)
    for name in remotes:
        _add_remote(repo, tmp_path, name)
    _git(["tag", "-a", "v1.0.0", "-m", "release"], repo)
    return repo, _branch(repo)


def test_push_release_sends_the_branch_and_the_tag_to_every_remote(tmp_path):
    repo, branch = _tagged_repo(tmp_path, "alpha", "beta")

    release.push_release(repo, branch, "v1.0.0", ["alpha", "beta"])

    for name in ("alpha", "beta"):
        bare = tmp_path / f"{name}.git"
        assert _remote_ref(bare, f"refs/heads/{branch}") == _head(repo)
        assert _remote_ref(bare, "refs/tags/v1.0.0^{commit}") == _head(repo)


def test_push_release_is_atomic_so_a_rejected_branch_keeps_the_tag_off_the_remote(tmp_path):
    """A tag whose commit is not on the branch is the half-published state to avoid."""
    repo, branch = _tagged_repo(tmp_path, "alpha")
    bare = tmp_path / "alpha.git"
    other = tmp_path / "other"
    _git(["clone", "-q", str(bare), str(other)], tmp_path)  # an empty remote: seed it with a diverging commit
    _git(["config", "user.email", "o@example.com"], other)
    _git(["config", "user.name", "Other"], other)
    (other / "x.txt").write_text("x", encoding="utf-8")
    _git(["add", "x.txt"], other)
    _git(["commit", "-m", "elsewhere"], other)
    _git(["push", "-q", "origin", f"HEAD:refs/heads/{branch}"], other)

    with pytest.raises(release.ReleaseError):
        release.push_release(repo, branch, "v1.0.0", ["alpha"])

    assert _remote_ref(bare, "refs/tags/v1.0.0") is None


def test_push_release_failure_names_what_was_pushed_and_how_to_finish(tmp_path):
    repo, branch = _tagged_repo(tmp_path, "alpha", "beta")
    _refuse_pushes(tmp_path / "beta.git")

    with pytest.raises(release.ReleaseError) as exc:
        release.push_release(repo, branch, "v1.0.0", ["alpha", "beta"])

    message = str(exc.value)
    assert "'beta'" in message
    assert "no pushes today" in message
    assert "already pushed to: alpha" in message
    assert f"git push --atomic beta refs/heads/{branch} refs/tags/v1.0.0" in message
    assert _remote_ref(tmp_path / "alpha.git", "refs/tags/v1.0.0") is not None


def test_push_release_stops_at_the_first_failing_remote(tmp_path):
    """The order given is the order published: a private remote first means a
    failure there keeps the public one untouched."""
    repo, branch = _tagged_repo(tmp_path, "alpha", "beta")
    _refuse_pushes(tmp_path / "alpha.git")

    with pytest.raises(release.ReleaseError) as exc:
        release.push_release(repo, branch, "v1.0.0", ["alpha", "beta"])

    assert "already pushed to: (none)" in str(exc.value)
    assert _remote_ref(tmp_path / "beta.git", "refs/tags/v1.0.0") is None


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


def test_run_refuses_an_unknown_remote_before_changing_anything(tmp_path, monkeypatch, make_log):
    repo = _release_repo(tmp_path, monkeypatch, make_log)
    before = _head(repo)

    with pytest.raises(release.ReleaseError, match="'nope'"):
        release.run(_args(repo, remote=["origin", "nope"]))

    assert _head(repo) == before
    assert not (repo / "CHANGELOG.md").exists()
    assert not release.tag_exists(repo, "v0.4.0")


def test_run_refuses_a_detached_head_before_changing_anything(tmp_path, monkeypatch, make_log):
    repo = _release_repo(tmp_path, monkeypatch, make_log)
    _git(["checkout", "-q", "--detach"], repo)

    with pytest.raises(release.ReleaseError, match="detached"):
        release.run(_args(repo))

    assert not (repo / "CHANGELOG.md").exists()


def test_run_dry_run_prints_section_and_plan_and_changes_nothing(tmp_path, monkeypatch, capsys, make_log):
    repo = _release_repo(tmp_path, monkeypatch, make_log, remotes=("gitea", "github"))
    before = _head(repo)

    release.run(_args(repo, dry_run=True, remote=["gitea", "github"]))

    captured = capsys.readouterr()
    assert "### Added" in captured.out
    assert "Shipped feature" in captured.out
    assert "would commit the changelog" in captured.err
    assert "v0.4.0" in captured.err
    assert "gitea, github" in captured.err
    assert _head(repo) == before
    assert not (repo / "CHANGELOG.md").exists()
    assert not release.tag_exists(repo, "v0.4.0")
    assert _remote_ref(tmp_path / "gitea.git", "refs/tags/v0.4.0") is None


def test_run_dry_run_still_rejects_an_unknown_remote(tmp_path, monkeypatch, make_log):
    repo = _release_repo(tmp_path, monkeypatch, make_log)

    with pytest.raises(release.ReleaseError, match="'nope'"):
        release.run(_args(repo, dry_run=True, remote=["nope"]))


def test_confirm_prompt_names_the_tag_the_branch_and_every_remote(monkeypatch):
    seen = []
    monkeypatch.setattr("builtins.input", lambda prompt: seen.append(prompt) or "y")

    assert release._confirm("v0.4.0", "main", ["gitea", "github"]) is True

    assert "v0.4.0" in seen[0] and "main" in seen[0] and "gitea, github" in seen[0]


def test_run_aborts_without_yes_when_user_declines(tmp_path, monkeypatch, make_log):
    repo = _release_repo(tmp_path, monkeypatch, make_log)
    before = _head(repo)
    monkeypatch.setattr(release, "_confirm", lambda tag, branch, remotes: False)

    with pytest.raises(release.ReleaseError, match="aborted"):
        release.run(_args(repo, yes=False))

    assert _head(repo) == before
    assert not (repo / "CHANGELOG.md").exists()
    assert not release.tag_exists(repo, "v0.4.0")


@needs_ssh_keygen
def test_run_commits_the_changelog_then_tags_that_commit_and_pushes_both(tmp_path, monkeypatch, make_log):
    repo = _release_repo(tmp_path, monkeypatch, make_log)
    before = _head(repo)

    release.run(_args(repo, remote=["origin"]))

    head = _head(repo)
    assert head != before
    assert _out(["rev-parse", "HEAD~1"], repo) == before
    assert _out(["log", "-1", "--format=%s"], repo) == "chore(release): changelog for 0.4.0"
    assert _out(["status", "--porcelain"], repo) == ""
    # the tag is on the changelog commit, so it contains its own changelog entry
    assert _out(["rev-parse", "v0.4.0^{commit}"], repo) == head
    assert "## [0.4.0]" in _out(["show", "v0.4.0:CHANGELOG.md"], repo)
    assert "Shipped feature" in _out(["show", "v0.4.0:CHANGELOG.md"], repo)
    # an annotated, signed tag whose message is the changelog section
    tag_object = _out(["cat-file", "-p", "v0.4.0"], repo)
    assert "SSH SIGNATURE" in tag_object
    assert "Shipped feature" in tag_object
    # and the branch and the tag both reached the remote
    bare = tmp_path / "origin.git"
    assert _remote_ref(bare, f"refs/heads/{_branch(repo)}") == head
    assert _remote_ref(bare, "refs/tags/v0.4.0^{commit}") == head


@needs_ssh_keygen
def test_run_publishes_to_every_remote_asked_for(tmp_path, monkeypatch, make_log):
    repo = _release_repo(tmp_path, monkeypatch, make_log, remotes=("gitea", "github"))

    release.run(_args(repo, remote=["gitea", "github"]))

    for name in ("gitea", "github"):
        assert _remote_ref(tmp_path / f"{name}.git", "refs/tags/v0.4.0^{commit}") == _head(repo)


@needs_ssh_keygen
def test_run_leaves_a_remote_it_was_not_told_about_alone(tmp_path, monkeypatch, make_log):
    repo = _release_repo(tmp_path, monkeypatch, make_log, remotes=("gitea", "github"))

    release.run(_args(repo, remote=["gitea"]))

    assert _remote_ref(tmp_path / "gitea.git", "refs/tags/v0.4.0") is not None
    assert _remote_ref(tmp_path / "github.git", "refs/tags/v0.4.0") is None


def test_run_rolls_the_changelog_back_when_the_commit_is_refused(tmp_path, monkeypatch, make_log):
    repo = _release_repo(tmp_path, monkeypatch, make_log)
    before = _head(repo)
    _refuse_commits(repo)

    with pytest.raises(release.ReleaseError, match="hook says no"):
        release.run(_args(repo))

    assert _head(repo) == before
    assert not (repo / "CHANGELOG.md").exists()
    assert _out(["status", "--porcelain"], repo) == ""
    assert not release.tag_exists(repo, "v0.4.0")
    assert _remote_ref(tmp_path / "origin.git", "refs/tags/v0.4.0") is None


@needs_ssh_keygen
def test_run_undoes_its_own_commit_when_the_tag_cannot_be_signed(tmp_path, monkeypatch, make_log):
    """No tag and no changelog commit may be left behind to trip the next attempt."""
    repo = _release_repo(tmp_path, monkeypatch, make_log, signing=False)
    before = _head(repo)

    with pytest.raises(release.ReleaseError):
        release.run(_args(repo))

    assert _head(repo) == before
    assert not (repo / "CHANGELOG.md").exists()
    assert _out(["status", "--porcelain"], repo) == ""
    assert not release.tag_exists(repo, "v0.4.0")
    assert _remote_ref(tmp_path / "origin.git", "refs/tags/v0.4.0") is None


@needs_ssh_keygen
def test_run_keeps_the_commit_and_tag_when_a_push_fails_and_says_how_to_finish(tmp_path, monkeypatch, make_log):
    repo = _release_repo(tmp_path, monkeypatch, make_log, remotes=("gitea", "github"))
    _refuse_pushes(tmp_path / "github.git")

    with pytest.raises(release.ReleaseError) as exc:
        release.run(_args(repo, remote=["gitea", "github"]))

    assert "already pushed to: gitea" in str(exc.value)
    assert "git push --atomic github" in str(exc.value)
    assert release.tag_exists(repo, "v0.4.0")  # published on gitea already: not rolled back
    assert _out(["rev-parse", "v0.4.0^{commit}"], repo) == _head(repo)


# --- command line ------------------------------------------------------------------------


def test_remote_can_be_given_more_than_once():
    args = release._parse_args(["--remote", "gitea", "--remote", "github"])

    assert args.remote == ["gitea", "github"]


def test_remote_defaults_to_none_so_the_repository_decides():
    assert release._parse_args([]).remote is None


def test_main_reports_release_error_and_returns_1(tmp_path, monkeypatch, capsys):
    repo = _init_repo(tmp_path)
    _write_pyproject(repo, "0.4.0")
    monkeypatch.setattr(release, "installed_version", lambda: "0.3.0")

    code = release.main(["--repo-root", str(repo)])

    assert code == 1
    assert "0.4.0" in capsys.readouterr().err
