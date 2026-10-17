"""Tests for `scripts/sensitive_scan.py`: the private deny-list scanner for
names, employers and hosts that credential scanners cannot know about.

Real throwaway git repos are used throughout; nothing here touches this
repository's history. The terms in the fixtures are made up."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parent.parent / "scripts" / "sensitive_scan.py"
_spec = importlib.util.spec_from_file_location("questkit_sensitive_scan", _PATH)
scan = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = scan
_spec.loader.exec_module(scan)


def _git(repo: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    )
    return out.stdout.strip()


def _commit(repo: Path, name: str, text: str, message: str) -> str:
    (repo / name).write_text(text, encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


class Repo(type(Path())):  # a Path that also carries the fixture's commit ids
    shas: list[str]


@pytest.fixture
def repo(tmp_path):
    r = Repo(tmp_path / "repo")
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "T")
    shas = [
        _commit(r, "a.txt", "hello\n", "init"),
        _commit(r, "b.txt", "works at Acme Corp\n", "add b"),
        _commit(r, "c.txt", "clean\n", "add c"),
        _commit(r, "d.txt", "nothing here\n", "mention globex"),
        _commit(r, "e.txt", "clean too\n", "add e"),
    ]
    r.shas = shas
    return r


def _run(repo, *argv, capsys, stdin=None, monkeypatch=None):
    if stdin is not None:
        import io

        monkeypatch.setattr(sys, "stdin", io.StringIO(stdin))
    code = scan.main(["--repo", str(repo), *argv])
    out = capsys.readouterr()
    return code, out.out, out.err


# --- terms ---------------------------------------------------------------------


def test_terms_file_supports_comments_literals_and_regexes(tmp_path):
    f = tmp_path / "terms"
    f.write_text("# a comment\n\nlit:a.b\nacme\\d+\n", encoding="utf-8")

    patterns = scan.load_terms_file(f)

    assert [p.search("A.B") is not None for p in patterns] == [True, False]
    assert patterns[0].search("axb") is None  # literal dot
    assert patterns[1].search("ACME42") is not None  # case-insensitive regex


def test_terms_default_to_the_env_file(tmp_path, monkeypatch):
    f = tmp_path / "terms"
    f.write_text("acme\n", encoding="utf-8")
    monkeypatch.setenv("SENSITIVE_TERMS_FILE", str(f))

    assert len(scan.collect_terms(term=[], pattern=[], terms_file=None)) == 1


def test_no_terms_means_no_patterns(monkeypatch, tmp_path):
    monkeypatch.delenv("SENSITIVE_TERMS_FILE", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "nothing"))
    monkeypatch.setenv("HOME", str(tmp_path / "nothing"))

    assert scan.collect_terms(term=[], pattern=[], terms_file=None) == []


# --- history -------------------------------------------------------------------


def test_history_lists_matching_commits_and_the_rewrite_scope(repo, capsys):
    code, out, _ = _run(repo, "history", "--term", "acme", capsys=capsys)

    assert code == 1
    assert "Matching commits: 1 of 5" in out
    assert repo.shas[1][:7] in out
    # the first match is the 2nd commit: it and everything after must change
    assert "would be rewritten: 4 of 5" in out
    assert "keep their ids: 1" in out


def test_history_scans_commit_messages_too(repo, capsys):
    code, out, _ = _run(repo, "history", "--term", "globex", capsys=capsys)

    assert code == 1
    assert repo.shas[3][:7] in out
    assert "would be rewritten: 2 of 5" in out


def test_history_without_matches_exits_zero(repo, capsys):
    code, out, _ = _run(repo, "history", "--term", "initech", capsys=capsys)

    assert code == 0
    assert "Matching commits: 0 of 5" in out
    assert "would be rewritten" not in out


def test_history_regex_respects_word_boundaries(repo, capsys):
    (repo / "f.txt").write_text("initechs department\n", encoding="utf-8")
    _git(repo, "add", "f.txt")
    _git(repo, "commit", "-q", "-m", "prose")

    loose = _run(repo, "history", "--pattern", "initech", capsys=capsys)
    strict = _run(repo, "history", "--pattern", r"\binitech\b", capsys=capsys)

    assert loose[0] == 1
    assert strict[0] == 0


def test_history_reports_the_squash_span_between_first_and_last_match(repo, capsys):
    _, out, _ = _run(repo, "history", "--term", "acme", "--term", "globex", capsys=capsys)

    assert "Matching commits: 2 of 5" in out
    assert "squash span (first to last match): 3 commits" in out


def test_history_counts_matches_on_other_branches(repo, capsys):
    _git(repo, "checkout", "-q", "-b", "side", repo.shas[0])
    _commit(repo, "s.txt", "acme side\n", "side work")
    _git(repo, "checkout", "-q", "main")

    _, out, _ = _run(repo, "history", "--term", "acme", capsys=capsys)

    assert "Matching commits: 2 of 6" in out
    # main's b.txt commit (+3 descendants) and the side commit
    assert "would be rewritten: 5 of 6" in out


def test_history_json(repo, capsys):
    code, out, _ = _run(repo, "history", "--term", "acme", "--json", capsys=capsys)

    data = json.loads(out)
    assert code == 1
    assert data["total_commits"] == 5
    assert data["rewrite_count"] == 4
    assert data["keep_count"] == 1
    assert [m["sha"] for m in data["matches"]] == [repo.shas[1]]
    assert data["matches"][0]["terms"] == ["acme"]
    assert data["matches"][0]["descendants"] == 3


def test_history_requires_terms(repo, capsys, monkeypatch, tmp_path):
    monkeypatch.delenv("SENSITIVE_TERMS_FILE", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "nothing"))
    monkeypatch.setenv("HOME", str(tmp_path / "nothing"))

    code, _, err = _run(repo, "history", capsys=capsys)

    assert code == 2
    assert "no terms" in err.lower()


# --- tree ----------------------------------------------------------------------


def test_tree_lists_files_in_the_current_tree(repo, capsys):
    code, out, _ = _run(repo, "tree", "--term", "acme", capsys=capsys)

    assert code == 1
    assert "b.txt" in out
    assert "a.txt" not in out


# --- staged (pre-commit) --------------------------------------------------------


def test_staged_flags_an_added_line(repo, capsys):
    (repo / "n.txt").write_text("ping Acme\n", encoding="utf-8")
    _git(repo, "add", "n.txt")

    code, out, _ = _run(repo, "staged", "--term", "acme", capsys=capsys)

    assert code == 1
    assert "n.txt" in out


def test_staged_ignores_removed_lines_and_unstaged_files(repo, capsys):
    (repo / "b.txt").write_text("fine now\n", encoding="utf-8")  # removes the term
    _git(repo, "add", "b.txt")
    (repo / "u.txt").write_text("acme but unstaged\n", encoding="utf-8")

    code, _, _ = _run(repo, "staged", "--term", "acme", capsys=capsys)

    assert code == 0


def test_staged_passes_with_a_notice_when_no_terms_are_configured(
    repo, capsys, monkeypatch, tmp_path
):
    monkeypatch.delenv("SENSITIVE_TERMS_FILE", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "nothing"))
    monkeypatch.setenv("HOME", str(tmp_path / "nothing"))

    code, _, err = _run(repo, "staged", capsys=capsys)

    assert code == 0
    assert "skipping" in err.lower()


# --- push (pre-push) -------------------------------------------------------------


def _push_line(local, remote):
    return f"refs/heads/main {local} refs/heads/main {remote}\n"


def test_push_flags_commits_in_the_pushed_range(repo, capsys, monkeypatch):
    line = _push_line(repo.shas[4], repo.shas[0])

    code, out, _ = _run(repo, "push", "--term", "acme", capsys=capsys, stdin=line, monkeypatch=monkeypatch)

    assert code == 1
    assert repo.shas[1][:7] in out


def test_push_ignores_commits_already_on_the_remote(repo, capsys, monkeypatch):
    line = _push_line(repo.shas[4], repo.shas[2])  # remote already has the Acme commit

    code, _, _ = _run(repo, "push", "--term", "acme", capsys=capsys, stdin=line, monkeypatch=monkeypatch)

    assert code == 0


def test_push_checks_commit_messages(repo, capsys, monkeypatch):
    line = _push_line(repo.shas[4], repo.shas[2])

    code, out, _ = _run(repo, "push", "--term", "globex", capsys=capsys, stdin=line, monkeypatch=monkeypatch)

    assert code == 1
    assert repo.shas[3][:7] in out


def test_push_of_a_new_branch_scans_everything_not_on_a_remote(repo, capsys, monkeypatch):
    zero = "0" * 40
    line = _push_line(repo.shas[4], zero)

    code, _, _ = _run(repo, "push", "--term", "acme", capsys=capsys, stdin=line, monkeypatch=monkeypatch)

    assert code == 1


def test_push_ignores_branch_deletions(repo, capsys, monkeypatch):
    zero = "0" * 40
    line = f"(delete) {zero} refs/heads/old {repo.shas[1]}\n"

    code, _, _ = _run(repo, "push", "--term", "acme", capsys=capsys, stdin=line, monkeypatch=monkeypatch)

    assert code == 0


# --- push under the pre-commit framework (refs in the environment, no stdin) -------


def test_push_reads_the_pre_commit_environment(repo, capsys, monkeypatch):
    monkeypatch.setenv("PRE_COMMIT_FROM_REF", repo.shas[0])
    monkeypatch.setenv("PRE_COMMIT_TO_REF", repo.shas[4])

    code, out, _ = _run(repo, "push", "--pre-commit", "--term", "acme", capsys=capsys)

    assert code == 1
    assert repo.shas[1][:7] in out


def test_push_environment_range_can_be_clean(repo, capsys, monkeypatch):
    monkeypatch.setenv("PRE_COMMIT_FROM_REF", repo.shas[2])
    monkeypatch.setenv("PRE_COMMIT_TO_REF", repo.shas[4])

    code, _, _ = _run(repo, "push", "--pre-commit", "--term", "acme", capsys=capsys)

    assert code == 0


def test_push_environment_without_a_from_ref_scans_what_no_remote_has(repo, capsys, monkeypatch):
    monkeypatch.delenv("PRE_COMMIT_FROM_REF", raising=False)
    monkeypatch.setenv("PRE_COMMIT_TO_REF", repo.shas[4])

    code, _, _ = _run(repo, "push", "--pre-commit", "--term", "acme", capsys=capsys)

    assert code == 1


def test_push_environment_with_no_to_ref_is_a_no_op(repo, capsys, monkeypatch):
    monkeypatch.delenv("PRE_COMMIT_TO_REF", raising=False)

    code, _, _ = _run(repo, "push", "--pre-commit", "--term", "acme", capsys=capsys)

    assert code == 0


# --- not a git repository ------------------------------------------------------------


@pytest.mark.parametrize("mode", ["history", "tree", "staged"])
def test_a_directory_that_is_not_a_repository_is_a_clean_error(
    tmp_path, capsys, monkeypatch, mode
):
    """git failing must be reported, never a traceback and never a silent pass: a
    staged scan that cannot read the diff would otherwise look like 'nothing found'."""
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))

    code, _, err = _run(tmp_path, mode, "--term", "acme", capsys=capsys)

    assert code == 2
    assert "not a git repository" in err.lower()
    assert "Traceback" not in err


def test_a_missing_repo_path_is_a_clean_error(tmp_path, capsys):
    code, _, err = _run(tmp_path / "nope", "history", "--term", "acme", capsys=capsys)

    assert code == 2
    assert "Traceback" not in err
    assert err.startswith("sensitive-scan:")
