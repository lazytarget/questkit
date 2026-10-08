"""Tests for `quest-bump-modified`'s status_changed backfill (QST-e6g6t follow-up).

A quest edited as raw text -- in Obsidian, or by anyone bypassing the CLI --
can change `status` without touching `status_changed`, since only the CLI's
`set_cmd` knows to stamp it. The hook catches this by diffing the staged
content against what's actually committed at HEAD.
"""

from __future__ import annotations

import subprocess

from questkit.hooks import bump_modified_main
from questkit.quest import Quest


def _git_init(repo_root):
    subprocess.run(["git", "init", "-q"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_root, check=True)


def _commit(repo_root, path):
    subprocess.run(["git", "add", "--", str(path.relative_to(repo_root))], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=repo_root, check=True)


_BODY = "\n## Description\n"


def _write_quest(path, status, status_changed=None, extra=""):
    lines = [
        "---",
        "id: QST-aaaaa",
        "title: T",
        f"status: {status}",
    ]
    if status_changed:
        lines.append(f"status_changed: {status_changed}")
    lines.append("modified: 2026-08-14")
    if extra:
        lines.append(extra)
    lines.append("---")
    text = "\n".join(lines) + "\n" + _BODY
    path.write_text(text, encoding="utf-8")


def test_a_raw_status_edit_gets_status_changed_backfilled(tmp_path, monkeypatch):
    repo = tmp_path
    _git_init(repo)
    path = repo / "QST-aaaaa--t.md"
    _write_quest(path, status="in-progress", status_changed="2026-08-10")
    _commit(repo, path)

    _write_quest(path, status="done", status_changed="2026-08-10")  # raw edit, status_changed untouched
    monkeypatch.setattr("questkit.hooks.today", lambda: "2026-08-22")

    bump_modified_main([str(path)])

    assert Quest.load(path).get("status_changed").isoformat() == "2026-08-22"


def test_no_status_change_leaves_status_changed_alone(tmp_path, monkeypatch):
    repo = tmp_path
    _git_init(repo)
    path = repo / "QST-aaaaa--t.md"
    _write_quest(path, status="in-progress", status_changed="2026-08-10")
    _commit(repo, path)

    _write_quest(path, status="in-progress", status_changed="2026-08-10")  # unrelated edit only
    monkeypatch.setattr("questkit.hooks.today", lambda: "2026-08-22")

    bump_modified_main([str(path)])

    assert Quest.load(path).get("status_changed").isoformat() == "2026-08-10"


def test_a_deliberate_status_changed_value_is_not_overwritten(tmp_path, monkeypatch):
    """If status_changed *also* differs from HEAD, something already set it
    deliberately (the CLI in the same change, a migration backfill) -- the
    hook must not fight that."""
    repo = tmp_path
    _git_init(repo)
    path = repo / "QST-aaaaa--t.md"
    _write_quest(path, status="in-progress", status_changed="2026-08-10")
    _commit(repo, path)

    _write_quest(path, status="done", status_changed="2026-08-15")  # both fields moved together
    monkeypatch.setattr("questkit.hooks.today", lambda: "2026-08-22")

    bump_modified_main([str(path)])

    assert Quest.load(path).get("status_changed").isoformat() == "2026-08-15"


def test_a_brand_new_quest_with_no_history_gets_no_backfill(tmp_path, monkeypatch):
    repo = tmp_path
    _git_init(repo)
    path = repo / "QST-aaaaa--t.md"
    _write_quest(path, status="draft")  # never committed -- no HEAD version at all
    monkeypatch.setattr("questkit.hooks.today", lambda: "2026-08-22")

    bump_modified_main([str(path)])

    assert Quest.load(path).get("status_changed") is None


def test_outside_a_git_repo_the_backfill_is_skipped_but_modified_still_bumps(tmp_path, monkeypatch):
    path = tmp_path / "QST-aaaaa--t.md"
    _write_quest(path, status="done")
    monkeypatch.setattr("questkit.hooks.today", lambda: "2026-08-22")

    bump_modified_main([str(path)])

    quest = Quest.load(path)
    assert quest.get("status_changed") is None
    assert quest.get("modified").isoformat() == "2026-08-22"


def test_status_changed_backfill_and_modified_bump_both_land_in_one_run(tmp_path, monkeypatch):
    repo = tmp_path
    _git_init(repo)
    path = repo / "QST-aaaaa--t.md"
    _write_quest(path, status="in-progress", status_changed="2026-08-10")
    _commit(repo, path)

    _write_quest(path, status="done", status_changed="2026-08-10")
    monkeypatch.setattr("questkit.hooks.today", lambda: "2026-08-22")

    bump_modified_main([str(path)])

    quest = Quest.load(path)
    assert quest.get("status_changed").isoformat() == "2026-08-22"
    assert quest.get("modified").isoformat() == "2026-08-22"


def test_prints_a_note_when_it_backfills(tmp_path, monkeypatch, capsys):
    repo = tmp_path
    _git_init(repo)
    path = repo / "QST-aaaaa--t.md"
    _write_quest(path, status="in-progress", status_changed="2026-08-10")
    _commit(repo, path)

    _write_quest(path, status="done", status_changed="2026-08-10")
    monkeypatch.setattr("questkit.hooks.today", lambda: "2026-08-22")
    capsys.readouterr()

    bump_modified_main([str(path)])

    assert "backfilled status_changed" in capsys.readouterr().out


# --- QST-reakz: stage the bump, say so, and only touch files that changed -----


def _staged(repo):
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only"], cwd=repo, capture_output=True, text=True, check=True
    )
    return out.stdout.split()


def _unstaged(repo):
    out = subprocess.run(
        ["git", "diff", "--name-only"], cwd=repo, capture_output=True, text=True, check=True
    )
    return out.stdout.split()


def test_the_bump_is_staged_so_no_unstaged_diff_remains(tmp_path, monkeypatch):
    repo = tmp_path
    _git_init(repo)
    path = repo / "QST-aaaaa--t.md"
    _write_quest(path, status="draft")
    _commit(repo, path)

    _write_quest(path, status="draft", extra="priority: high")  # hand edit, stale modified
    subprocess.run(["git", "add", "--", path.name], cwd=repo, check=True)
    monkeypatch.setattr("questkit.hooks.today", lambda: "2026-08-22")

    assert bump_modified_main([str(path)]) == 0

    assert _unstaged(repo) == []
    staged = subprocess.run(
        ["git", "show", f":{path.name}"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout
    assert "modified: 2026-08-22" in staged


def test_one_informational_line_shows_old_to_new_date(tmp_path, monkeypatch, capsys):
    repo = tmp_path
    _git_init(repo)
    path = repo / "QST-aaaaa--t.md"
    _write_quest(path, status="draft")
    _commit(repo, path)
    _write_quest(path, status="draft", extra="priority: high")
    monkeypatch.setattr("questkit.hooks.today", lambda: "2026-08-22")
    capsys.readouterr()

    bump_modified_main([str(path)])

    lines = [ln for ln in capsys.readouterr().out.splitlines() if ln.strip()]
    assert lines == ["[quest-bump-modified] QST-aaaaa--t.md: modified 2026-08-14 → 2026-08-22"]


def test_an_unchanged_file_is_neither_bumped_nor_staged_nor_announced(tmp_path, monkeypatch, capsys):
    repo = tmp_path
    _git_init(repo)
    path = repo / "QST-aaaaa--t.md"
    _write_quest(path, status="draft")  # modified: 2026-08-14
    _commit(repo, path)
    monkeypatch.setattr("questkit.hooks.today", lambda: "2026-08-22")
    capsys.readouterr()

    bump_modified_main([str(path)])  # e.g. `pre-commit run --all-files`

    assert "modified: 2026-08-14" in path.read_text()
    assert _staged(repo) == []
    assert _unstaged(repo) == []
    assert capsys.readouterr().out == ""


def test_a_brand_new_quest_counts_as_changed_and_is_staged(tmp_path, monkeypatch):
    repo = tmp_path
    _git_init(repo)
    seed = repo / "QST-seed0--s.md"
    _write_quest(seed, status="draft")
    _commit(repo, seed)  # HEAD exists, but not for the new file
    path = repo / "QST-aaaaa--t.md"
    _write_quest(path, status="draft")
    subprocess.run(["git", "add", "--", path.name], cwd=repo, check=True)
    monkeypatch.setattr("questkit.hooks.today", lambda: "2026-08-22")

    bump_modified_main([str(path)])

    assert Quest.load(path).get("modified").isoformat() == "2026-08-22"
    assert _unstaged(repo) == []


def test_a_status_changed_backfill_is_staged_too(tmp_path, monkeypatch):
    repo = tmp_path
    _git_init(repo)
    path = repo / "QST-aaaaa--t.md"
    _write_quest(path, status="in-progress", status_changed="2026-08-10")
    _commit(repo, path)
    _write_quest(path, status="done", status_changed="2026-08-10")
    subprocess.run(["git", "add", "--", path.name], cwd=repo, check=True)
    monkeypatch.setattr("questkit.hooks.today", lambda: "2026-08-22")

    bump_modified_main([str(path)])

    assert _unstaged(repo) == []
    staged = subprocess.run(
        ["git", "show", f":{path.name}"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout
    assert "status_changed: 2026-08-22" in staged


def test_outside_a_git_repo_nothing_is_staged_and_no_error(tmp_path, monkeypatch, capsys):
    path = tmp_path / "QST-aaaaa--t.md"
    _write_quest(path, status="draft")
    monkeypatch.setattr("questkit.hooks.today", lambda: "2026-08-22")

    assert bump_modified_main([str(path)]) == 0
    assert "modified 2026-08-14 → 2026-08-22" in capsys.readouterr().out


def test_both_hook_manifests_set_verbose_on_bump_modified():
    from pathlib import Path

    import yaml

    root = Path(__file__).resolve().parents[1]
    manifest = yaml.safe_load((root / ".pre-commit-hooks.yaml").read_text())
    config = yaml.safe_load((root / ".pre-commit-config.yaml").read_text())
    hooks = [h for h in manifest if h["id"] == "quest-bump-modified"]
    hooks += [h for r in config["repos"] for h in r["hooks"] if h["id"] == "quest-bump-modified"]
    assert len(hooks) == 2
    assert all(h.get("verbose") is True for h in hooks)
