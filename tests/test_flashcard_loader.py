"""Tests for utils.file_handler: loading and validating JSON decks."""

from pathlib import Path

import pytest

from utils.file_handler import (
    Flashcard,
    FlashcardLoadError,
    load_flashcards,
    parse_flashcards,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VALID_CARDS = [
    {"front": "Capital of France?", "back": "Paris"},
    {"front": "2 + 2", "back": "4"},
]


def test_load_valid_flashcards_array(write_deck):
    path = write_deck(VALID_CARDS)

    cards = load_flashcards(path)

    assert cards == [
        Flashcard(front="Capital of France?", back="Paris"),
        Flashcard(front="2 + 2", back="4"),
    ]


def test_load_valid_flashcards_object(write_deck):
    path = write_deck({"title": "Mixed", "cards": VALID_CARDS})

    cards = load_flashcards(path)

    assert [card.back for card in cards] == ["Paris", "4"]


def test_load_invalid_json(write_deck):
    path = write_deck('[{"front": "Q", "back": "A"},')  # truncated file

    with pytest.raises(FlashcardLoadError) as excinfo:
        load_flashcards(path)

    message = str(excinfo.value)
    assert "not valid JSON" in message
    assert "line 1" in message
    # The friendly error must not chain the raw JSONDecodeError.
    assert excinfo.value.__cause__ is None
    assert excinfo.value.__suppress_context__ is True


def test_load_json_python_refuses_to_decode(write_deck):
    # Valid JSON syntax, but json.loads raises a plain ValueError (not a
    # JSONDecodeError) for integers longer than 4300 digits.
    path = write_deck('[{"front": "q", "back": ' + "9" * 5000 + "}]")

    with pytest.raises(FlashcardLoadError, match="number that is too long"):
        load_flashcards(path)


def test_load_missing_required_field(write_deck):
    path = write_deck([
        {"front": "Q1", "back": "A1"},
        {"front": "Q2"},
    ])

    with pytest.raises(FlashcardLoadError, match=r'card #2 .*"back"'):
        load_flashcards(path)


def test_load_missing_both_fields_lists_both(write_deck):
    path = write_deck([{"hint": "nothing useful"}])

    with pytest.raises(FlashcardLoadError, match='"front" and "back" fields'):
        load_flashcards(path)


@pytest.mark.parametrize("bad_value", ["", "   ", None, True, ["a"], {}])
def test_load_rejects_empty_or_non_text_values(write_deck, bad_value):
    path = write_deck([{"front": "Q", "back": bad_value}])

    with pytest.raises(FlashcardLoadError, match='invalid "back"'):
        load_flashcards(path)


def test_numbers_are_accepted_as_text(write_deck):
    path = write_deck([{"front": "2 ** 3", "back": 8}])

    assert load_flashcards(path) == [Flashcard(front="2 ** 3", back="8")]


def test_field_names_are_case_insensitive_and_values_trimmed(write_deck):
    path = write_deck([{"Front": "  Q  ", "BACK": " A "}])

    assert load_flashcards(path) == [Flashcard(front="Q", back="A")]


def test_object_without_cards_key(write_deck):
    path = write_deck({"deck": VALID_CARDS})

    with pytest.raises(FlashcardLoadError, match='needs a "cards" list'):
        load_flashcards(path)


def test_cards_key_must_be_a_list(write_deck):
    path = write_deck({"cards": {"front": "Q", "back": "A"}})

    with pytest.raises(FlashcardLoadError, match='"cards" must be a list'):
        load_flashcards(path)


@pytest.mark.parametrize("data", ['"just a string"', "42", "null"])
def test_top_level_must_be_list_or_object(write_deck, data):
    path = write_deck(data)

    with pytest.raises(FlashcardLoadError, match="expected a list of cards"):
        load_flashcards(path)


def test_card_must_be_an_object(write_deck):
    path = write_deck([["Q", "A"]])

    with pytest.raises(FlashcardLoadError, match="card #1 must be an object"):
        load_flashcards(path)


@pytest.mark.parametrize("data", [[], {"cards": []}])
def test_empty_deck_is_rejected(write_deck, data):
    path = write_deck(data)

    with pytest.raises(FlashcardLoadError, match="does not contain any"):
        load_flashcards(path)


def test_missing_file(tmp_path):
    with pytest.raises(FlashcardLoadError, match="not found"):
        load_flashcards(tmp_path / "missing.json")


def test_directory_instead_of_file(tmp_path):
    with pytest.raises(FlashcardLoadError, match="is a directory"):
        load_flashcards(tmp_path)


def test_non_utf8_file(tmp_path):
    path = tmp_path / "latin1.json"
    path.write_bytes(b'[{"front": "caf\xe9", "back": "x"}]')

    with pytest.raises(FlashcardLoadError, match="not a UTF-8 text file"):
        load_flashcards(path)


def test_unreadable_file(write_deck, monkeypatch):
    path = write_deck(VALID_CARDS)

    def deny(*args, **kwargs):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(type(path), "read_text", deny)

    with pytest.raises(FlashcardLoadError, match="Permission denied"):
        load_flashcards(path)


def test_parse_flashcards_uses_source_in_messages():
    with pytest.raises(FlashcardLoadError, match="^my_deck: "):
        parse_flashcards([{"front": "Q"}], source="my_deck")


@pytest.mark.parametrize(
    "deck_path",
    sorted((PROJECT_ROOT / "data").glob("*.json")),
    ids=lambda path: path.name,
)
def test_bundled_decks_are_valid(deck_path):
    assert len(load_flashcards(deck_path)) > 0
