# Flashcard Quizzer – notes for AI coding agents

- Python 3.10+, standard library only at runtime. Dev tools are in `requirements.txt`.
- Layout: `main.py` (argparse CLI) → `quiz_engine.py` (QuizMode strategies, QuizModeFactory, QuizSession/QuizStats) → `utils/file_handler.py` (JSON loading/validation), `utils/colors.py` (ANSI colors).
- Keep the Strategy/Factory structure: add a new mode by subclassing `QuizMode`, giving it a `name`, and adding it to the tuple that builds `QuizModeFactory._modes`.
- User-facing errors must be raised as `FlashcardLoadError` (or argparse errors) — never let a traceback reach the user.
- Before finishing any change run:
  - `python -m pytest tests/` (all must pass)
  - `python -m pytest --cov=. --cov-report=html` (keep coverage > 80%; currently 100%)
  - `flake8` (must be clean; default 79-char lines)
- Record notable prompt refinements and logic corrections in `docs/ai_edit_log.md`.
