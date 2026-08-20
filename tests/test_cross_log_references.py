"""Tests for QST-yiep7's qualified cross-log references in `blocked_by`.

A bare id always resolves within the current log (unchanged, and unaffected
by whether other logs are synced). A qualified `project/QST-xxxxx` reference
declares its own scope: if the named log is in the current sweep, the id must
resolve there (error otherwise); if the named log simply is not present on
this device, that is a **note**, never an error -- validation must give the
same verdict on a phone with only half the vault synced as on a workstation
with everything.
"""

from __future__ import annotations

import json


def test_a_bare_id_unresolvable_here_is_still_a_hard_error(isolated, make_log, write_quest, run):
    log = make_log(isolated, "alpha", project="alpha")
    write_quest(log, "QST-bbbbb", slug="b", status="todo", blocked_by=["QST-nonexistent"])

    result = run("validate", "--in", str(log))

    assert result.code == 1
    assert "QST-nonexistent" in result.out


def test_a_qualified_ref_resolving_in_a_swept_log_validates_clean(
    isolated, make_log, write_quest, run, monkeypatch
):
    alpha = make_log(isolated, "alpha", project="alpha")
    beta = make_log(isolated, "beta", project="beta")
    write_quest(alpha, "QST-aaaaa", slug="a", status="todo")
    write_quest(beta, "QST-bbbbb", slug="b", status="todo", blocked_by=["alpha/QST-aaaaa"])
    monkeypatch.setenv("QST_ROOT", str(isolated))

    result = run("validate", "--in", str(beta))

    assert result.code == 0


def test_a_qualified_ref_naming_an_absent_log_is_a_note_not_an_error(
    isolated, make_log, write_quest, run, monkeypatch
):
    beta = make_log(isolated, "beta", project="beta")
    write_quest(beta, "QST-bbbbb", slug="b", status="todo", blocked_by=["work-a/QST-aaaaa"])
    monkeypatch.setenv("QST_ROOT", str(isolated))

    result = run("validate", "--in", str(beta), "--notes")

    assert result.code == 0
    assert "work-a" in result.out


def test_a_qualified_ref_naming_a_present_log_with_a_missing_id_is_an_error(
    isolated, make_log, write_quest, run, monkeypatch
):
    make_log(isolated, "alpha", project="alpha")
    beta = make_log(isolated, "beta", project="beta")
    write_quest(beta, "QST-bbbbb", slug="b", status="todo", blocked_by=["alpha/QST-zzzzz"])
    monkeypatch.setenv("QST_ROOT", str(isolated))

    result = run("validate", "--in", str(beta))

    assert result.code == 1
    assert "alpha/QST-zzzzz" in result.out


def test_an_ambiguous_project_name_downgrades_to_a_note(
    isolated, make_log, write_quest, run, monkeypatch
):
    """Two logs sharing a project name is a corpus problem, but not one that
    should ever block a commit on the wrong machine -- treated the same as an
    absent log."""
    make_log(isolated / "one", "dup", project="dup")
    make_log(isolated / "two", "dup", project="dup")
    beta = make_log(isolated, "beta", project="beta")
    write_quest(beta, "QST-bbbbb", slug="b", status="todo", blocked_by=["dup/QST-aaaaa"])
    monkeypatch.setenv("QST_ROOT", str(isolated))

    result = run("validate", "--in", str(beta), "--notes")

    assert result.code == 0


def test_computed_blocked_honors_a_qualified_ref_under_a_multi_log_sweep(
    isolated, make_log, write_quest, run, monkeypatch
):
    alpha = make_log(isolated, "alpha", project="alpha")
    beta = make_log(isolated, "beta", project="beta")
    write_quest(alpha, "QST-aaaaa", slug="a", status="todo")
    write_quest(beta, "QST-bbbbb", slug="b", status="todo", blocked_by=["alpha/QST-aaaaa"])
    monkeypatch.setenv("QST_ROOT", str(isolated))

    result = run(
        "list", "-A", "--where", "status:exists",
        "--select", "id,blocked", "--format", "json",
    )

    rows = {r["id"]: r["blocked"] for r in json.loads(result.out)}
    assert rows["QST-bbbbb"] is True


def test_a_single_log_sweep_cannot_see_a_qualified_ref_outside_it(
    isolated, make_log, write_quest, run
):
    """`--in` is a bounded search set -- a qualified ref to a log outside it
    contributes nothing to `blocked`, the same as any other out-of-scope id."""
    alpha = make_log(isolated, "alpha", project="alpha")
    beta = make_log(isolated, "beta", project="beta")
    write_quest(alpha, "QST-aaaaa", slug="a", status="todo")
    write_quest(beta, "QST-bbbbb", slug="b", status="todo", blocked_by=["alpha/QST-aaaaa"])

    result = run(
        "list", "--in", str(beta), "--where", "status:exists",
        "--select", "id,blocked", "--format", "json",
    )

    rows = {r["id"]: r["blocked"] for r in json.loads(result.out)}
    assert rows["QST-bbbbb"] is False
