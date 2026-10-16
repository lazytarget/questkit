"""Tests for QST-njwu7's `quest validate --format json`.

Machine-readable findings so agents/CI can consume `quest validate` results
without scraping stderr prose. Text output stays the default -- this is an
opt-in `--format json`, not a replacement. Exit-code semantics are identical
in both modes; `--format json` composes with `--report FILE` (the JSON goes
to stdout, the Markdown note still goes to FILE) and with `--no-notes`.

Output shape: a JSON object `{"findings": [...], "summary": {...}}`.
Each finding is `{file, id, kind, rule, message}` -- `kind` is `"error"` or
`"note"`, `rule` is a stable slug naming which check produced it. `summary`
carries `{checked, errors, notes}`, the same three numbers the text
summary line reports.
"""

from __future__ import annotations

import json


def test_json_output_is_an_object_with_findings_and_summary(
    isolated, make_log, write_quest, run
):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", status="nonsense")

    result = run("validate", "--in", str(log), "--format", "json")

    data = json.loads(result.out)
    assert "findings" in data
    assert "summary" in data


def test_a_finding_has_the_documented_shape(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", status="nonsense")

    result = run("validate", "--in", str(log), "--format", "json")

    data = json.loads(result.out)
    assert len(data["findings"]) >= 1
    finding = data["findings"][0]
    assert set(finding) == {"file", "id", "kind", "rule", "message"}
    assert finding["kind"] == "error"
    assert finding["id"] == "QST-aaaaa"
    assert "status" in finding["message"]


def test_notes_appear_as_kind_note_by_default(isolated, make_log, write_quest, run):
    """Slug drift is a note, not an error -- see test_validate_notes.py."""
    log = make_log(isolated)
    path = write_quest(log, "QST-aaaaa", slug="original-slug")
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        lines.append("title: A completely different title" if line.startswith("title:") else line)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = run("validate", "--in", str(log), "--format", "json")

    data = json.loads(result.out)
    kinds = {f["kind"] for f in data["findings"]}
    assert "note" in kinds
    assert "error" not in kinds


def test_no_notes_excludes_notes_from_json(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    path = write_quest(log, "QST-aaaaa", slug="original-slug")
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        lines.append("title: A completely different title" if line.startswith("title:") else line)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = run("validate", "--in", str(log), "--format", "json", "--no-notes")

    data = json.loads(result.out)
    assert data["findings"] == []


def test_summary_counts_match_text_mode(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", status="nonsense")
    write_quest(log, "QST-bbbbb", status="todo")

    result = run("validate", "--in", str(log), "--format", "json")

    data = json.loads(result.out)
    assert data["summary"] == {"checked": 2, "errors": 1, "notes": 0}


def test_exit_code_is_identical_to_text_mode(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", status="nonsense")

    result = run("validate", "--in", str(log), "--format", "json")

    assert result.code == 1


def test_a_clean_log_exits_zero_with_empty_findings(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", status="todo")

    result = run("validate", "--in", str(log), "--format", "json")

    data = json.loads(result.out)
    assert result.code == 0
    assert data["findings"] == []
    assert data["summary"] == {"checked": 1, "errors": 0, "notes": 0}


def test_json_composes_with_report_writing_markdown_and_json_separately(
    isolated, make_log, write_quest, run
):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", status="nonsense")
    report = log / "_validation.md"

    result = run("validate", "--in", str(log), "--format", "json", "--report", str(report))

    json.loads(result.out)  # stdout is still valid JSON, not interleaved with the report
    assert report.is_file()
    assert "error" in report.read_text().lower()


def test_text_format_is_still_the_default(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", status="nonsense")

    result = run("validate", "--in", str(log))

    assert "[quest validate]" in result.out
    assert "error:" in result.out


# --- QST-hzlny: a scalar in a list field is ONE type error ----------------


def test_scalar_in_blocked_by_is_one_list_type_error(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa", blocked_by="QST-eg94z")

    result = run("validate", "--in", str(log), "--format", "json")

    findings = json.loads(result.out)["findings"]
    assert [f["rule"] for f in findings] == ["list-type"]
    assert findings[0]["message"] == "blocked_by must be a list, got string 'QST-eg94z'"
    assert result.code == 1


def test_scalar_in_custom_list_field_is_a_list_type_error(isolated, make_log, write_quest, run):
    log = make_log(isolated, schema={"fields": {"owners": {"type": "list"}}})
    write_quest(log, "QST-aaaaa", owners="ann")

    result = run("validate", "--in", str(log), "--format", "json")

    findings = json.loads(result.out)["findings"]
    assert [f["rule"] for f in findings] == ["list-type"]
    assert "owners must be a list" in findings[0]["message"]


def test_real_lists_do_not_trigger_the_list_type_rule(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-bbbbb")
    write_quest(log, "QST-aaaaa", blocked_by=["QST-bbbbb"])

    result = run("validate", "--in", str(log), "--format", "json")

    assert json.loads(result.out)["findings"] == []
