"""Shared pytest fixtures."""

import json

import pytest

from utils.file_handler import Flashcard


@pytest.fixture
def write_deck(tmp_path):
    """Write ``content`` to a temp file and return its path.

    Python objects are dumped as JSON; strings are written verbatim so
    tests can create deliberately broken files.
    """
    def _write(content, name="deck.json"):
        path = tmp_path / name
        if isinstance(content, str):
            path.write_text(content, encoding="utf-8")
        else:
            path.write_text(json.dumps(content), encoding="utf-8")
        return path

    return _write


@pytest.fixture
def cards():
    """Five simple cards: A/a, B/b, ... E/e."""
    return [Flashcard(front=letter, back=letter.lower()) for letter in "ABCDE"]
