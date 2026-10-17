"""Tests for `quest doctor` (QST-whcdp): a read-only, environment-wide
diagnosis pass -- duplicate ids, sync-conflict copies, orphaned files,
broken configs, stale hook pins, install sanity, env sanity, and
generated-artifact drift.
"""

from __future__ import annotations

import json
import os
import subprocess

from questkit.commands import doctor_cmd


def test_doctor_is_clean_on_a_healthy_single_log(quest_log, run, monkeypatch):
    monkeypatch.setattr(doctor_cmd.shutil, "which", lambda name: None)
    run("new", "A quest", "--status", "todo")

    result = run("doctor")

    assert result.code == 0
    assert "no problems" in result.out.lower()


def test_doctor_json_format_matches_the_validate_finding_shape(quest_log, run, monkeypatch):
    monkeypatch.setattr(doctor_cmd.shutil, "which", lambda name: None)
    result = run("doctor", "--format", "json")

    data = json.loads(result.out)
    assert data == {"findings": [], "summary": {"logs_checked": 1, "problems": 0}}


def test_doctor_is_read_only(quest_log, run):
    quest_id = run("new", "A quest", "--status", "todo").out.strip().split("/")[-1].split("--")[0]
    path = next(quest_log.glob(f"{quest_id}*.md"))
    before = path.read_text()

    run("doctor")

    assert path.read_text() == before


# --- check 1: duplicate ids across logs -------------------------------------


def test_duplicate_ids_across_logs_are_reported(isolated, make_log, write_quest, run):
    log_a = make_log(isolated, "alpha")
    log_b = make_log(isolated, "beta")
    write_quest(log_a, "QST-aaaaa", title="First")
    write_quest(log_b, "QST-aaaaa", title="Second")

    result = run("doctor", "--root", str(isolated))

    assert result.code == 1
    assert "duplicate-id" in result.out
    assert "QST-aaaaa" in result.out


def test_no_duplicate_ids_is_clean(isolated, make_log, write_quest, run, monkeypatch):
    monkeypatch.setattr(doctor_cmd.shutil, "which", lambda name: None)
    log_a = make_log(isolated, "alpha")
    log_b = make_log(isolated, "beta")
    write_quest(log_a, "QST-aaaaa", title="First")
    write_quest(log_b, "QST-bbbbb", title="Second")

    result = run("doctor", "--root", str(isolated))

    assert result.code == 0


# --- check 2: sync-conflict copies -------------------------------------------


def test_sync_conflict_copies_are_reported(quest_log, run):
    quest_id = run("new", "A quest", "--status", "todo").out.strip().split("/")[-1].split("--")[0]
    real = next(quest_log.glob(f"{quest_id}*.md"))
    conflict = real.with_name(real.stem + ".sync-conflict-20260814-120000-ABCDEFG" + real.suffix)
    conflict.write_text(real.read_text(encoding="utf-8"), encoding="utf-8")

    result = run("doctor")

    assert result.code == 1
    assert "sync-conflict" in result.out


# --- check 3: orphaned quest files outside any log ---------------------------


def test_orphaned_quest_file_outside_any_log_is_reported(isolated, make_log, run):
    make_log(isolated, "alpha")
    stray_dir = isolated / "playground" / ".stversions"
    stray_dir.mkdir(parents=True)
    (stray_dir / "QST-x7k2m--stray.md").write_text("---\nid: QST-x7k2m\n---\n")

    result = run("doctor", "--root", str(isolated))

    assert result.code == 1
    assert "orphaned-quest-file" in result.out
    assert "QST-x7k2m" in result.out


def test_a_quest_file_inside_a_real_log_is_not_orphaned(quest_log, run):
    run("new", "A quest", "--status", "todo")

    result = run("doctor")

    assert "orphaned-quest-file" not in result.out


# --- check 4: broken log configs, aggregated ---------------------------------


def test_broken_config_version_is_reported(isolated, make_log, run):
    log = make_log(isolated, "alpha")
    (log / ".questkit.yaml").write_text("version: 99\n")

    result = run("doctor", "--root", str(isolated))

    assert result.code == 1
    assert "broken-config" in result.out


# --- check 5: stale hook pins -------------------------------------------------


def test_stale_hook_pin_is_reported(isolated, run):
    questkit_checkout = isolated / "questkit-checkout"
    questkit_checkout.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=questkit_checkout, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=questkit_checkout, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=questkit_checkout, check=True)
    (questkit_checkout / "f.txt").write_text("x")
    subprocess.run(["git", "add", "f.txt"], cwd=questkit_checkout, check=True)
    subprocess.run(["git", "commit", "-m", "one"], cwd=questkit_checkout, check=True)
    (questkit_checkout / "f.txt").write_text("y")
    subprocess.run(["git", "add", "f.txt"], cwd=questkit_checkout, check=True)
    subprocess.run(["git", "commit", "-m", "two"], cwd=questkit_checkout, check=True)
    actual_head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=questkit_checkout, capture_output=True, text=True, check=True
    ).stdout.strip()

    consumer = isolated / "consumer"
    consumer.mkdir()
    (consumer / ".pre-commit-config.yaml").write_text(
        f"repos:\n"
        f"  - repo: {questkit_checkout}\n"
        f"    rev: stale0000000000000000000000000000000000\n"
        "    hooks:\n"
        "      - id: quest-format\n"
    )

    result = run("doctor", "--root", str(isolated))

    assert result.code == 1
    assert "stale-hook-pin" in result.out
    assert actual_head in result.out


def test_current_hook_pin_is_not_reported(isolated, run):
    questkit_checkout = isolated / "questkit-checkout"
    questkit_checkout.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=questkit_checkout, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=questkit_checkout, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=questkit_checkout, check=True)
    (questkit_checkout / "f.txt").write_text("x")
    subprocess.run(["git", "add", "f.txt"], cwd=questkit_checkout, check=True)
    subprocess.run(["git", "commit", "-m", "one"], cwd=questkit_checkout, check=True)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=questkit_checkout, capture_output=True, text=True, check=True
    ).stdout.strip()

    consumer = isolated / "consumer"
    consumer.mkdir()
    (consumer / ".pre-commit-config.yaml").write_text(
        f"repos:\n"
        f"  - repo: {questkit_checkout}\n"
        f"    rev: {head}\n"
        "    hooks:\n"
        "      - id: quest-validate\n"
    )

    result = run("doctor", "--root", str(isolated))

    assert "stale-hook-pin" not in result.out


# --- check 7: env sanity ------------------------------------------------------


def test_bad_quest_log_env_is_reported(isolated, run, monkeypatch):
    monkeypatch.setenv("QUEST_LOG", str(isolated / "nowhere"))
    monkeypatch.delenv("QST_ROOT", raising=False)

    result = run("doctor", "--root", str(isolated))

    assert result.code == 1
    assert "env" in result.out
    assert "QUEST_LOG" in result.out


def test_bad_qst_root_entry_is_reported(isolated, run, monkeypatch):
    monkeypatch.delenv("QUEST_LOG", raising=False)
    monkeypatch.setenv("QST_ROOT", str(isolated / "nowhere"))

    result = run("doctor", "--root", str(isolated))

    assert result.code == 1
    assert "QST_ROOT" in result.out


def test_valid_env_vars_are_not_reported(isolated, make_log, run, monkeypatch):
    log = make_log(isolated, "alpha")
    monkeypatch.setenv("QUEST_LOG", str(log))
    monkeypatch.delenv("QST_ROOT", raising=False)

    result = run("doctor", "--root", str(isolated))

    assert "QUEST_LOG" not in result.out


# --- check 8: generated-artifact drift ---------------------------------------


def test_stale_template_is_reported(isolated, make_log, run):
    log = make_log(isolated, "alpha")
    template = log / "_template.md"
    template.write_text("stale")
    old = (log / ".questkit.yaml").stat().st_mtime - 10
    os.utime(template, (old, old))

    result = run("doctor", "--root", str(isolated))

    assert result.code == 1
    assert "artifact-drift" in result.out
    assert "_template.md" in result.out


def test_fresh_template_is_not_reported(isolated, make_log, run):
    log = make_log(isolated, "alpha")
    template = log / "_template.md"
    template.write_text("fresh")

    result = run("doctor", "--root", str(isolated))

    assert "artifact-drift" not in result.out


# --- unit tests on the install-sanity check (best-effort, mocked) -----------


def test_shared_venv_version_mismatch_is_reported(monkeypatch):
    monkeypatch.setattr(doctor_cmd.shutil, "which", lambda name: "/usr/bin/quest")

    class _Result:
        stdout = "questkit 0.0.1-stale\n"

    monkeypatch.setattr(doctor_cmd.subprocess, "run", lambda *a, **k: _Result())

    findings = doctor_cmd._check_shared_venv_version_agreement()

    assert len(findings) == 1
    assert "0.0.1-stale" in findings[0].message


def test_shared_venv_matching_version_is_clean(monkeypatch):
    from questkit import __version__

    monkeypatch.setattr(doctor_cmd.shutil, "which", lambda name: "/usr/bin/quest")

    class _Result:
        stdout = f"questkit {__version__}\n"

    monkeypatch.setattr(doctor_cmd.subprocess, "run", lambda *a, **k: _Result())

    assert doctor_cmd._check_shared_venv_version_agreement() == []


def test_no_quest_on_path_is_not_a_problem(monkeypatch):
    monkeypatch.setattr(doctor_cmd.shutil, "which", lambda name: None)

    assert doctor_cmd._check_shared_venv_version_agreement() == []
