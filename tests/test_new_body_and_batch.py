"""Tests for QST-xk7js's inbound half: `quest new --body -` and `--batch -`.

These are the missing inbound edge to `quest brief` -- an agent that turned
a spec into N tickets can write them in one call instead of shelling out N
times, and can write a real body instead of only flags.
"""

from __future__ import annotations

from unittest.mock import patch

from questkit.quest import Quest


def _with_stdin(text):
    return patch("sys.stdin.read", return_value=text)


def test_body_dash_reads_the_markdown_body_from_stdin(quest_log, run):
    with _with_stdin("## Spec\n\nDo the thing.\n"):
        result = run("new", "A quest", "--status", "todo", "--body", "-")

    assert result.code == 0
    path = next(quest_log.glob("QST-*.md"))
    assert "Do the thing." in Quest.load(path).body


def test_without_body_the_default_template_is_used(quest_log, run):
    result = run("new", "A quest", "--status", "todo")

    assert result.code == 0
    path = next(quest_log.glob("QST-*.md"))
    body = Quest.load(path).body
    assert body.strip() != ""


def test_batch_creates_one_quest_per_entry_and_prints_ids_in_order(quest_log, run):
    batch = """
- title: First quest
  type: task
  status: todo
  tags: [a]
- title: Second quest
  type: bug
  status: todo
  tags: [b]
"""
    with _with_stdin(batch):
        result = run("new", "--batch", "-")

    assert result.code == 0
    ids = result.lines
    assert len(ids) == 2
    paths = sorted(quest_log.glob("QST-*.md"))
    assert len(paths) == 2
    titles = [Quest.load(p).get("title") for p in paths]
    assert set(titles) == {"First quest", "Second quest"}
    # ids print in the same order the entries were given
    first_id = next(p for p in paths if Quest.load(p).get("title") == "First quest").stem.partition("--")[0]
    assert ids[0] == first_id


def test_batch_entry_set_maps_to_custom_fields(isolated, make_log, run, monkeypatch):
    log = make_log(isolated, schema={"fields": {"component": {"type": "string"}}})
    monkeypatch.chdir(log.parent)
    batch = """
- title: With a component
  type: task
  status: todo
  set: {component: api}
"""
    with _with_stdin(batch):
        result = run("new", "--batch", "-", "--in", str(log))

    assert result.code == 0
    path = next(log.glob("QST-*.md"))
    assert Quest.load(path).get("component") == "api"


def test_batch_entry_body_is_used_verbatim(quest_log, run):
    batch = """
- title: With a body
  type: task
  status: todo
  body: |
    ## Spec
    Custom body content.
"""
    with _with_stdin(batch):
        result = run("new", "--batch", "-")

    assert result.code == 0
    path = next(quest_log.glob("QST-*.md"))
    assert "Custom body content." in Quest.load(path).body


def test_batch_with_a_positional_title_is_a_clear_error(quest_log, run):
    result = run("new", "A title", "--batch", "-")

    assert result.code == 1
    assert "--batch" in result.out or "--batch" in result.err


def test_batch_requires_the_dash_value(quest_log, run):
    result = run("new", "--batch", "literal")

    assert result.code == 1


def test_batch_entry_missing_a_title_is_an_error(quest_log, run):
    with _with_stdin("- type: task\n"):
        result = run("new", "--batch", "-")

    assert result.code == 1
