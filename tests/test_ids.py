"""Tests for quest id generation."""

from questkit.ids import generate_id


def test_generate_id_has_expected_shape(tmp_path):
    quest_id = generate_id(tmp_path)
    assert quest_id.startswith("QST-")
    assert len(quest_id) == len("QST-") + 5


def test_generate_id_avoids_existing_files(tmp_path, monkeypatch):
    sequence = iter(list("aaaaa") + list("bbbbb"))
    monkeypatch.setattr("questkit.ids.secrets.choice", lambda alphabet: next(sequence))
    (tmp_path / "QST-aaaaa--existing.md").write_text("x")

    quest_id = generate_id(tmp_path, length=5)

    assert quest_id == "QST-bbbbb"
