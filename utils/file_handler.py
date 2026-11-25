"""Load and validate flashcard decks stored as JSON.

Two layouts are accepted:

* Array format:  ``[{"front": "...", "back": "..."}, ...]``
* Object format: ``{"cards": [{"front": "...", "back": "..."}, ...]}``

Every problem (missing file, bad JSON syntax, wrong structure, missing or
empty fields) is raised as :class:`FlashcardLoadError` with a message that
is safe to show to the user, so the CLI never has to print a traceback.
"""

import json
from dataclasses import dataclass
from pathlib import Path

REQUIRED_FIELDS = ("front", "back")


class FlashcardLoadError(Exception):
    """A deck could not be read or failed validation."""


@dataclass(frozen=True)
class Flashcard:
    """A single question (front) and its expected answer (back)."""

    front: str
    back: str


def load_flashcards(path):
    """Read the JSON deck at ``path`` and return a list of Flashcards."""
    path = Path(path)
    try:
        raw_text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise FlashcardLoadError(f"Deck file not found: {path}") from None
    except IsADirectoryError:
        raise FlashcardLoadError(
            f"{path} is a directory, not a deck file."
        ) from None
    except UnicodeDecodeError:
        raise FlashcardLoadError(
            f"{path} is not a UTF-8 text file."
        ) from None
    except OSError as exc:
        raise FlashcardLoadError(
            f"Could not read {path}: {exc.strerror or exc}"
        ) from None

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise FlashcardLoadError(
            f"{path} is not valid JSON "
            f"(line {exc.lineno}, column {exc.colno}: {exc.msg})."
        ) from None
    except (ValueError, RecursionError):
        # Valid syntax Python still refuses: >4300-digit numbers, deep nesting.
        raise FlashcardLoadError(
            f"{path} could not be read as JSON: it has a number that is too "
            f"long or nesting that is too deep."
        ) from None

    return parse_flashcards(data, source=str(path))


def parse_flashcards(data, source="deck"):
    """Validate already-decoded JSON ``data`` and build Flashcards."""
    items = _extract_card_list(data, source)
    if not items:
        raise FlashcardLoadError(f"{source} does not contain any flashcards.")
    return [
        _parse_card(item, number, source)
        for number, item in enumerate(items, start=1)
    ]


def _extract_card_list(data, source):
    """Return the raw list of card entries from array or object JSON."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if "cards" not in data:
            raise FlashcardLoadError(
                f'{source}: the top-level object needs a "cards" list.'
            )
        if not isinstance(data["cards"], list):
            raise FlashcardLoadError(f'{source}: "cards" must be a list.')
        return data["cards"]
    raise FlashcardLoadError(
        f"{source}: expected a list of cards or an object with a "
        f'"cards" list, got {type(data).__name__}.'
    )


def _parse_card(item, number, source):
    """Validate a single raw card mapping and return a Flashcard."""
    if not isinstance(item, dict):
        raise FlashcardLoadError(
            f'{source}: card #{number} must be an object with "front" '
            f'and "back" fields.'
        )
    # Accept "Front"/"BACK" etc. so hand-written decks are not rejected
    # over capitalisation alone.
    fields = {str(key).strip().lower(): value for key, value in item.items()}

    missing = [name for name in REQUIRED_FIELDS if name not in fields]
    if missing:
        names = " and ".join(f'"{name}"' for name in missing)
        noun = "field" if len(missing) == 1 else "fields"
        raise FlashcardLoadError(
            f"{source}: card #{number} is missing the {names} {noun}."
        )

    values = {}
    for name in REQUIRED_FIELDS:
        value = fields[name]
        # Numbers are allowed (e.g. "back": 8) but booleans/lists are not.
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            value = str(value)
        if not isinstance(value, str) or not value.strip():
            raise FlashcardLoadError(
                f'{source}: card #{number} has an empty or invalid "{name}" '
                f"field (it must be non-empty text)."
            )
        values[name] = value.strip()

    return Flashcard(front=values["front"], back=values["back"])
