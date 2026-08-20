"""Tests for `field_order` — one rule, driving both `quest new` and `quest format`.

An explicit ordered list, then everything else alphabetically. A three-group
rule (ordered natives -> alphabetical natives -> alphabetical custom) was
rejected because it requires questkit to know which fields are "native", and
that boundary is itself schema-defined: the same quest would sort differently
in two logs, and `quest mv` would silently reorder frontmatter.

`quest new` had its own hardcoded order, so without this every freshly
captured quest was immediately non-conformant and the next `quest format`
rewrote it.
"""

from __future__ import annotations

from questkit import schema
from questkit.quest import Quest


def _keys(path) -> list[str]:
    return list(Quest.load(path).frontmatter.keys())


def _id_of(result) -> str:
    return result.out.strip().split("/")[-1].split("--")[0]


def test_the_default_field_order_is_the_declared_one():
    assert schema.SchemaConfig.default().field_order == (
        "id",
        "title",
        "description",
        "project",
        "type",
        "status",
        "priority",
        "tags",
        "created",
        "status_changed",
        "modified",
    )


def test_format_reorders_frontmatter_to_field_order(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    path = write_quest(log, "QST-aaaaa")
    # write_quest emits its own order; format must impose the schema's.
    run("format", str(log))

    keys = _keys(path)
    ordered = [k for k in schema.SchemaConfig.default().field_order if k in keys]
    assert keys[: len(ordered)] == ordered


def test_fields_absent_from_field_order_sort_alphabetically_after(
    isolated, make_log, write_quest, run
):
    log = make_log(isolated)
    path = write_quest(log, "QST-aaaaa", zebra="z", alpha="a", effort="m")

    run("format", str(log))

    keys = _keys(path)
    order = schema.SchemaConfig.default().field_order
    tail = [k for k in keys if k not in order]
    assert keys[-len(tail) :] == tail  # the tail really is at the end
    assert tail == sorted(tail)
    assert tail.index("alpha") < tail.index("effort") < tail.index("zebra")


def test_quest_new_writes_field_order_directly(quest_log, run):
    """Not just `format` -- otherwise every captured quest is born non-conformant."""
    quest_id = _id_of(run("new", "A quest", "--status", "todo"))
    path = next(quest_log.glob(f"{quest_id}*.md"))

    keys = _keys(path)
    ordered = [k for k in schema.SchemaConfig.default().field_order if k in keys]
    assert keys[: len(ordered)] == ordered


def test_a_freshly_captured_quest_needs_no_reformatting(quest_log, run):
    """The regression this rule exists to prevent."""
    run("new", "A quest", "--status", "todo")

    result = run("format", "--check")

    assert result.code == 0


def test_a_log_can_override_field_order(isolated, make_log, write_quest, run):
    log = make_log(isolated, schema={"field_order": ["title", "id", "status"]})
    path = write_quest(log, "QST-aaaaa")

    run("format", str(log))

    assert _keys(path)[:3] == ["title", "id", "status"]


def test_field_order_is_inherited_through_extends(isolated, make_log, write_schema, write_quest, run):
    write_schema(isolated / "schemas", "base", {"field_order": ["title", "id", "status"]})
    log = make_log(isolated, schema={"extends": "../schemas/base.yaml"})
    path = write_quest(log, "QST-aaaaa")

    run("format", str(log))

    assert _keys(path)[:3] == ["title", "id", "status"]


def test_reordering_alone_counts_as_a_change(isolated, make_log, write_quest, run):
    log = make_log(isolated)
    write_quest(log, "QST-aaaaa")

    first = run("format", str(log))
    second = run("format", str(log))

    assert "1 reformatted" in first.out
    assert "0 reformatted" in second.out


def test_field_order_does_not_invent_missing_fields(isolated, make_log, write_quest, run, absent):
    """Ordering is not backfilling -- that is --fill-defaults' job."""
    log = make_log(isolated)
    path = write_quest(log, "QST-aaaaa", description=absent)

    run("format", str(log))

    assert "description" not in _keys(path)


def test_mv_does_not_reorder_when_both_logs_share_a_schema(
    isolated, make_log, write_quest, run
):
    """The three-group rule's failure mode, asserted absent.

    `mv` legitimately *adds* `project` (it stamps the destination log's), so
    the assertion is about the relative order of the fields both files have --
    which is what would differ under a native-vs-custom rule.
    """
    source = make_log(isolated, "alpha")
    dest = make_log(isolated, "beta")
    path = write_quest(source, "QST-aaaaa", effort="m")
    run("format", str(source))
    before = _keys(path)

    assert run("mv", "QST-aaaaa", str(dest), "--in", str(source)).code == 0

    moved = next(dest.glob("QST-aaaaa*.md"))
    assert [k for k in _keys(moved) if k in before] == before
