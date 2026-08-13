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


def test_find_by_id_matches_full_filename(tmp_path):
    (tmp_path / "QST-abcde--example.md").write_text("---\nid: QST-abcde\n---\n\nbody\n")
    (tmp_path / "QST-fghij--other.md").write_text("---\nid: QST-fghij\n---\n\nbody\n")

    found = find_by_id(tmp_path, "QST-abcde")

    assert found is not None
    assert found.name == "QST-abcde--example.md"
    assert find_by_id(tmp_path, "QST-zzzzz") is None
