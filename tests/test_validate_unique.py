"""Tests for QST-5brm7's `unique: true` custom-field constraint.

Log-scoped, like every other validation rule -- no cross-log uniqueness
concept. Belongs in the CLI validate loop (needs the whole log in view), not
in `schema.validate_quest()`, which only ever sees one file at a time -- the
same split as cross-reference resolution (`blocked_by`, wikilinks). Null and
absent values are exempt: nothing to collide with.
"""

from __future__ import annotations


def _schema():
    return {"fields": {"external_id": {"type": "string", "unique": True}}}


def test_duplicate_non_null_values_are_a_validate_error(isolated, make_log, write_quest, run):
    log = make_log(isolated, schema=_schema())
    write_quest(log, "QST-aaaaa", external_id="X1")
    write_quest(log, "QST-bbbbb", external_id="X1")

    result = run("validate", "--in", str(log))

    assert result.code == 1
    assert "error:" in result.out
    assert "external_id" in result.out
    assert "QST-aaaaa" in result.out
    assert "QST-bbbbb" in result.out


def test_the_error_names_both_files(isolated, make_log, write_quest, run):
    log = make_log(isolated, schema=_schema())
    write_quest(log, "QST-aaaaa", external_id="X1")
    write_quest(log, "QST-bbbbb", external_id="X1")

    result = run("validate", "--in", str(log))

    # One of the pair carries the error naming the other, or each names the
    # other -- either way both filenames must appear somewhere in the output.
    assert result.out.count("QST-aaaaa") >= 1
    assert result.out.count("QST-bbbbb") >= 1


def test_distinct_values_are_not_flagged(isolated, make_log, write_quest, run):
    log = make_log(isolated, schema=_schema())
    write_quest(log, "QST-aaaaa", external_id="X1")
    write_quest(log, "QST-bbbbb", external_id="X2")

    result = run("validate", "--in", str(log))

    assert result.code == 0
    assert "external_id" not in result.out


def test_null_values_are_exempt_from_the_constraint(isolated, make_log, write_quest, run, absent):
    log = make_log(isolated, schema=_schema())
    write_quest(log, "QST-aaaaa", external_id=absent)
    write_quest(log, "QST-bbbbb", external_id=absent)

    result = run("validate", "--in", str(log))

    assert result.code == 0


def test_a_non_unique_field_is_unaffected_even_when_shared(isolated, make_log, write_quest, run):
    log = make_log(isolated, schema={"fields": {"component": {"type": "string"}}})
    write_quest(log, "QST-aaaaa", component="core")
    write_quest(log, "QST-bbbbb", component="core")

    result = run("validate", "--in", str(log))

    assert result.code == 0


def test_three_way_duplicate_reports_one_error_per_file(isolated, make_log, write_quest, run):
    log = make_log(isolated, schema=_schema())
    write_quest(log, "QST-aaaaa", external_id="X1")
    write_quest(log, "QST-bbbbb", external_id="X1")
    write_quest(log, "QST-ccccc", external_id="X1")

    result = run("validate", "--in", str(log))

    assert result.code == 1
    assert "3 quest(s) checked, 3 error(s)" in result.out
