"""End-to-end tests: JSON file -> loader -> factory -> session -> CLI."""

import subprocess
import sys
from pathlib import Path

import pytest

import main
from quiz_engine import QuizModeFactory, QuizSession
from utils.file_handler import load_flashcards

PROJECT_ROOT = Path(__file__).resolve().parent.parent

THREE_CARDS = {
    "cards": [
        {"front": "Capital of France?", "back": "Paris"},
        {"front": "2 + 2", "back": "4"},
        {"front": "Largest planet?", "back": "Jupiter"},
    ]
}


def scripted_input(monkeypatch, answers):
    """Replace input() with one that replays ``answers``.

    Like a real closed stdin, it raises EOFError when answers run out.
    Returns the list of prompts that were shown.
    """
    remaining = list(answers)
    prompts = []

    def fake_input(prompt=""):
        prompts.append(prompt)
        if not remaining:
            raise EOFError
        answer = remaining.pop(0)
        if isinstance(answer, BaseException):
            raise answer
        return answer

    monkeypatch.setattr("builtins.input", fake_input)
    return prompts


def test_full_session(write_deck):
    """A user answers 3 questions (2 right, 1 wrong); check the stats."""
    cards = load_flashcards(write_deck(THREE_CARDS))
    session = QuizSession(QuizModeFactory.create("sequential", cards))

    results = []
    for answer in ["paris", "5", "  Jupiter "]:
        assert session.next_card() is not None
        results.append(session.submit_answer(answer))

    assert session.next_card() is None
    assert [result.correct for result in results] == [True, False, True]
    stats = session.stats
    assert stats.answered == 3
    assert stats.correct == 2
    assert stats.incorrect == 1
    assert stats.accuracy == pytest.approx(66.667, abs=0.001)
    assert [card.front for card in stats.misses] == ["2 + 2"]


def test_cli_full_session(write_deck, monkeypatch, capsys):
    path = write_deck(THREE_CARDS)
    prompts = scripted_input(monkeypatch, ["Paris", "5", "jupiter"])

    exit_code = main.main(["-f", str(path)])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert prompts == ["> "] * 3
    assert "(3 cards, sequential mode)" in out
    assert out.count("Correct!") == 2
    assert "Incorrect. The answer is: 4" in out
    assert "Deck complete!" in out
    assert "Score: 2/3 correct (66.7%)" in out
    assert "Session statistics" not in out  # only shown with --stats


def test_cli_stats_flag_prints_detailed_report(write_deck, monkeypatch,
                                               capsys):
    path = write_deck(THREE_CARDS)
    scripted_input(monkeypatch, ["Paris", "5", "jupiter"])

    main.main(["-f", str(path), "--stats"])

    out = capsys.readouterr().out
    assert "Session statistics" in out
    assert "Questions answered: 3" in out
    assert "Incorrect:          1" in out
    assert "Accuracy:           66.7%" in out
    assert "2 + 2 -> 4 (missed 1 time)" in out


def test_cli_adaptive_game_repeats_missed_question(write_deck, monkeypatch,
                                                   capsys):
    path = write_deck(THREE_CARDS)
    # Miss "2 + 2"; with only one card left it comes back straight after it.
    scripted_input(monkeypatch, ["Paris", "5", "Jupiter", "4"])

    exit_code = main.main(["-m", "ADAPTIVE", "-f", str(path), "--stats"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert out.count("Question 4: 2 + 2") == 1
    assert "Score: 3/4 correct (75.0%)" in out
    assert "Unique cards seen:  3" in out


@pytest.mark.parametrize("command", ["exit", "  EXIT ", "quit"])
def test_cli_exit_command_quits_gracefully(write_deck, monkeypatch, capsys,
                                           command):
    path = write_deck(THREE_CARDS)
    scripted_input(monkeypatch, ["Paris", command, "never asked"])

    exit_code = main.main(["-f", str(path)])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "Quiz stopped. Goodbye!" in out
    assert "Score: 1/1 correct (100.0%)" in out
    assert "Question 3" not in out


@pytest.mark.parametrize("interrupt", [KeyboardInterrupt(), EOFError()])
def test_cli_ctrl_c_and_ctrl_d_quit_gracefully(write_deck, monkeypatch,
                                               capsys, interrupt):
    path = write_deck(THREE_CARDS)
    scripted_input(monkeypatch, ["Paris", interrupt])

    exit_code = main.main(["-f", str(path), "--stats"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Quiz stopped. Goodbye!" in captured.out
    assert "Score: 1/1 correct (100.0%)" in captured.out
    assert "Traceback" not in captured.err


def test_cli_invalid_json_prints_friendly_error(write_deck, capsys):
    path = write_deck("{not json")

    exit_code = main.main(["-f", str(path)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.err.startswith("Error: ")
    assert "not valid JSON" in captured.err
    assert captured.out == ""


def test_cli_missing_field_prints_friendly_error(write_deck, capsys):
    path = write_deck([{"front": "Q"}])

    assert main.main(["-f", str(path)]) == 1
    assert 'missing the "back" field' in capsys.readouterr().err


def test_cli_missing_file_prints_friendly_error(tmp_path, capsys):
    assert main.main(["-f", str(tmp_path / "nope.json")]) == 1
    assert "Deck file not found" in capsys.readouterr().err


@pytest.mark.parametrize(
    "argv",
    [["-f", "data/glossary.json", "-m", "hardcore"], ["-m", "random"]],
    ids=["unknown-mode", "missing-file-flag"],
)
def test_cli_argument_errors_exit_with_usage(argv, capsys):
    with pytest.raises(SystemExit) as excinfo:
        main.main(argv)

    assert excinfo.value.code == 2
    assert "usage:" in capsys.readouterr().err


def test_cli_uses_green_and_red_on_a_terminal(write_deck, monkeypatch,
                                              capsys):
    path = write_deck(THREE_CARDS)
    scripted_input(monkeypatch, ["Paris", "5", "Jupiter"])
    monkeypatch.setattr(main, "supports_color", lambda stream: True)

    main.main(["-f", str(path)])

    out = capsys.readouterr().out
    assert "\033[32mCorrect!\033[0m" in out
    assert "\033[31mIncorrect. The answer is: 4\033[0m" in out


def test_cli_no_color_flag_disables_colors(write_deck, monkeypatch, capsys):
    path = write_deck(THREE_CARDS)
    scripted_input(monkeypatch, ["Paris", "5", "Jupiter"])
    monkeypatch.setattr(main, "supports_color", lambda stream: True)

    main.main(["-f", str(path), "--no-color"])

    assert "\033[" not in capsys.readouterr().out


# --- Real processes: exactly what a user types in a terminal ---------------

def run_cli(args, stdin=""):
    return subprocess.run(
        [sys.executable, "main.py", *args],
        cwd=PROJECT_ROOT,
        input=stdin,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_play_full_adaptive_game_in_subprocess():
    deck = PROJECT_ROOT / "data" / "python_basics.json"
    answers = [card.back for card in load_flashcards(deck)]

    result = run_cli(["-m", "adaptive", "-f", "data/python_basics.json"],
                     stdin="\n".join(answers) + "\n")

    assert result.returncode == 0, result.stderr
    assert "Deck complete!" in result.stdout
    total = len(answers)
    assert f"Score: {total}/{total} correct (100.0%)" in result.stdout
    assert result.stderr == ""


def test_bad_deck_in_subprocess_has_no_traceback(write_deck):
    path = write_deck('[{"front": "Q", "back": }]')

    result = run_cli(["-f", str(path)])

    assert result.returncode == 1
    assert "Error:" in result.stderr
    assert "Traceback" not in result.stderr
