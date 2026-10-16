"""Tests for the Quest frontmatter/body round trip and id lookup."""

import os

from questkit.quest import Quest, find_by_id


def test_quest_round_trip_preserves_fields(tmp_path):
    path = tmp_path / "QST-abcde--example.md"
    path.write_text(
        "---\n"
        "id: QST-abcde\n"
        "title: Example\n"
        "status: draft\n"
        "tags: [a, b]\n"
        "---\n\n"
        "## Description\n\nSome body text.\n"
    )

    quest = Quest.load(path)

    assert quest.get("id") == "QST-abcde"
    assert quest.get("tags") == ["a", "b"]
    assert "Some body text." in quest.body

    quest.set("status", "todo")
    quest.save()

    reloaded = Quest.load(path)
    assert reloaded.get("status") == "todo"
    assert reloaded.get("id") == "QST-abcde"
    assert "Some body text." in reloaded.body


def test_save_normalizes_list_styles(tmp_path):
    from ruamel.yaml.comments import CommentedMap

    fm = CommentedMap()
    fm["id"] = "QST-abcde"
    fm["tags"] = ["a", "b", "c"]
    fm["blocked_by"] = []
    fm["aliases"] = ["QST-abcde"]
    path = tmp_path / "QST-abcde--example.md"
    Quest(path=path, frontmatter=fm, body="## Description\n").save()

    text = path.read_text()
    assert "tags:\n  - a\n  - b\n  - c\n" in text
    assert "blocked_by: []" in text
    # A single-item list still expands to block style -- matches how
    # Obsidian always writes a non-empty array, even with one item.
    assert "aliases:\n  - QST-abcde\n" in text


def test_save_normalizes_date_fields_unquoted(tmp_path):
    path = tmp_path / "QST-abcde--example.md"
    path.write_text(
        "---\n"
        "id: QST-abcde\n"
        "created: '2026-05-25'\n"
        "modified: 2026-08-13\n"
        "due: '2026-09-01'\n"
        "---\n\n"
        "## Description\n"
    )

    Quest.load(path).save()

    text = path.read_text()
    assert "created: 2026-05-25\n" in text
    assert "modified: 2026-08-13\n" in text
    assert "due: 2026-09-01\n" in text
    assert "'" not in text


def test_save_converts_single_quotes_to_double(tmp_path):
    path = tmp_path / "QST-abcde--example.md"
    path.write_text(
        "---\n"
        "id: QST-abcde\n"
        "title: 'Some: Title'\n"
        "tags:\n"
        "  - 'a: b'\n"
        "---\n\n"
        "## Description\n"
    )

    Quest.load(path).save()

    text = path.read_text()
    assert 'title: "Some: Title"' in text
    assert '- "a: b"' in text
    assert "'" not in text


# --- write-only-on-change -------------------------------------------------------
#
# `save()` used to write unconditionally. That makes an mtime-based quiescence
# gate unusable (the designated committer polls for it), produces empty commits
# in `git: auto` logs, and churns Syncthing for files whose bytes never changed.


def test_save_returns_false_and_leaves_the_file_alone_when_nothing_changed(tmp_path):
    path = tmp_path / "QST-abcde--example.md"
    path.write_text(
        "---\nid: QST-abcde\ntitle: Example\nstatus: todo\n---\n\n## Description\n\nBody.\n"
    )
    Quest.load(path).save()  # settle into normalized form first
    before = path.read_text()
    mtime_before = path.stat().st_mtime_ns

    wrote = Quest.load(path).save()

    assert wrote is False
    assert path.read_text() == before
    assert path.stat().st_mtime_ns == mtime_before


def test_save_returns_true_and_writes_when_content_changed(tmp_path):
    path = tmp_path / "QST-abcde--example.md"
    path.write_text("---\nid: QST-abcde\nstatus: todo\n---\n\n## Description\n")
    Quest.load(path).save()

    quest = Quest.load(path)
    quest.set("status", "in-progress")
    wrote = quest.save()

    assert wrote is True
    assert "status: in-progress" in path.read_text()


def test_save_returns_true_for_a_brand_new_file(tmp_path):
    from ruamel.yaml.comments import CommentedMap

    fm = CommentedMap()
    fm["id"] = "QST-abcde"
    path = tmp_path / "QST-abcde--example.md"

    assert Quest(path=path, frontmatter=fm, body="## Description\n").save() is True


def test_save_reports_a_write_when_only_normalization_changes(tmp_path):
    """A file that needs normalizing has changed, even if no field was touched."""
    path = tmp_path / "QST-abcde--example.md"
    path.write_text("---\nid: QST-abcde\ncreated: '2026-05-25'\n---\n\n## Description\n")

    assert Quest.load(path).save() is True
    assert Quest.load(path).save() is False


def test_save_is_idempotent_across_repeated_calls(tmp_path):
    path = tmp_path / "QST-abcde--example.md"
    path.write_text(
        "---\nid: QST-abcde\ntitle: 'Some: Title'\ntags:\n  - a\n---\n\n## Description\n"
    )

    first = Quest.load(path).save()
    settled = path.read_text()

    assert first is True
    for _ in range(3):
        assert Quest.load(path).save() is False
        assert path.read_text() == settled


def test_save_writes_when_the_body_alone_changed(tmp_path):
    path = tmp_path / "QST-abcde--example.md"
    path.write_text("---\nid: QST-abcde\n---\n\n## Description\n\nOriginal.\n")
    Quest.load(path).save()

    quest = Quest.load(path)
    quest.body = "## Description\n\nRewritten.\n"

    assert quest.save() is True
    assert "Rewritten." in path.read_text()


def test_save_does_not_follow_up_a_no_op_with_an_atime_only_touch(tmp_path):
    """The no-op path must not open the file for writing at all."""
    path = tmp_path / "QST-abcde--example.md"
    path.write_text("---\nid: QST-abcde\n---\n\n## Description\n")
    Quest.load(path).save()
    os.chmod(path, 0o444)  # read-only: a write attempt would raise

    try:
        assert Quest.load(path).save() is False
    finally:
        os.chmod(path, 0o644)


def test_find_by_id_matches_full_filename(tmp_path):
    (tmp_path / "QST-abcde--example.md").write_text("---\nid: QST-abcde\n---\n\nbody\n")
    (tmp_path / "QST-fghij--other.md").write_text("---\nid: QST-fghij\n---\n\nbody\n")

    found = find_by_id(tmp_path, "QST-abcde")

    assert found is not None
    assert found.name == "QST-abcde--example.md"
    assert find_by_id(tmp_path, "QST-zzzzz") is None


def test_render_ends_with_a_blank_line_after_the_body(tmp_path):
    path = tmp_path / "QST-aaaaa--t.md"
    path.write_text("---\nid: QST-aaaaa\n---\n\n## Description\n\ntext\n", encoding="utf-8")

    rendered = Quest.load(path).render()

    assert rendered.endswith("text\n\n")
    assert not rendered.endswith("\n\n\n")


def test_render_is_stable_when_the_file_already_ends_with_a_blank_line(tmp_path):
    path = tmp_path / "QST-aaaaa--t.md"
    path.write_text("---\nid: QST-aaaaa\n---\n\n## Description\n\ntext\n\n\n\n", encoding="utf-8")

    quest = Quest.load(path)
    first = quest.render()

    assert first.endswith("text\n\n")
    quest.save()
    assert Quest.load(path).render() == first
    assert path.read_text(encoding="utf-8") == first
