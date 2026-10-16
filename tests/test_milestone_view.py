"""Tests for QST-tok0k's `views.milestone` in the `development` schema.

`views.milestone` is a prefill (`where: ["milestone:exists"], sort:
"milestone:desc,status:asc"`) reachable like any other view. "Which
milestone" needs no dedicated flag -- the existing two-layer view/where
precedence (a caller's own `--where` on a field drops that field's default
out of the view's clause) already answers it, and the burnup counts ride on
`--group-by` (QST-oguay).
"""

from __future__ import annotations

import json
from pathlib import Path

from questkit.config import QuestLogConfig


def test_the_development_schema_declares_views_milestone():
    """Characterization test for schemas/development.yaml,
    which this repo's own log already adopts (see test_agentic_demotion.py)."""
    quests_dir = Path(__file__).resolve().parents[1] / "quests"
    config = QuestLogConfig.load(quests_dir)

    view = config.schema.views["milestone"]
    assert view.where == ("milestone:exists",)
    assert view.sort == "milestone:desc,status:asc"


def _milestone_schema():
    return {
        "fields": {"milestone": {"type": "string"}},
        "views": {"milestone": {"where": ["milestone:exists"], "sort": "milestone:desc,status:asc"}},
    }


def test_milestone_view_is_reachable_via_dash_dash_view(isolated, make_log, write_quest, run):
    log = make_log(isolated, schema=_milestone_schema())
    write_quest(log, "QST-aaaaa", slug="a", status="todo", milestone="0.4.0")
    write_quest(log, "QST-bbbbb", slug="b", status="todo")  # no milestone

    result = run("list", "--in", str(log), "--view", "milestone")

    assert "QST-aaaaa" in result.out
    assert "QST-bbbbb" not in result.out


def test_milestone_view_sorts_by_milestone_desc_then_status_asc(isolated, make_log, write_quest, run):
    log = make_log(isolated, schema=_milestone_schema())
    write_quest(log, "QST-aaaaa", slug="a", status="in-progress", milestone="0.3.0")
    write_quest(log, "QST-bbbbb", slug="b", status="draft", milestone="0.4.0")
    write_quest(log, "QST-ccccc", slug="c", status="todo", milestone="0.4.0")

    result = run("list", "--in", str(log), "--view", "milestone")

    ids = [line.split()[0] for line in result.out.splitlines()[1:] if line.startswith("QST-")]
    # 0.4.0 before 0.3.0 (desc); within 0.4.0, draft before todo (declared status order)
    assert ids == ["QST-bbbbb", "QST-ccccc", "QST-aaaaa"]


def test_a_where_on_milestone_overrides_the_views_own_clause(isolated, make_log, write_quest, run):
    """Two-layer precedence: --where "milestone=0.4.0" replaces the view's own
    milestone:exists clause instead of ANDing with it -- no dedicated 'which
    milestone' flag is needed."""
    log = make_log(isolated, schema=_milestone_schema())
    write_quest(log, "QST-aaaaa", slug="a", status="todo", milestone="0.4.0")
    write_quest(log, "QST-bbbbb", slug="b", status="todo", milestone="0.3.0")

    result = run(
        "list", "--in", str(log), "--view", "milestone", "--where", "milestone=0.4.0",
    )

    assert "QST-aaaaa" in result.out
    assert "QST-bbbbb" not in result.out


def test_burnup_one_liner_group_by_milestone_and_status(isolated, make_log, write_quest, run):
    log = make_log(isolated, schema=_milestone_schema())
    write_quest(log, "QST-aaaaa", slug="a", status="todo", milestone="0.4.0")
    write_quest(log, "QST-bbbbb", slug="b", status="todo", milestone="0.4.0")
    write_quest(log, "QST-ccccc", slug="c", status="done", milestone="0.4.0")
    write_quest(log, "QST-ddddd", slug="d", status="todo")  # no milestone -- excluded by the view

    result = run(
        "list", "--in", str(log), "--view", "milestone", "--group-by", "milestone,status",
        "--format", "json",
    )

    rows = json.loads(result.out)
    assert {"milestone": "0.4.0", "status": "todo", "count": 2} in rows
    assert {"milestone": "0.4.0", "status": "done", "count": 1} in rows
    assert len(rows) == 2


def test_milestone_view_works_under_a_across_multiple_logs(
    isolated, make_log, write_quest, run, monkeypatch
):
    """Stands in for 'works across the four development logs' -- each log
    independently evaluates its own views.milestone (existing -A behavior)."""
    alpha = make_log(isolated / "alpha", "alpha", project="alpha", schema=_milestone_schema())
    beta = make_log(isolated / "beta", "beta", project="beta", schema=_milestone_schema())
    write_quest(alpha, "QST-aaaaa", status="todo", milestone="0.4.0")
    write_quest(alpha, "QST-bbbbb", status="todo")  # no milestone
    write_quest(beta, "QST-ccccc", status="todo", milestone="0.4.0")
    monkeypatch.setenv("QST_ROOT", str(isolated))

    result = run("list", "-A", "--view", "milestone")

    assert "QST-aaaaa" in result.out
    assert "QST-bbbbb" not in result.out
    assert "QST-ccccc" in result.out
