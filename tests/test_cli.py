"""Unit tests for CLI helpers: colors, argument parsing, summary output."""

import io
from pathlib import Path

import pytest

import main
from quiz_engine import QuizStats
from utils.colors import Colorizer, supports_color
from utils.file_handler import Flashcard


class FakeTerminal(io.StringIO):
    def isatty(self):
        return True


def test_supports_color_on_a_terminal(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    assert supports_color(FakeTerminal()) is True


def test_supports_color_when_output_is_piped(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    assert supports_color(io.StringIO()) is False
    assert supports_color(object()) is False  # no isatty() at all


def test_no_color_environment_variable_wins(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert supports_color(FakeTerminal()) is False


def test_colorizer_wraps_text_only_when_enabled():
    on, off = Colorizer(enabled=True), Colorizer(enabled=False)

    assert on.green("ok") == "\033[32mok\033[0m"
    assert on.red("no") == "\033[31mno\033[0m"
    assert on.yellow("hm") == "\033[33mhm\033[0m"
    assert on.cyan("Q") == "\033[36mQ\033[0m"
    assert on.bold("B") == "\033[1mB\033[0m"
    assert off.green("ok") == "ok"


def test_parser_defaults():
    args = main.build_parser().parse_args(["-f", "deck.json"])

    assert args.file == Path("deck.json")
    assert args.mode == "sequential"
    assert args.stats is False
    assert args.no_color is False


def test_parser_long_options_and_mode_case():
    args = main.build_parser().parse_args(
        ["--file", "deck.json", "--mode", "Random", "--stats", "--no-color"]
    )

    assert (args.mode, args.stats, args.no_color) == ("random", True, True)


def make_stats(correct, incorrect):
    stats = QuizStats()
    for number in range(correct):
        stats.record(Flashcard(f"ok{number}", "x"), True)
    for number in range(incorrect):
        stats.record(Flashcard(f"bad{number}", "x"), False)
    return stats


@pytest.mark.parametrize(
    "correct, incorrect, color",
    [(4, 1, "\033[32m"), (1, 1, "\033[33m"), (1, 2, "\033[31m")],
    ids=["green>=80%", "yellow>=50%", "red<50%"],
)
def test_score_line_color_depends_on_accuracy(correct, incorrect, color):
    lines = main.format_summary(make_stats(correct, incorrect),
                                Colorizer(enabled=True))

    assert lines[0].startswith(color)


def test_detailed_summary_for_a_perfect_run():
    lines = main.format_summary(make_stats(3, 0), Colorizer(enabled=False),
                                detailed=True)

    assert "No missed cards. Perfect run!" in lines
    assert "Cards to review:" not in lines


def test_detailed_summary_lists_most_missed_first():
    stats = QuizStats()
    easy, hard = Flashcard("easy", "1"), Flashcard("hard", "2")
    stats.record(easy, False)
    stats.record(hard, False)
    stats.record(hard, False)

    lines = main.format_summary(stats, Colorizer(enabled=False),
                                detailed=True)

    review = lines[lines.index("Cards to review:") + 1:]
    assert review == [
        "  - hard -> 2 (missed 2 times)",
        "  - easy -> 1 (missed 1 time)",
    ]


def test_summary_when_nothing_was_answered():
    lines = main.format_summary(QuizStats(), Colorizer(enabled=False),
                                detailed=True)

    assert lines[0] == "Score: 0/0 correct (0.0%)"
    assert "No missed cards. Perfect run!" not in lines
