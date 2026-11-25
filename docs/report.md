# Flashcard Quizzer: Final Project Report

## 1. Project Overview

Flashcard Quizzer is a command-line study tool written in Python. A user
points it at a JSON deck, picks how the questions should be served, and
answers each card at a prompt. Correct answers are shown in green, incorrect
ones in red with the expected answer, and a score is printed when the deck
ends or the user quits. The project's second purpose was to practise
directing an AI coding agent through a realistic build: splitting the work
into phases, checking what the agent produced, and correcting it when it
was wrong.

The finished application meets every item in the Definition of Done.
`python main.py -m adaptive -f data/python_basics.json` plays a full game;
`quiz_engine.py` contains the Strategy and Factory patterns; all 90 tests
pass; coverage of application code is 100%; and `flake8` reports no errors.
The runtime uses only the Python standard library.

## 2. Architecture

The code is split into three layers, each in its own module.

**Data layer: `utils/file_handler.py`.** `load_flashcards(path)` reads a file
and returns a list of immutable `Flashcard(front, back)` objects. It accepts
both required formats: a bare JSON array of cards, or an object with a
`"cards"` list. Every failure is converted into a single exception type,
`FlashcardLoadError`, with a message written for the user, for example
`data/deck.json: card #2 is missing the "back" field.` Errors are raised with
`from None`, so the original `JSONDecodeError` or `OSError` is not chained
into the output. The loader also handles cases the brief did not list: an
empty deck, a non-object card, a `"cards"` value that is not a list, a
directory passed as a file, a non-UTF-8 file, and an unreadable file. Field
names are matched case-insensitively and numeric values are accepted, so a
hand-written deck with `"Back": 8` loads instead of failing over formatting.

**Logic layer: `quiz_engine.py`.** This module holds the quiz modes, the
factory, answer checking and session statistics. It has no knowledge of the
terminal, which makes it straightforward to test.

**Presentation layer: `main.py` and `utils/colors.py`.** `main.py` parses
arguments with `argparse`, runs the question loop, and formats the summary.
`utils/colors.py` wraps text in ANSI codes and switches colors off when
output is piped, when the `NO_COLOR` environment variable is set, or when
`--no-color` is passed.

## 3. Design Patterns

**Strategy.** `QuizMode` is an abstract base class that defines the interface
every mode shares: `next_card()` returns the next card or `None` when the
quiz is over, and `record_answer(correct)` reports the result. Concrete
modes supply the part that varies. `SequentialMode` and `RandomMode` only
implement `_initial_order()`. `AdaptiveMode` also overrides the
`_on_answer()` hook. `QuizSession` holds a reference to a `QuizMode` and
never checks which subclass it has. Strategy was chosen over `if/elif`
branches inside `QuizSession` so ordering state stays isolated and new modes
require zero changes to session or CLI code.

The adaptive algorithm needed the most thought. "Prioritise cards the user
gets wrong" could mean several things. The final version keeps a queue of
card indices. When a card is missed, it is inserted two positions from the
front, so it returns after two more cards instead of waiting for the end of
the deck. Each card is asked at most three times, which guarantees that a
session ends even if the user never gets a card right. Using indices instead
of the cards themselves means two identical cards in a deck are tracked
separately.

**Factory.** `QuizModeFactory` maps a name to a class, decoupling CLI string
parsing from concrete class imports. `create(name, cards)` returns a
ready-to-use instance, and `get_mode_class(name)` returns the class itself.
Names are case-insensitive, and an unknown name raises a `ValueError` that
lists the valid choices. The CLI builds its `--mode` choices from
`QuizModeFactory.available_modes()`, so registering a new mode in the factory
is enough to make it available on the command line.

## 4. Command-Line Interface

The CLI supports `-f/--file` (required), `-m/--mode` (default `sequential`),
`--stats` and `--no-color`. The brief did not define `--stats`. I took it to
mean a detailed end-of-session report, because the required integration
test is about the final stats calculation. A one-line score is always shown;
with `--stats` the app also prints questions answered, correct, incorrect,
accuracy, unique cards seen, and a list of cards to review, ordered by
number of misses.

Quitting is graceful in every way a user might try. Typing `exit` or `quit`
ends the quiz. Ctrl+C (`KeyboardInterrupt`) and Ctrl+D or closed input
(`EOFError`) are caught around the question loop. In each case the app
prints "Quiz stopped. Goodbye!", reports the score for the questions
answered, and exits with code 0. A bad deck exits with code 1 and an
argument error with argparse's usual code 2, so the tool behaves predictably
in scripts.

Answers are compared after case-folding and collapsing whitespace.
Punctuation is deliberately kept; Section 6 explains why.

## 5. Testing and Quality

The suite has 90 tests in four files and includes every scenario the brief
requires:

- `test_flashcard_loader.py`: `test_load_valid_flashcards_array`,
  `test_load_invalid_json` and `test_load_missing_required_field`, plus the
  object format, every structural error, file-system errors, and a
  parametrised check that every deck in `data/` is valid.
- `test_quiz_modes.py`: `test_quiz_mode_factory` (parametrised over all
  three modes, checking both the class and the instance) and
  `test_adaptive_mode_behavior`, which asserts the exact order
  `A, B, C, A, D, E` when card A is missed once. Further tests cover the
  attempt cap, duplicate cards, seeded shuffling and the abstract base class.
- `test_integration.py`: `test_full_session` loads a three-card file, runs
  it through the factory and a session, answers two correctly and one
  incorrectly, and checks 3 answered, 2 correct, 1 incorrect and 66.7%
  accuracy. Other tests drive the real `main()` with scripted input,
  covering `exit`, Ctrl+C, Ctrl+D, colors and every error path. Two tests
  launch `main.py` as a real subprocess: one plays a complete adaptive game
  of `python_basics.json`, the other confirms a broken deck produces no
  traceback.
- `test_cli.py`: argument parsing, color detection and summary formatting.

`python -m pytest --cov=. --cov-report=html` reports 100% of 275 statements
covered. The configuration in `pyproject.toml` excludes the test files, the
virtual environment and the `__main__` block, so that figure measures only
application code.
`flake8` runs clean with its default 79-character line limit.

## 6. Working with the AI Agent

The build used Claude Code across four phases (loader, engine, CLI, tests),
reviewing every output against a checklist and running it before accepting.
`docs/ai_edit_log.md` records eleven interactions; four shaped the design.

First, the planned answer normaliser stripped punctuation. Checking it
against the sample deck showed that `=` and `==` would both reduce to an
empty string, so a wrong answer to the equality-operator card would be
marked correct. Punctuation is now significant, and a regression test covers
the case.

Second, the first test run failed ten CLI tests. `run_quiz` had been written
with `ask=input` as a default argument, which captured the built-in function
when the module was imported. Later attempts to patch `input` had no effect.
Resolving `input` at call time fixed it, and it is a reminder that "the
tests fail" can point to a design problem rather than a test problem.

Third, an early manual run of adaptive mode scored 2 out of 15 because the
piped answers assumed deck order while the mode had re-queued a missed card.
The application was right and the script was wrong. As a result the adaptive
tests state the expected order explicitly.

Fourth, the mocked Ctrl+C tests only prove that a handler exists. To confirm
a real interrupt is handled, the app was run in a pseudo-terminal and sent
an actual Ctrl+C. It printed the partial score in color and exited cleanly.

The agent was fastest at boilerplate, test scaffolding and edge-case lists.
It needed the most direction where the brief was vague (`--stats`, the
meaning of "prioritise") and where the correct behaviour depended on the
data, as in the `==` example.

## 7. Challenges and Lessons Learned

The main difficulty was ambiguity rather than code. The starter skeleton
referenced in the brief was not in the repository, so the folder layout and
sample decks had to be recreated. Several requirements, including `--stats`,
adaptive ordering and answer matching, needed a decision to be made and
written down before they could be tested. Writing each decision as a test
made it concrete and stops it from regressing.

The second lesson concerns metrics. Running `--cov=.` without configuration
would count the test files and inflate the score. Excluding them gives a
smaller but honest number, which the suite still exceeds comfortably.

## 8. Future Improvements

- Save progress between sessions so adaptive mode can start with the cards a
  user found hardest last time.
- Accept several correct answers per card (for example `"back": ["len",
  "len()"]`) and optional fuzzy matching for longer definitions.
- Add a `--limit N` option for short practice rounds on large decks.
- Package the app with a console entry point so it runs as `flashcards`
  instead of `python main.py`.
