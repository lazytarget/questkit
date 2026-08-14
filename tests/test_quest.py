"""Tests for the Quest frontmatter/body round trip and id lookup."""

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


def test_find_by_id_matches_full_filename(tmp_path):
    (tmp_path / "QST-abcde--example.md").write_text("---\nid: QST-abcde\n---\n\nbody\n")
    (tmp_path / "QST-fghij--other.md").write_text("---\nid: QST-fghij\n---\n\nbody\n")

    found = find_by_id(tmp_path, "QST-abcde")

    assert found is not None
    assert found.name == "QST-abcde--example.md"
    assert find_by_id(tmp_path, "QST-zzzzz") is None
