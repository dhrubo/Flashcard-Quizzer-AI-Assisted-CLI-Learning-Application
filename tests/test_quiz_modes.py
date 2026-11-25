"""Tests for the quiz engine: strategies, factory, answers and stats."""

import random

import pytest

from quiz_engine import (
    AdaptiveMode,
    QuizMode,
    QuizModeFactory,
    QuizSession,
    QuizStats,
    RandomMode,
    SequentialMode,
    check_answer,
)
from utils.file_handler import Flashcard


def drain(mode, wrong=()):
    """Play ``mode`` to the end; fronts listed in ``wrong`` are missed.

    Returns the fronts in the order they were asked.
    """
    asked = []
    while (card := mode.next_card()) is not None:
        asked.append(card.front)
        mode.record_answer(card.front not in wrong)
    return asked


# --- Factory ---------------------------------------------------------------

@pytest.mark.parametrize(
    "name, expected_class",
    [
        ("sequential", SequentialMode),
        ("random", RandomMode),
        ("adaptive", AdaptiveMode),
    ],
)
def test_quiz_mode_factory(cards, name, expected_class):
    assert QuizModeFactory.get_mode_class(name) is expected_class

    mode = QuizModeFactory.create(name, cards)

    assert type(mode) is expected_class
    assert isinstance(mode, QuizMode)


def test_factory_is_case_and_whitespace_insensitive(cards):
    assert isinstance(QuizModeFactory.create("  Adaptive ", cards),
                      AdaptiveMode)


def test_factory_rejects_unknown_mode(cards):
    with pytest.raises(ValueError, match="Unknown quiz mode 'hardcore'"):
        QuizModeFactory.create("hardcore", cards)


def test_factory_lists_available_modes():
    assert QuizModeFactory.available_modes() == [
        "sequential", "random", "adaptive",
    ]


# --- Strategy base class ---------------------------------------------------

def test_quiz_mode_is_abstract(cards):
    with pytest.raises(TypeError):
        QuizMode(cards)


@pytest.mark.parametrize("mode_class", [SequentialMode, RandomMode,
                                        AdaptiveMode])
def test_modes_require_cards(mode_class):
    with pytest.raises(ValueError, match="at least one flashcard"):
        mode_class([])


def test_record_answer_before_next_card_is_an_error(cards):
    mode = SequentialMode(cards)

    with pytest.raises(RuntimeError):
        mode.record_answer(True)


def test_remaining_counts_queued_cards(cards):
    mode = SequentialMode(cards)
    assert mode.remaining == 5

    mode.next_card()

    assert mode.remaining == 4


# --- Sequential & Random ---------------------------------------------------

def test_sequential_mode_keeps_deck_order(cards):
    mode = SequentialMode(cards)

    assert drain(mode, wrong={"B"}) == ["A", "B", "C", "D", "E"]
    assert mode.next_card() is None


def test_random_mode_asks_each_card_once_in_shuffled_order(cards):
    first = drain(RandomMode(cards, rng=random.Random(7)))
    again = drain(RandomMode(cards, rng=random.Random(7)))
    other = drain(RandomMode(cards, rng=random.Random(8)))

    assert sorted(first) == ["A", "B", "C", "D", "E"]
    assert first == again  # same seed, same order
    assert first != other  # different seed, different order


def test_random_mode_does_not_repeat_wrong_cards(cards):
    asked = drain(RandomMode(cards, rng=random.Random(1)),
                  wrong={"A", "B", "C", "D", "E"})

    assert sorted(asked) == ["A", "B", "C", "D", "E"]


# --- Adaptive --------------------------------------------------------------

def test_adaptive_mode_behavior(cards):
    """A missed card comes back (ahead of unseen cards); others do not."""
    mode = AdaptiveMode(cards, retry_gap=2)

    asked = []
    missed_once = set()
    while (card := mode.next_card()) is not None:
        asked.append(card.front)
        # Miss "A" the first time only, answer everything else correctly.
        correct = not (card.front == "A" and "A" not in missed_once)
        if not correct:
            missed_once.add("A")
        mode.record_answer(correct)

    assert asked.count("A") == 2
    assert all(asked.count(front) == 1 for front in "BCDE")
    # Re-asked after a 2-card gap, before the unseen cards D and E.
    assert asked == ["A", "B", "C", "A", "D", "E"]


def test_adaptive_mode_stops_repeating_after_max_attempts(cards):
    mode = AdaptiveMode(cards, max_attempts=3)

    asked = drain(mode, wrong={"C"})

    assert asked.count("C") == 3
    assert len(asked) == 7


def test_adaptive_mode_repeats_immediately_when_nothing_else_left():
    mode = AdaptiveMode([Flashcard("Only", "card")], max_attempts=2)

    assert drain(mode, wrong={"Only"}) == ["Only", "Only"]


def test_adaptive_mode_tracks_duplicate_cards_separately():
    duplicate = Flashcard("Same", "card")
    mode = AdaptiveMode([duplicate, duplicate], max_attempts=2)

    # Both copies are missed twice each before the quiz gives up.
    assert drain(mode, wrong={"Same"}) == ["Same"] * 4


@pytest.mark.parametrize("kwargs", [{"retry_gap": -1}, {"max_attempts": 0}])
def test_adaptive_mode_validates_options(cards, kwargs):
    with pytest.raises(ValueError):
        AdaptiveMode(cards, **kwargs)


# --- Answer checking & session ---------------------------------------------

@pytest.mark.parametrize(
    "given, expected, result",
    [
        ("def", "def", True),
        ("  DEF ", "def", True),
        ("design   pattern", "Design pattern", True),
        ("=", "==", False),  # punctuation matters
        ("", "def", False),
        ("define", "def", False),
    ],
)
def test_check_answer(given, expected, result):
    assert check_answer(given, expected) is result


def test_stats_accuracy_with_no_answers_is_zero():
    assert QuizStats().accuracy == 0.0


def test_session_scores_answers_and_feeds_the_strategy(cards):
    session = QuizSession(AdaptiveMode(cards[:1], max_attempts=2))

    session.next_card()
    first = session.submit_answer("wrong")
    session.next_card()  # the adaptive mode re-asks the missed card
    second = session.submit_answer("a")

    assert (first.correct, first.expected, first.given) == (False, "a",
                                                            "wrong")
    assert second.correct is True
    assert session.next_card() is None
    assert session.stats.answered == 2
    assert session.stats.misses == {cards[0]: 1}


def test_submit_answer_without_question_is_an_error(cards):
    with pytest.raises(RuntimeError):
        QuizSession(SequentialMode(cards)).submit_answer("a")
