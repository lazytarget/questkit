"""Tests for QST-5rjla's in-repo pieces: the schema-generated `_template.md`,
`quest new`'s use of a log's own template, and the "Needs attention" Bases
view. The topology.yaml distribution rows and Home Assistant integration are
infrastructure outside this repository -- not testable from it (see the
quest's own Log).
"""

from __future__ import annotations

from datetime import date

from questkit.quest import Quest


def test_init_template_writes_a_template_from_the_schema(isolated, run):
    run("init", str(isolated))

    result = run("init", str(isolated), "--template")

    assert result.code == 0
    template = isolated / "quests" / "_template.md"
    assert template.is_file()
    text = template.read_text()
    assert text.startswith("---")
    assert "{{ id }}" in text
    assert "{{ today }}" in text


def test_template_reflects_the_logs_declared_project(isolated, run):
    run("init", str(isolated), "--project", "family")

    run("init", str(isolated), "--template")

    text = (isolated / "quests" / "_template.md").read_text()
    assert "project: family" in text


def test_template_includes_declared_custom_fields(isolated, make_log, run):
    make_log(isolated, schema={"fields": {"component": {"type": "string"}}})

    run("init", str(isolated), "--template")

    text = (isolated / "quests" / "_template.md").read_text()
    assert "component:" in text


def test_regenerating_after_a_schema_change_updates_it(isolated, make_log, run):
    log = make_log(isolated)
    run("init", str(isolated), "--template")
    before = (log / "_template.md").read_text()
    assert "component" not in before

    import io

    from ruamel.yaml import YAML

    yaml = YAML()
    config_path = log / ".questkit.yaml"
    data = yaml.load(config_path.read_text())
    data["schema"] = {"fields": {"component": {"type": "string"}}}
    buf = io.StringIO()
    yaml.dump(data, buf)
    config_path.write_text(buf.getvalue())

    run("init", str(isolated), "--template")

    after = (log / "_template.md").read_text()
    assert "component:" in after


def test_template_field_names_match_what_new_would_produce(isolated, run):
    run("init", str(isolated))
    run("init", str(isolated), "--template")
    template_text = (isolated / "quests" / "_template.md").read_text()

    result = run("new", "A quest", "--status", "todo")
    quest_id = result.lines[-1].split()[0].split("/")[-1].split("--")[0]
    quest_path = next((isolated / "quests").glob(f"{quest_id}--*.md"))
    real_fields = set(Quest.load(quest_path).frontmatter.keys())

    front, _, _ = template_text.partition("---")[2].partition("---")
    import io

    from ruamel.yaml import YAML

    template_fields = set((YAML().load(io.StringIO(front)) or {}).keys())

    # every field the template offers is one `quest new` actually writes --
    # a placeholder for a field the log doesn't use would mislead a human.
    assert template_fields <= real_fields


def test_template_is_excluded_by_the_quest_pattern(isolated, make_log, run):
    log = make_log(isolated)
    run("init", str(isolated), "--template")

    import fnmatch

    assert not fnmatch.fnmatch("_template.md", "QST-*.md")
    assert (log / "_template.md").exists()


def test_new_uses_the_logs_own_template_when_present(isolated, make_log, run):
    log = make_log(isolated)
    (log / "_template.md").write_text(
        "---\nid: x\n---\n\n## Custom body from the log's own template\n"
    )

    result = run("new", "A quest", "--status", "todo", "--in", str(log))

    assert result.code == 0
    path = next(log.glob("QST-*.md"))
    assert "Custom body from the log's own template" in Quest.load(path).body


def test_new_falls_back_to_the_packaged_template_otherwise(quest_log, run):
    result = run("new", "A quest", "--status", "todo")

    assert result.code == 0
    path = next(quest_log.glob("QST-*.md"))
    body = Quest.load(path).body
    assert "## Description" in body
    assert "## Acceptance Criteria" in body


def test_a_filled_in_template_passes_validate(isolated, make_log, run):
    log = make_log(isolated)
    run("init", str(isolated), "--template")
    template_text = (log / "_template.md").read_text()

    filled = (
        template_text.replace('"{{ id }}"', "QST-aaaaa")
        .replace("{{ today }}", date.today().isoformat())
    )
    (log / "QST-aaaaa--a-real-quest.md").write_text(filled)

    result = run("validate", "--in", str(log))

    assert result.code == 0


def test_template_module_is_gone():
    import pytest

    with pytest.raises(ModuleNotFoundError):
        import questkit.template  # noqa: F401


def test_base_view_includes_needs_attention(isolated, run):
    run("init", str(isolated), "--base")

    text = (isolated / "quests" / "quests.base").read_text()
    assert "Needs attention" in text
