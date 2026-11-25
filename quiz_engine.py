"""Quiz engine: question-ordering strategies, a factory, and session stats.

Design patterns
---------------
* Strategy: :class:`QuizMode` is the abstract strategy. Each concrete mode
  (:class:`SequentialMode`, :class:`RandomMode`, :class:`AdaptiveMode`)
  decides which card is served next and may react to answers. The
  :class:`QuizSession` only talks to the ``QuizMode`` interface, so modes
  are interchangeable.
* Factory: :class:`QuizModeFactory` maps a user-supplied name such as
  ``"adaptive"`` to the right concrete class, so callers (the CLI) never
  name a concrete mode.
"""

import random
from abc import ABC, abstractmethod
from collections import Counter, deque
from dataclasses import dataclass, field


class QuizMode(ABC):
    """Strategy interface: decides the order in which cards are asked.

    Usage: call :meth:`next_card` to get a card (``None`` means the quiz is
    over), then :meth:`record_answer` with whether it was answered
    correctly. Modes keep a queue of card *indices* rather than cards so
    that duplicate cards in a deck are tracked separately.
    """

    #: Name used by :class:`QuizModeFactory` and shown to the user.
    name = ""

    def __init__(self, cards):
        """Initialize the strategy with a non-empty sequence of flashcards."""
        if not cards:
            raise ValueError("A quiz needs at least one flashcard.")
        self.cards = tuple(cards)
        self._queue = deque(self._initial_order())
        self._current = None

    @abstractmethod
    def _initial_order(self):
        """Return card indices in the order they are first asked."""

    def _on_answer(self, index, correct):
        """React to an answer for card ``index``. Default: do nothing."""

    def next_card(self):
        """Return the next card to ask, or ``None`` when the quiz is over."""
        if not self._queue:
            self._current = None
            return None
        self._current = self._queue.popleft()
        return self.cards[self._current]

    def record_answer(self, correct):
        """Record whether the card last returned by next_card was right."""
        if self._current is None:
            raise RuntimeError("record_answer() called before next_card().")
        index, self._current = self._current, None
        self._on_answer(index, correct)

    @property
    def remaining(self):
        """Number of cards still queued (not counting the current one)."""
        return len(self._queue)


class SequentialMode(QuizMode):
    """Ask every card once, in deck order (1, 2, 3, ...)."""

    name = "sequential"

    def _initial_order(self):
        """Return indices in original deck order."""
        return list(range(len(self.cards)))


class RandomMode(QuizMode):
    """Ask every card once, in shuffled order."""

    name = "random"

    def __init__(self, cards, rng=None):
        """Initialize random mode with an optional ``random.Random`` RNG."""
        # ``rng`` lets tests pass a seeded random.Random for repeatability.
        self._rng = rng or random.Random()
        super().__init__(cards)

    def _initial_order(self):
        """Return indices shuffled with ``self._rng``."""
        order = list(range(len(self.cards)))
        self._rng.shuffle(order)
        return order


class AdaptiveMode(QuizMode):
    """Ask every card, and bring missed cards back sooner.

    A card answered incorrectly is re-queued ``retry_gap`` places from the
    front of the queue, so it comes back after that many other cards
    instead of at the end of the deck. A card is asked at most
    ``max_attempts`` times so a session always ends.
    """

    name = "adaptive"

    def __init__(self, cards, retry_gap=2, max_attempts=3):
        """Initialize adaptive mode with retry spacing and an attempt cap."""
        if retry_gap < 0:
            raise ValueError("retry_gap cannot be negative.")
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1.")
        self.retry_gap = retry_gap
        self.max_attempts = max_attempts
        self._attempts = Counter()
        super().__init__(cards)

    def _initial_order(self):
        """Start in deck order before adapting to missed answers."""
        return list(range(len(self.cards)))

    def _on_answer(self, index, correct):
        """Re-queue missed card ``index`` after ``retry_gap`` cards."""
        self._attempts[index] += 1
        if correct or self._attempts[index] >= self.max_attempts:
            return
        position = min(self.retry_gap, len(self._queue))
        self._queue.insert(position, index)


class QuizModeFactory:
    """Factory that builds a :class:`QuizMode` from its name."""

    _modes = {
        mode.name: mode for mode in (SequentialMode, RandomMode, AdaptiveMode)
    }

    @classmethod
    def available_modes(cls):
        """Names accepted by :meth:`create`, e.g. for argparse choices."""
        return list(cls._modes)

    @classmethod
    def get_mode_class(cls, mode_name):
        """Return the QuizMode subclass registered under ``mode_name``."""
        key = str(mode_name).strip().lower()
        try:
            return cls._modes[key]
        except KeyError:
            choices = ", ".join(cls._modes)
            raise ValueError(
                f"Unknown quiz mode '{mode_name}'. Choose from: {choices}."
            ) from None

    @classmethod
    def create(cls, mode_name, cards):
        """Instantiate the mode called ``mode_name`` for ``cards``."""
        return cls.get_mode_class(mode_name)(cards)


def normalize_answer(text):
    """Lower-case and collapse whitespace so '  Def ' matches 'def'.

    Punctuation is deliberately kept: stripping it would make '=' match
    '==' (both would normalise to an empty string).
    """
    return " ".join(str(text).split()).casefold()


def check_answer(given, expected):
    """True if ``given`` matches ``expected`` after normalisation."""
    return normalize_answer(given) == normalize_answer(expected)


@dataclass
class QuizStats:
    """Running totals for one quiz session."""

    correct: int = 0
    incorrect: int = 0
    misses: Counter = field(default_factory=Counter)
    cards_seen: set = field(default_factory=set)

    def record(self, card, correct):
        """Record one answered card and update miss counts if incorrect."""
        self.cards_seen.add(card)
        if correct:
            self.correct += 1
        else:
            self.incorrect += 1
            self.misses[card] += 1

    @property
    def answered(self):
        """Total number of questions answered in this session."""
        return self.correct + self.incorrect

    @property
    def accuracy(self):
        """Percentage of answers that were correct (0.0 if none)."""
        if not self.answered:
            return 0.0
        return 100.0 * self.correct / self.answered


@dataclass(frozen=True)
class AnswerResult:
    """Outcome of one submitted answer."""

    correct: bool
    given: str
    expected: str


class QuizSession:
    """Runs a quiz using any QuizMode strategy and keeps the score."""

    def __init__(self, mode):
        """Initialize a session backed by the given ``QuizMode`` strategy."""
        self.mode = mode
        self.stats = QuizStats()
        self.current_card = None

    def next_card(self):
        """Advance to and return the next flashcard, or ``None`` if done."""
        self.current_card = self.mode.next_card()
        return self.current_card

    def submit_answer(self, answer):
        """Grade ``answer`` for the active card and update session state."""
        if self.current_card is None:
            raise RuntimeError("No question is waiting for an answer.")
        card, self.current_card = self.current_card, None
        correct = check_answer(answer, card.back)
        self.stats.record(card, correct)
        self.mode.record_answer(correct)
        return AnswerResult(correct=correct, given=answer, expected=card.back)
