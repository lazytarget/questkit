"""Tests for `quest migrate` — frontmatter-aware corpus migrations.

The prose-collision tests are the reason this command exists rather than a
documented `sed`. Verified in questkit's own log on 2026-08-19:

    QST-bmzl2:114  - [ ] Every quest ... is completed or explicitly scrapped
    QST-whm2e:65   ... Completed quests stay exactly where they were created

A line-oriented substitution corrupts both. Only a frontmatter-aware tool can
rename a *value of a field* without touching prose that uses the same word.
"""

from __future__ import annotations

import subprocess

from questkit.quest import Quest

# --- --backfill ------------------------------------------------------------------


def test_backfill_fills_only_files_missing_the_field(isolated, make_log, write_quest, run, absent):
    log = make_log(isolated)
    without = write_quest(log, "QST-aaaaa", slug="without", created="2026-01-05", status_changed=absent)
    already = write_quest(log, "QST-bbbbb", slug="already", created="2026-01-05", status_changed="2026-07-07")

    result = run("migrate", "--backfill", "status_changed=created", "--in", str(log))

    assert result.code == 0
    assert str(Quest.load(without).get("status_changed")) == "2026-01-05"
    assert str(Quest.load(already).get("status_changed")) == "2026-07-07"


def test_backfill_is_idempotent(isolated, make_log, write_quest, run, absent):
    log = make_log(isolated)
    path = write_quest(log, "QST-aaaaa", created="2026-01-05", status_changed=absent)

    run("migrate", "--backfill", "status_changed=created", "--in", str(log))
    settled = path.read_text()
    result = run("migrate", "--backfill", "status_changed=created", "--in", str(log))

    assert path.read_text() == settled
    assert "0 changed" in result.out


def test_backfill_never_overwrites_an_existing_value(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    path = write_quest(log, "QST-aaaaa", created="2026-01-05", status_changed="2026-07-07")

    run("migrate", "--backfill", "status_changed=created", "--in", str(log))

    assert str(Quest.load(path).get("status_changed")) == "2026-07-07"


def test_backfill_from_a_literal(isolated, make_log, write_quest, run, absent):
    log = make_log(isolated)
    path = write_quest(log, "QST-aaaaa", owner=absent)

    run("migrate", "--backfill", "owner=peter", "--in", str(log))

    assert Quest.load(path).get("owner") == "peter"


def test_backfill_from_a_macro(isolated, make_log, write_quest, run, absent, monkeypatch):
    monkeypatch.setattr("questkit.macros.today", lambda: "2026-08-21")
    log = make_log(isolated, "alpha")
    path = write_quest(log, "QST-aaaaa", reviewed=absent)

    run("migrate", "--backfill", "reviewed={{ today }}", "--in", str(log))

    assert str(Quest.load(path).get("reviewed")) == "2026-08-21"


def test_backfill_project_macro_uses_the_owning_log(isolated, make_log, write_quest, run, absent):
    log = make_log(isolated, "alpha", project="alpha")
    path = write_quest(log, "QST-aaaaa", project=absent)

    run("migrate", "--backfill", "project={{ project }}", "--in", str(log))

    assert Quest.load(path).get("project") == "alpha"


def test_backfill_skips_a_file_whose_source_field_is_also_absent(
    isolated, make_log, write_quest, run, absent
):
    log = make_log(isolated)
    path = write_quest(log, "QST-aaaaa", status_changed=absent, due=absent)

    result = run("migrate", "--backfill", "status_changed=due", "--in", str(log))

    assert result.code == 0
    assert "status_changed" not in Quest.load(path).frontmatter
    assert "1 skipped" in result.out


# --- --rename-value --------------------------------------------------------------


def test_rename_value_rewrites_the_frontmatter_value(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    path = write_quest(log, "QST-aaaaa", status="completed")

    result = run("migrate", "--rename-value", "status:completed=done", "--in", str(log))

    assert result.code == 0
    assert Quest.load(path).get("status") == "done"


def test_rename_value_leaves_the_word_alone_in_bodies_and_descriptions(
    isolated, make_log, write_quest, run
):
    """The whole reason this is a command and not a documented sed."""
    log = make_log(isolated)
    path = write_quest(
        log,
        "QST-aaaaa",
        status="completed",
        description="Every quest in the Scope table is completed or explicitly scrapped",
        body="## Description\n\nCompleted quests stay exactly where they were created, forever.\n"
        "\n- [ ] the status field says completed\n",
    )

    run("migrate", "--rename-value", "status:completed=done", "--in", str(log))

    quest = Quest.load(path)
    assert quest.get("status") == "done"
    assert "is completed or explicitly scrapped" in quest.get("description")
    assert "Completed quests stay exactly" in quest.body
    assert "the status field says completed" in quest.body


def test_rename_value_touches_only_the_named_field(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    path = write_quest(log, "QST-aaaaa", status="completed", type="task", resolution="completed")

    run("migrate", "--rename-value", "status:completed=done", "--in", str(log))

    quest = Quest.load(path)
    assert quest.get("status") == "done"
    assert quest.get("resolution") == "completed"


def test_rename_value_ignores_files_holding_a_different_value(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    todo = write_quest(log, "QST-aaaaa", slug="todo", status="todo")

    result = run("migrate", "--rename-value", "status:completed=done", "--in", str(log))

    assert Quest.load(todo).get("status") == "todo"
    assert "0 changed" in result.out


def test_rename_value_rewrites_a_list_membership(isolated, make_log, write_quest, run):
    """`tags` is a list, so renaming one member must not collapse the list."""
    log = make_log(isolated)
    path = write_quest(log, "QST-aaaaa", tags=["cli", "old-name", "dx"])

    run("migrate", "--rename-value", "tags:old-name=new-name", "--in", str(log))

    assert list(Quest.load(path).get("tags")) == ["cli", "new-name", "dx"]


# --- timestamps ------------------------------------------------------------------


def test_migration_does_not_bump_modified(isolated, make_log, write_quest, run):
    """A migration is not a content edit; bumping `modified` would launder staleness."""
    log = make_log(isolated)
    path = write_quest(log, "QST-aaaaa", status="completed", modified="2020-01-01")

    run("migrate", "--rename-value", "status:completed=done", "--in", str(log))

    assert str(Quest.load(path).get("modified")) == "2020-01-01"


def test_migration_does_not_touch_status_changed(isolated, make_log, write_quest, run):
    """Renaming completed->done is the same status under a new name, not a transition."""
    log = make_log(isolated)
    path = write_quest(log, "QST-aaaaa", status="completed", status_changed="2020-01-01")

    run("migrate", "--rename-value", "status:completed=done", "--in", str(log))

    assert str(Quest.load(path).get("status_changed")) == "2020-01-01"


def test_a_no_op_migration_changes_no_mtimes(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", status="todo")
    write_quest(log, "QST-bbbbb", status="todo")
    run("format", str(log))
    mtimes = {p: p.stat().st_mtime_ns for p in log.glob("QST-*.md")}

    run("migrate", "--rename-value", "status:completed=done", "--in", str(log))

    assert {p: p.stat().st_mtime_ns for p in log.glob("QST-*.md")} == mtimes


# --- --dry-run -------------------------------------------------------------------


def test_dry_run_prints_a_per_file_diff_and_writes_nothing(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    path = write_quest(log, "QST-aaaaa", status="completed")
    before = path.read_text()
    mtime_before = path.stat().st_mtime_ns

    result = run("migrate", "--rename-value", "status:completed=done", "--in", str(log), "--dry-run")

    assert result.code == 0
    assert path.read_text() == before
    assert path.stat().st_mtime_ns == mtime_before
    assert "-status: completed" in result.out
    assert "+status: done" in result.out
    assert "QST-aaaaa" in result.out


def test_dry_run_reports_the_same_counts_the_real_run_produces(
    isolated, make_log, write_quest, run
):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", slug="a", status="completed")
    write_quest(log, "QST-bbbbb", slug="b", status="todo")

    dry = run("migrate", "--rename-value", "status:completed=done", "--in", str(log), "--dry-run")
    real = run("migrate", "--rename-value", "status:completed=done", "--in", str(log))

    assert "1 changed" in dry.out
    assert "1 changed" in real.out


# --- scoping ---------------------------------------------------------------------


def test_in_is_repeatable_and_bounds_the_migration(isolated, make_log, write_quest, run):
    alpha = make_log(isolated, "alpha")
    beta = make_log(isolated, "beta")
    gamma = make_log(isolated, "gamma")
    a = write_quest(alpha, "QST-aaaaa", status="completed")
    b = write_quest(beta, "QST-bbbbb", status="completed")
    g = write_quest(gamma, "QST-ggggg", status="completed")

    run(
        "migrate", "--rename-value", "status:completed=done",
        "--in", str(alpha), "--in", str(beta),
    )

    assert Quest.load(a).get("status") == "done"
    assert Quest.load(b).get("status") == "done"
    assert Quest.load(g).get("status") == "completed"


def test_root_narrows_an_all_logs_sweep(isolated, make_log, write_quest, run):
    inside = make_log(isolated / "sub", "alpha")
    outside = make_log(isolated, "beta")
    a = write_quest(inside, "QST-aaaaa", status="completed")
    b = write_quest(outside, "QST-bbbbb", status="completed")

    run("migrate", "--rename-value", "status:completed=done", "-A", "--root", str(isolated / "sub"))

    assert Quest.load(a).get("status") == "done"
    assert Quest.load(b).get("status") == "completed"


def test_all_logs_sweeps_every_log_under_the_root(multi_log, run):
    result = run("migrate", "--rename-value", "status:completed=done", "-A")

    assert result.code == 0
    migrated = next(multi_log["alpha"].glob("QST-a2aaa*.md"))
    assert Quest.load(migrated).get("status") == "done"


def test_summary_names_logs_files_changed_and_skipped(isolated, make_log, write_quest, run):
    log = make_log(isolated, "alpha")
    write_quest(log, "QST-aaaaa", slug="a", status="completed")
    write_quest(log, "QST-bbbbb", slug="b", status="todo")

    result = run("migrate", "--rename-value", "status:completed=done", "--in", str(log))

    assert "1 log" in result.out
    assert "1 changed" in result.out
    assert "1 skipped" in result.out


def test_a_migration_with_no_verb_errors(isolated, make_log, run):
    log = make_log(isolated)

    assert run("migrate", "--in", str(log)).code == 1


def test_a_malformed_rename_value_errors(isolated, make_log, run):
    log = make_log(isolated)

    assert run("migrate", "--rename-value", "nonsense", "--in", str(log)).code == 1


def test_a_malformed_backfill_errors(isolated, make_log, run):
    log = make_log(isolated)

    assert run("migrate", "--backfill", "nonsense", "--in", str(log)).code == 1


# --- --commit --------------------------------------------------------------------


def _git(cwd, *args) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout.strip()


def _repo(root):
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "Test")
    return root


def test_commit_is_opt_in(isolated, make_log, write_quest, run):
    _repo(isolated)
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", status="completed")
    _git(isolated, "add", "-A")
    _git(isolated, "commit", "-qm", "seed")

    run("migrate", "--rename-value", "status:completed=done", "--in", str(log))

    assert _git(isolated, "status", "--porcelain") != ""


def test_commit_produces_one_commit_per_log(isolated, make_log, write_quest, run):
    _repo(isolated)
    alpha = make_log(isolated, "alpha")
    beta = make_log(isolated, "beta")
    write_quest(alpha, "QST-aaaaa", status="completed")
    write_quest(beta, "QST-bbbbb", status="completed")
    _git(isolated, "add", "-A")
    _git(isolated, "commit", "-qm", "seed")
    before = int(_git(isolated, "rev-list", "--count", "HEAD"))

    result = run(
        "migrate", "--rename-value", "status:completed=done",
        "--in", str(alpha), "--in", str(beta), "--commit",
    )

    assert result.code == 0
    assert int(_git(isolated, "rev-list", "--count", "HEAD")) == before + 2
    assert "migrate" in _git(isolated, "log", "-1", "--format=%s")


def test_commit_refuses_outright_on_a_dirty_index(isolated, make_log, write_quest, run):
    _repo(isolated)
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", status="completed")
    _git(isolated, "add", "-A")
    _git(isolated, "commit", "-qm", "seed")
    (isolated / "unrelated.txt").write_text("staged\n")
    _git(isolated, "add", "unrelated.txt")

    result = run("migrate", "--rename-value", "status:completed=done", "--in", str(log), "--commit")

    assert result.code == 1
    assert "dirty" in result.out.lower() or "dirty" in result.err.lower()
    # and it refused *before* mutating anything
    assert Quest.load(next(log.glob("QST-aaaaa*.md"))).get("status") == "completed"


def test_commit_bypasses_local_hooks(isolated, make_log, write_quest, run):
    """A pre-commit hook can't distinguish a trusted, deterministic value
    rename from a hand edit -- it only sees a diff. Concretely,
    `quest-bump-modified`'s own status-transition backfill (QST-3h09k) would
    otherwise read this exact migration as a missed manual transition and
    stamp `status_changed`, undoing the field-preservation rule this module
    documents. `--no-verify` is what keeps that from happening; a hook that
    always fails is the simplest proof it's actually being passed."""
    _repo(isolated)
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", status="completed")
    _git(isolated, "add", "-A")
    _git(isolated, "commit", "-qm", "seed")
    hooks_dir = isolated / ".git" / "hooks"
    pre_commit = hooks_dir / "pre-commit"
    pre_commit.write_text("#!/bin/sh\nexit 1\n")
    pre_commit.chmod(0o755)

    result = run("migrate", "--rename-value", "status:completed=done", "--in", str(log), "--commit")

    assert result.code == 0
    assert "committed" in result.out


def test_commit_with_dry_run_is_refused(isolated, make_log, run):
    log = make_log(isolated)

    result = run(
        "migrate", "--rename-value", "status:completed=done",
        "--in", str(log), "--dry-run", "--commit",
    )

    assert result.code == 1


# --- field placement -------------------------------------------------------------


def test_backfill_places_status_changed_between_created_and_modified(
    isolated, make_log, write_quest, run, absent
):
    """Found on the real corpus: the field was appended after `blocked_by`.

    The ordered-insertion rule lived in set_cmd, so migrate -- the command that
    introduces this field to 122 files -- did not get it.
    """
    log = make_log(isolated)
    path = write_quest(log, "QST-aaaaa", created="2026-01-05", status_changed=absent)

    run("migrate", "--backfill", "status_changed=created", "--in", str(log))

    keys = list(Quest.load(path).frontmatter.keys())
    assert keys.index("created") < keys.index("status_changed") < keys.index("modified")


def test_backfill_of_an_unordered_field_appends(isolated, make_log, write_quest, run, absent):
    log = make_log(isolated)
    path = write_quest(log, "QST-aaaaa", owner=absent)

    run("migrate", "--backfill", "owner=peter", "--in", str(log))

    assert list(Quest.load(path).frontmatter.keys())[-1] == "owner"


def test_backfill_from_a_field_writes_a_value_not_a_yaml_alias(
    isolated, make_log, write_quest, run, absent
):
    """Found on the real corpus: the file read `status_changed: *id001`.

    Assigning the source field's own object makes it appear twice in one
    document, so ruamel emits a YAML anchor/alias pair. It round-trips
    correctly through a YAML parser and is useless to everything else --
    Obsidian's Properties panel, `grep`, and a human reading the file.
    """
    log = make_log(isolated)
    path = write_quest(log, "QST-aaaaa", created="2026-01-05", status_changed=absent)

    run("migrate", "--backfill", "status_changed=created", "--in", str(log))

    text = path.read_text()
    assert "status_changed: 2026-01-05" in text
    assert "*id" not in text
    assert "&id" not in text


def test_backfill_from_a_list_field_does_not_alias_or_share_the_list(
    isolated, make_log, write_quest, run, absent
):
    """A shared *mutable* value is worse than an alias: editing one edits both."""
    log = make_log(isolated)
    path = write_quest(log, "QST-aaaaa", tags=["a", "b"], categories=absent)

    run("migrate", "--backfill", "categories=tags", "--in", str(log))

    text = path.read_text()
    assert "*id" not in text
    quest = Quest.load(path)
    assert list(quest.get("categories")) == ["a", "b"]
    assert quest.get("categories") is not quest.get("tags")
