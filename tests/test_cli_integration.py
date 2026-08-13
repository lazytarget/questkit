"""End-to-end CLI smoke test: init -> new -> list -> show -> set -> done -> validate."""

import pytest

from questkit.cli import main


@pytest.fixture
def quest_log(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("QUEST_LOG", raising=False)
    assert main(["init"]) == 0
    return tmp_path / "quests"


def test_full_lifecycle(quest_log, capsys):
    assert main(["new", "Fix the garage door", "--type", "task", "--status", "todo"]) == 0
    created_path = capsys.readouterr().out.strip()
    quest_id = created_path.split("/")[-1].split("--")[0]

    assert main(["list"]) == 0
    listed = capsys.readouterr().out
    assert quest_id in listed

    assert main(["show", quest_id]) == 0
    shown = capsys.readouterr().out
    assert "Fix the garage door" in shown

    assert main(["set", quest_id, "priority=high"]) == 0
    capsys.readouterr()

    assert main(["done", quest_id]) == 0
    capsys.readouterr()

    assert main(["show", quest_id]) == 0
    shown_after = capsys.readouterr().out
    assert "status: completed" in shown_after
    assert "priority: high" in shown_after

    assert main(["validate"]) == 0


def test_new_without_init_reports_actionable_error(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("QUEST_LOG", raising=False)

    exit_code = main(["new", "Orphan quest"])

    assert exit_code == 1
    err = capsys.readouterr().err
    assert "quest init" in err


def test_init_is_idempotent(quest_log):
    marker = quest_log / ".questkit.yaml"
    original = marker.read_text()

    assert main(["init"]) == 0

    assert marker.read_text() == original


def test_draft_quest_is_created_without_description(quest_log):
    assert main(["new", "Just an idea"]) == 0
    path = next(quest_log.glob("QST-*.md"))
    assert "description:" not in path.read_text()


def test_init_git_flag_sets_config_mode(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("QUEST_LOG", raising=False)

    assert main(["init", "--git", "auto", "--project", "common"]) == 0

    config_text = (tmp_path / "quests" / ".questkit.yaml").read_text()
    assert "git: auto" in config_text
    assert "project: common" in config_text


def _new_quest_id(quest_log, title, capsys, extra=None):
    assert main(["new", title, "--status", "todo", *(extra or [])]) == 0
    return capsys.readouterr().out.strip().split("/")[-1].split("--")[0]


def test_validate_flags_dangling_blocked_by(quest_log, capsys):
    quest_id = _new_quest_id(quest_log, "Has a bad reference", capsys)
    path = next(quest_log.glob(f"{quest_id}*.md"))
    path.write_text(path.read_text().replace("blocked_by: []", "blocked_by: [QST-zzzzz]"))

    exit_code = main(["validate"])
    err = capsys.readouterr().out

    assert exit_code == 1
    assert "blocked_by references 'QST-zzzzz', not found" in err


def test_validate_flags_dangling_backlink(quest_log, capsys):
    quest_id = _new_quest_id(quest_log, "Has a bad backlink", capsys)
    path = next(quest_log.glob(f"{quest_id}*.md"))
    path.write_text(path.read_text() + "\nSee [[QST-zzzzz--nope]] for context.\n")

    exit_code = main(["validate"])
    err = capsys.readouterr().out

    assert exit_code == 1
    assert "backlink references 'QST-zzzzz', not found" in err


def test_validate_ignores_wikilinks_inside_code_spans_and_fences(quest_log, capsys):
    quest_id = _new_quest_id(quest_log, "Illustrates link syntax", capsys)
    path = next(quest_log.glob(f"{quest_id}*.md"))
    path.write_text(
        path.read_text()
        + "\nUse `[[QST-zzzzz]]` to link a quest.\n"
        + "\n```\nexample: [[QST-yyyyy]]\n```\n"
    )

    assert main(["validate"]) == 0


def test_validate_accepts_real_blocked_by_and_backlink(quest_log, capsys):
    target_id = _new_quest_id(quest_log, "Target quest", capsys)
    source_id = _new_quest_id(quest_log, "Source quest", capsys)
    path = next(quest_log.glob(f"{source_id}*.md"))
    target_path = next(quest_log.glob(f"{target_id}*.md"))
    text = path.read_text().replace("blocked_by: []", f"blocked_by: [{target_id}]")
    text += f"\nSee [[{target_path.stem}]] for context.\n"
    path.write_text(text)

    assert main(["validate"]) == 0


# --- v2: custom schema fields ---------------------------------------------------


def _add_required_sprint_field(quest_log):
    config_path = quest_log / ".questkit.yaml"
    with config_path.open("a", encoding="utf-8") as handle:
        handle.write("schema:\n  fields:\n    sprint:\n      type: string\n      required: true\n")


def test_new_warns_and_null_injects_custom_fields(quest_log, capsys):
    _add_required_sprint_field(quest_log)

    assert main(["new", "Needs a sprint", "--status", "todo"]) == 0
    captured = capsys.readouterr()

    assert "[warning] custom field 'sprint' is uninitialized" in captured.err
    path = next(quest_log.glob("QST-*.md"))
    assert "sprint:" in path.read_text()


def test_validate_fails_on_missing_required_custom_field(quest_log, capsys):
    _add_required_sprint_field(quest_log)
    quest_id = _new_quest_id(quest_log, "Needs a sprint", capsys)

    exit_code = main(["validate"])
    out = capsys.readouterr().out

    assert exit_code == 1
    assert "missing required custom field 'sprint'" in out

    assert main(["set", quest_id, "sprint=42"]) == 0
    capsys.readouterr()
    assert main(["validate"]) == 0


# --- v2: global-id cross-log mutation resolution --------------------------------


def test_set_and_show_resolve_across_logs(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("QUEST_LOG", raising=False)
    proj_a = tmp_path / "proj_a"
    proj_b = tmp_path / "proj_b"
    proj_a.mkdir()
    proj_b.mkdir()
    monkeypatch.chdir(proj_a)
    assert main(["init"]) == 0
    monkeypatch.chdir(proj_b)
    assert main(["init"]) == 0

    monkeypatch.chdir(proj_a)
    assert main(["new", "Cross log quest", "--status", "todo"]) == 0
    quest_id = capsys.readouterr().out.strip().split("/")[-1].split("--")[0]

    monkeypatch.chdir(proj_b)
    monkeypatch.setenv("QST_ROOT", str(tmp_path))
    assert main(["show", quest_id]) == 0
    assert "Cross log quest" in capsys.readouterr().out

    assert main(["set", quest_id, "priority=high"]) == 0
    capsys.readouterr()
    assert main(["show", quest_id]) == 0
    assert "priority: high" in capsys.readouterr().out


def test_set_reports_not_found_when_id_is_nowhere(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("QUEST_LOG", raising=False)
    monkeypatch.setenv("QST_ROOT", str(tmp_path))
    assert main(["init"]) == 0

    exit_code = main(["set", "QST-zzzzz", "priority=high"])

    assert exit_code == 1
    assert "no quest matching id 'QST-zzzzz' found" in capsys.readouterr().out


# --- v2: ambiguous destination guard on `quest new` ------------------------------


def test_new_fails_fast_on_ambiguous_destination(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("QUEST_LOG", raising=False)
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    monkeypatch.chdir(tmp_path / "a")
    assert main(["init"]) == 0
    monkeypatch.chdir(tmp_path / "b")
    assert main(["init"]) == 0

    monkeypatch.chdir(tmp_path)
    exit_code = main(["new", "Should not land anywhere"])

    assert exit_code == 1
    assert "Ambiguous destination" in capsys.readouterr().err
