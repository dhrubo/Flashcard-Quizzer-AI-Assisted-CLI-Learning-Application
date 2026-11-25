# AI Interaction and Code Review Log

**Tool:** Claude Code (desktop app), model Claude Opus 5.5
**Date:** 2026-11-25
**Workflow:** Four-phase build (1. Data layer & JSON loader, 2. Strategy & Factory quiz engine, 3. CLI & ANSI feedback, 4. Automated test suite & independent audit).

---

## AI Code Review Checklist

Every AI-generated plan, function, and test was reviewed against the following six-point checklist before acceptance:

- [x] **1. PEP 8 & Readability:** Strict 79-character lines (`flake8` clean), clear naming, small single-responsibility functions, and docstrings on all modules, classes, functions, and methods.
- [x] **2. Input Validation & Safe Error Handling:** Malformed JSON, missing/empty fields, invalid types, unreadable files, and numeric/recursion limits raise a clean `FlashcardLoadError` (`from None`) — never exposing raw Python tracebacks.
- [x] **3. Design Pattern Fidelity:** Strategy (`QuizMode` ABC + concrete modes) and Factory (`QuizModeFactory`) serve genuine decoupling purposes without `if/elif` mode checks in `QuizSession` or `main.py`.
- [x] **4. Edge Cases & Termination:** Empty decks, duplicate cards, zero-answered sessions, non-TTY pipes, `Ctrl+C` / `EOFError`, and bounded retries (`max_attempts=3`) so adaptive sessions always terminate.
- [x] **5. Correctness Against Real Deck Data:** String normalisation and ordering rules verified against actual cards in `data/*.json` (e.g., `=` vs. `==`).
- [x] **6. Testability & Honest Coverage:** Dependency seams work cleanly under `pytest` (`monkeypatch`, `capsys`, seeded `random.Random`, subprocesses), and `pyproject.toml` excludes `tests/*` and `.venv/*` so coverage reflects application code only (`100%`).

---

## Detailed AI Interactions

Each entry documents the **prompt used**, the **AI response / initial output**, the **checklist review & decision** (`Accepted`, `Modified`, or `Rejected`), and **how the result was verified**.

---

### 1. Bootstrapping Missing Starter Skeleton & Sample Decks

- **Prompt Used:**
  > "Inspect `/voc/work/project/starter` and the current repository structure, then implement Phase 1 (`utils/file_handler.py`) to load flashcards from both JSON array and object (`{"cards": [...]}`) formats without leaking tracebacks."
- **AI Response / Initial Output:**
  > Reported that `/voc/work/project/starter` did not exist on the local machine and the repository was empty. Proposed creating `main.py`, `quiz_engine.py`, `utils/file_handler.py`, `tests/`, `docs/`, and sample decks (`data/glossary.json` in array format, `data/python_basics.json` and `data/design_patterns.json` in object format).
- **Checklist Review & Decision (`Accepted` with explicit constraint):**
  - Checked against **Checklist #2 (Input Validation)** and **#5 (Real Deck Data)**. Rather than letting the agent silently assume a single JSON layout, I required sample decks covering *both* schemas plus tricky operator answers (`==`, `8`) to stress-test the loader and answer checker.
- **Verification:** `test_bundled_decks_are_valid` parametrises over every `data/*.json` file so broken deck schemas fail CI immediately.
- **Refined Prompt (for reuse):**
  > "The starter files are not in this repo. Create the folder structure from the brief and sample decks in both JSON formats (`[...]` and `{"cards": [...]}`); list any files or schemas you had to invent."

---

### 2. Resolving Ambiguous `--stats` CLI Specification

- **Prompt Used:**
  > "Plan Phase 3 (`main.py`): implement `argparse` flags `-f/--file`, `-m/--mode`, and `--stats`, colored feedback, and graceful `exit` / `Ctrl+C` handling. Propose options for `--stats` before writing code."
- **AI Response / Initial Output:**
  > Outlined three interpretations for `--stats`:
  > (a) inspect deck metadata (card count, average length) and exit without quizzing,
  > (b) persist historical scores to a hidden JSON file across runs, or
  > (c) always show a one-line score and, when `--stats` is passed, append a detailed end-of-session breakdown (answered, correct, incorrect, accuracy, unique cards seen, and missed cards ordered by miss count).
- **Checklist Review & Decision (`Accepted` Option C, `Rejected` Options A & B):**
  - Checked against **Checklist #1 (Readability/Simplicity)** and **#6 (Testability)**. Option B added unrequested file-state complexity; Option A conflicted with the required integration test checking end-of-session stats calculation. Option C keeps runs stateless while making `--stats` genuinely useful for studying.
- **Verification:** `test_cli_full_session` asserts the detailed block is omitted by default; `test_cli_stats_flag_prints_detailed_report` verifies all fields and missed-card ordering.

---

### 3. Answer Normalisation: Rejecting Punctuation Stripping

- **Prompt Used:**
  > "Implement `normalize_answer(text)` and `check_answer(given, expected)` in `quiz_engine.py` so minor formatting differences (casing, extra spaces) don't penalise the user."
- **AI Response / Initial Output:**
  ```python
  def normalize_answer(text):
      cleaned = re.sub(r"[^\w\s]", "", str(text))
      return " ".join(cleaned.split()).casefold()
  ```
  > Proposed stripping punctuation alongside case-folding and whitespace collapsing so `"def."` would match `"def"`.
- **Checklist Review & Decision (`Rejected` punctuation stripping):**
  - Flagged by **Checklist #5 (Correctness Against Real Deck Data)**. `data/python_basics.json` contains `"Which operator checks whether two values are equal?"` → `"=="`. Stripping non-word characters turns both `"="` (assignment, wrong) and `"=="` (equality, right) into `""`, marking wrong answers `Correct!`.
  - **Modification:** Kept only `.split()` whitespace collapsing and `.casefold()`; punctuation remains significant.
- **Verification:** `test_check_answer` explicitly tests `("=", "==", False)`, `("  DEF ", "def", True)`, and `("design   pattern", "Design pattern", True)`.

---

### 4. Adaptive Mode: Rejecting Card-Keyed Dicts & Unbounded Retries

- **Prompt Used:**
  > "Design `QuizMode` (Strategy ABC), `SequentialMode`, `RandomMode`, `AdaptiveMode`, and `QuizModeFactory` in `quiz_engine.py`. In `AdaptiveMode`, prioritise cards the user answers incorrectly."
- **AI Response / Initial Output:**
  ```python
  class AdaptiveMode(QuizMode):
      def __init__(self, cards):
          self._queue = deque(cards)
          self._misses = Counter()  # keyed by Flashcard instance

      def record_answer(self, card, correct):
          if not correct:
              self._misses[card] += 1
              self._queue.appendleft(card)
  ```
- **Checklist Review & Decision (`Rejected` initial algorithm; `Modified` design):**
  - Flagged by **Checklist #3 (Design Pattern Fidelity)** and **#4 (Edge Cases & Termination)** for three flaws:
    1. `Flashcard` is `@dataclass(frozen=True)`, so two identical cards in a deck share the same hash and merge attempt tracking.
    2. `appendleft(card)` re-asks a missed card *immediately* on the very next turn (testing short-term echo rather than recall), while `append(card)` buries it at the end of a large deck.
    3. Without an attempt cap, missing a card repeatedly causes an infinite loop.
  - **Modification:** `QuizMode` queues **card indices** (`0..n-1`) rather than `Flashcard` objects; `AdaptiveMode` re-inserts missed indices `retry_gap=2` slots ahead (`min(self.retry_gap, len(self._queue))`) and caps each card at `max_attempts=3`.
- **Verification:** `test_adaptive_mode_behavior` (`A, B, C, A, D, E`), `test_adaptive_mode_stops_repeating_after_max_attempts`, and `test_adaptive_mode_tracks_duplicate_cards_separately`.

---

### 5. Fixing Import-Time `input` Binding in `run_quiz`

- **Prompt Used:**
  > "Write unit and integration tests in `tests/test_cli.py` and `tests/test_integration.py` using `monkeypatch` on `builtins.input` and `capsys` to test full CLI sessions, `exit`, and `Ctrl+C`."
- **AI Response / Initial Output:**
  > Generated `main.py` earlier with:
  ```python
  def run_quiz(session, colors, ask=input):
      ...
      answer = ask("> ")
  ```
  > On the first `pytest` run, 10 CLI integration tests failed with `OSError: pytest: reading from stdin while output is captured!`.
- **Checklist Review & Decision (`Modified` function signature):**
  - Flagged by **Checklist #6 (Testability)**. Python evaluates default arguments once at `def` time when `main.py` is imported, binding `ask` permanently to the original unpatched `builtins.input` before `monkeypatch.setattr("builtins.input", ...)` runs.
  - **Modification:** Changed signature to `def run_quiz(session, colors, ask=None):` and resolved `if ask is None: ask = input` inside the function body at call time.
- **Verification:** All CLI and integration tests (`test_cli_full_session`, `test_cli_exit_command_quits_gracefully`, `test_cli_ctrl_c_and_ctrl_d_quit_gracefully`) pass cleanly.

---

### 6. Smoke-Test Order Mismatch in Adaptive Mode

- **Prompt Used:**
  > "Run a smoke test of `python main.py -m adaptive -f data/python_basics.json --stats` with one deliberate wrong answer to verify terminal output before finalising tests."
- **AI Response / Initial Output:**
  > Piped answers ordered identically to `python_basics.json` (`def`, `WRONG`, `3`, `8`, ...) and got `Score: 2/15 correct (13.3%)`. Initially suspected an off-by-one bug in `AdaptiveMode`.
- **Checklist Review & Decision (`Rejected` false bug diagnosis):**
  - Checked against **Checklist #4 (Edge Cases)** and **#5 (Real Deck Data)**. Tracing the queue showed `AdaptiveMode` worked as designed: missing Question 2 re-inserted it at Question 5, shifting every subsequent piped answer onto the wrong card.
  - **Decision:** Kept `AdaptiveMode` unchanged; updated scripted adaptive tests to derive answer sequences from the `retry_gap=2` schedule explicitly.
- **Verification:** Re-ran smoke test with adaptive-ordered answers (`11/12` correct, `91.7%`) and codified exact sequence assertions in `test_cli_adaptive_game_repeats_missed_question`.

---

### 7. Standardising File Paths & Pluralisation in Loader Error Messages

- **Prompt Used:**
  > "Check all `FlashcardLoadError` messages in `utils/file_handler.py` against malformed JSON, missing fields, and missing files for consistency."
- **AI Response / Initial Output:**
  > `load_flashcards` formatted `JSONDecodeError` with `path.resolve()` (full `/Users/...` path) while `parse_flashcards` used `path.name` (`deck.json`), and missing both fields printed `missing the "front" and "back" field.`
- **Checklist Review & Decision (`Modified` error formatting):**
  - Flagged by **Checklist #1 (Readability)** and **#2 (Safe Error Handling)**. Exposing full host paths leaks local directory layout and looks inconsistent next to bare filenames; singular `"field"` for two fields is ungrammatical.
  - **Modification:** Standardised on `str(path)` as supplied by the user and added singular/plural noun selection (`"field"` vs `"fields"`).
- **Verification:** `test_parse_flashcards_uses_source_in_messages` and `test_load_missing_both_fields_lists_both`.

---

### 8. Preventing Inflated Test Coverage Metrics

- **Prompt Used:**
  > "Configure `pytest-cov` so `python -m pytest --cov=. --cov-report=html` accurately measures application test coverage."
- **AI Response / Initial Output:**
  > Ran `pytest --cov=.` with default settings, which included `tests/*.py` (~450 lines of 100%-executed test files) in the denominator, inflating total coverage even if source branches were missed.
- **Checklist Review & Decision (`Modified` `pyproject.toml`):**
  - Flagged by **Checklist #6 (Honest Coverage)**. Including test files in `--cov=.` masks untested application lines. Also noted `htmlcov/.gitignore` prevents committing HTML output to Git.
  - **Modification:** Added `[tool.coverage.run] omit = [".venv/*", "venv/*", "tests/*"]` in `pyproject.toml` and saved a plain-text report at `docs/coverage_report.txt`.
- **Verification:** `pytest --cov=.` measures strictly the 275 statements in `main.py`, `quiz_engine.py`, `utils/file_handler.py`, and `utils/colors.py` at **100% coverage**.

---

### 9. Real Pseudo-Terminal `SIGINT` Verification Beyond Mocks

- **Prompt Used:**
  > "Verify `Ctrl+C` handling in a real pseudo-terminal (`pty`) rather than relying solely on `fake_input` raising `KeyboardInterrupt`."
- **AI Response / Initial Output:**
  > Spawned `main.py` inside Python's `pty` module, answered one card right (`\033[32mCorrect!\033[0m`), one wrong (`\033[31mIncorrect...`), and wrote raw byte `\x03` (`SIGINT`) at Question 3.
- **Checklist Review & Decision (`Accepted`):**
  - Verified **Checklist #2 (No Tracebacks)** and **#4 (Termination)**. Confirmed real OS signal delivery prints a clean newline, `"Quiz stopped. Goodbye!"`, partial score `1/2 (50.0%)`, exit code `0`, and `130` if interrupted before the quiz loop starts.
- **Verification:** Documented exit codes `0`, `1`, `2`, and `130` in `README.md`.

---

### 10. Simplifying Over-Engineered Random-Mode Test Assertion

- **Prompt Used:**
  > "Review `tests/test_quiz_modes.py` against our checklist for tautological or brittle assertions."
- **AI Response / Initial Output:**
  > Initial `RandomMode` test ended with:
  ```python
  assert first != ["A", "B", "C", "D", "E"] or other != first or sorted(first) == ["A", "B", "C", "D", "E"]
  ```
- **Checklist Review & Decision (`Rejected` compound `or` assertion; `Modified` test):**
  - Flagged by **Checklist #1 (Readability)** and **#6 (Testability)**. Because `sorted(first) == [...]` is always true when all cards are present, the `or` chain could pass even if `RandomMode` never shuffled at all!
  - **Modification:** Split into three independent `assert` statements using deterministic `random.Random(7)` and `random.Random(8)` instances: same elements, same order for identical seeds, different order across seeds.
- **Verification:** `test_random_mode_asks_each_card_once_in_shuffled_order`.

---

### 11. Independent Multi-Agent Audit: Catching `json.loads` `ValueError` & `RecursionError`

- **Prompt Used:**
  > "Review the codebase using fresh sub-agents (`code-review` Standards + Spec axes and `ponytail-review`) with zero build context, reproduce any real defects, and check documentation for drift."
- **AI Response / Initial Output:**
  > Identified two unhandled exceptions in `utils/file_handler.py` (`json.loads` raises `ValueError`—not `JSONDecodeError`—for integers >4,300 digits in Python 3.11+, and `RecursionError` on deeply nested arrays), four minor doc wording drifts, and also suggested deleting `ask=None`, `AnswerResult`, `QuizMode.remaining`, and `--no-color` as "YAGNI".
- **Checklist Review & Decision (`Accepted` bug + doc fixes; `Rejected` over-aggressive deletions):**
  - **Accepted (#2 Safe Error Handling):** Caught `(ValueError, RecursionError)` in `load_flashcards()` and converted them into `FlashcardLoadError(...) from None`; fixed adaptive retry wording and exit-code docs.
  - **Rejected (#1 Readability & #6 Testability):** Kept `ask=None` (explicit test seam), `AnswerResult` (structured return value vs raw tuple), `QuizMode.remaining` (clean Strategy inspection property), and `--no-color` (standard CLI ergonomics alongside `NO_COLOR`).
- **Verification:** Added `test_load_json_python_refuses_to_decode` (5,000-digit integer); all **90 tests pass** with **100% coverage** and `0` `flake8` issues.
