"""Tests for QST-22gdn's `quest-apply-trailers`: parsing `Quest:` commit
trailers (via `git interpret-trailers --parse`, never prose regex) and
transitioning (or Log-mentioning) the quest(s) they name.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from questkit.hooks import apply_trailers_main
from questkit.quest import Quest


def _git_init(repo_root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_root, check=True)


def _commit(repo_root: Path, message: str, filename: str = "code.py") -> str:
    path = repo_root / filename
    path.write_text(path.read_text() + "x\n" if path.exists() else "x\n")
    subprocess.run(["git", "add", "-A"], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", message], cwd=repo_root, check=True)
    return subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], cwd=repo_root, capture_output=True, text=True
    ).stdout.strip()


def test_status_token_trailer_transitions_the_quest(tmp_path, make_log, write_quest, monkeypatch):
    repo = tmp_path
    _git_init(repo)
    log = make_log(repo, project="proj", git="manual")
    write_quest(log, "QST-aaaaa", status="todo")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=repo, check=True)

    _commit(repo, "fix: something\n\nQuest: QST-aaaaa done\n")
    monkeypatch.chdir(repo)

    exit_code = apply_trailers_main([])

    assert exit_code == 0
    quest = Quest.load(log / "QST-aaaaa--a-quest.md")
    assert quest.get("status") == "done"
    assert str(quest.get("status_changed")) == quest.get("modified").isoformat()


def test_bare_mention_trailer_appends_a_log_entry(tmp_path, make_log, write_quest, monkeypatch):
    repo = tmp_path
    _git_init(repo)
    log = make_log(repo, project="proj", git="manual")
    write_quest(log, "QST-bbbbb", status="todo")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=repo, check=True)

    sha = _commit(repo, "chore: touch\n\nQuest: QST-bbbbb\n")
    monkeypatch.chdir(repo)

    exit_code = apply_trailers_main([])

    assert exit_code == 0
    quest = Quest.load(log / "QST-bbbbb--a-quest.md")
    assert quest.get("status") == "todo"  # bare mention never changes status
    assert sha in quest.body
    assert "## Log" in quest.body


def test_reapplying_the_same_status_transition_is_a_no_op(tmp_path, make_log, write_quest, monkeypatch):
    repo = tmp_path
    _git_init(repo)
    log = make_log(repo, project="proj", git="manual")
    write_quest(log, "QST-ccccc", status="done", status_changed="2020-01-01", modified="2020-01-01")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=repo, check=True)

    _commit(repo, "fix: something\n\nQuest: QST-ccccc done\n")
    monkeypatch.chdir(repo)

    apply_trailers_main([])

    quest = Quest.load(log / "QST-ccccc--a-quest.md")
    # already `done` -- a no-op: modified/status_changed untouched
    assert str(quest.get("modified")) == "2020-01-01"
    assert str(quest.get("status_changed")) == "2020-01-01"


def test_reapplying_the_same_commit_does_not_duplicate_a_mention_log_entry(
    tmp_path, make_log, write_quest, monkeypatch
):
    repo = tmp_path
    _git_init(repo)
    log = make_log(repo, project="proj", git="manual")
    write_quest(log, "QST-ddddd", status="todo")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=repo, check=True)

    sha = _commit(repo, "chore: touch\n\nQuest: QST-ddddd\n")
    monkeypatch.chdir(repo)

    apply_trailers_main([])
    apply_trailers_main([])  # simulate a re-run (e.g. the timer re-scanning)

    quest = Quest.load(log / "QST-ddddd--a-quest.md")
    assert quest.body.count(sha) == 1


def test_out_of_vocabulary_status_token_warns_and_does_not_write(
    tmp_path, make_log, write_quest, monkeypatch, capsys
):
    repo = tmp_path
    _git_init(repo)
    log = make_log(repo, project="proj", git="manual")
    write_quest(log, "QST-eeeee", status="todo")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=repo, check=True)

    _commit(repo, "fix: something\n\nQuest: QST-eeeee not-a-real-status\n")
    monkeypatch.chdir(repo)
    capsys.readouterr()

    exit_code = apply_trailers_main([])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "not-a-real-status" in out
    quest = Quest.load(log / "QST-eeeee--a-quest.md")
    assert quest.get("status") == "todo"


def test_unknown_quest_id_warns_and_does_not_crash(tmp_path, make_log, write_quest, monkeypatch, capsys):
    repo = tmp_path
    _git_init(repo)
    make_log(repo, project="proj", git="manual")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=repo, check=True)

    _commit(repo, "fix: something\n\nQuest: QST-zzzzz done\n")
    monkeypatch.chdir(repo)
    capsys.readouterr()

    exit_code = apply_trailers_main([])

    assert exit_code == 0
    assert "QST-zzzzz" in capsys.readouterr().out


def test_a_schema_overridden_vocabulary_writes_its_own_status_words(
    tmp_path, make_log, write_quest, monkeypatch
):
    repo = tmp_path
    _git_init(repo)
    log = make_log(
        repo,
        project="proj",
        git="manual",
        schema={"statuses": ["todo", "shipped"], "terminal_statuses": ["shipped"]},
    )
    write_quest(log, "QST-fffff", status="todo")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=repo, check=True)

    _commit(repo, "fix: something\n\nQuest: QST-fffff shipped\n")
    monkeypatch.chdir(repo)

    exit_code = apply_trailers_main([])

    assert exit_code == 0
    quest = Quest.load(log / "QST-fffff--a-quest.md")
    assert quest.get("status") == "shipped"


def test_multiple_quest_trailers_in_one_commit_are_all_applied(tmp_path, make_log, write_quest, monkeypatch):
    repo = tmp_path
    _git_init(repo)
    log = make_log(repo, project="proj", git="manual")
    write_quest(log, "QST-11111", status="todo")
    write_quest(log, "QST-22222", status="todo")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=repo, check=True)

    _commit(repo, "chore: two\n\nQuest: QST-11111 done\nQuest: QST-22222 scrapped\n")
    monkeypatch.chdir(repo)

    apply_trailers_main([])

    assert Quest.load(log / "QST-11111--a-quest.md").get("status") == "done"
    assert Quest.load(log / "QST-22222--a-quest.md").get("status") == "scrapped"


def test_explicit_commit_ref_argument_is_used_instead_of_head(tmp_path, make_log, write_quest, monkeypatch):
    """Timer-callable: a caller can pass an explicit rev range/commit rather
    than relying on the post-commit hook's implicit HEAD."""
    repo = tmp_path
    _git_init(repo)
    log = make_log(repo, project="proj", git="manual")
    write_quest(log, "QST-ggggg", status="todo")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=repo, check=True)

    _commit(repo, "fix: something\n\nQuest: QST-ggggg done\n")
    _commit(repo, "chore: unrelated\n")  # HEAD now points past the trailer commit
    monkeypatch.chdir(repo)

    exit_code = apply_trailers_main(["HEAD~1"])

    assert exit_code == 0
    assert Quest.load(log / "QST-ggggg--a-quest.md").get("status") == "done"


def test_commit_with_no_quest_trailer_is_a_no_op(tmp_path, make_log, write_quest, monkeypatch, capsys):
    repo = tmp_path
    _git_init(repo)
    make_log(repo, project="proj", git="manual")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=repo, check=True)

    _commit(repo, "chore: plain commit, no trailer\n")
    monkeypatch.chdir(repo)

    exit_code = apply_trailers_main([])

    assert exit_code == 0
