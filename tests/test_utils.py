"""Tests for slugify, in particular non-ASCII transliteration."""

from questkit.utils import slugify


def test_slugify_basic():
    assert slugify("Fix the garage door") == "fix-the-garage-door"


def test_slugify_transliterates_accented_letters_instead_of_dropping_them():
    assert slugify("Anmäla mig på Excellerate kurser") == "anmala-mig-pa-excellerate-kurser"
    assert slugify("Prata med Jonas") == "prata-med-jonas"


def test_slugify_empty_title_falls_back():
    assert slugify("   ") == "untitled"
