"""Flashcard Quizzer: study a JSON deck of flashcards in the terminal.

Examples::

    python main.py -f data/python_basics.json
    python main.py -m adaptive -f data/python_basics.json --stats
"""

import argparse
import sys
from pathlib import Path

from quiz_engine import QuizModeFactory, QuizSession
from utils.colors import Colorizer, supports_color
from utils.file_handler import FlashcardLoadError, load_flashcards

EXIT_COMMANDS = frozenset({"exit", "quit"})


def build_parser():
    """Build and return the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Quiz yourself on a deck of flashcards.",
        epilog="Type 'exit' or press Ctrl+C at any prompt to stop early.",
    )
    parser.add_argument(
        "-f", "--file",
        required=True,
        type=Path,
        help='JSON deck: a list of {"front", "back"} cards, '
             'or an object with a "cards" list',
    )
    parser.add_argument(
        "-m", "--mode",
        default="sequential",
        type=str.lower,
        choices=QuizModeFactory.available_modes(),
        help="order in which cards are asked (default: %(default)s)",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="show a detailed statistics report when the quiz ends",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="disable colored output",
    )
    return parser


def run_quiz(session, colors, ask=None):
    """Ask questions until the deck is done or the user types 'exit'.

    ``ask`` defaults to the built-in input(), looked up at call time so it
    can be patched in tests. Returns True if the user quit early.
    Ctrl+C (KeyboardInterrupt) and end-of-input (EOFError) propagate to
    the caller.
    """
    if ask is None:
        ask = input
    number = 0
    while (card := session.next_card()) is not None:
        number += 1
        print(f"\n{colors.cyan(f'Question {number}:')} {card.front}")
        answer = ask("> ")
        if answer.strip().lower() in EXIT_COMMANDS:
            return True
        result = session.submit_answer(answer)
        if result.correct:
            print(colors.green("Correct!"))
        else:
            print(colors.red(f"Incorrect. The answer is: {result.expected}"))
    return False


def format_summary(stats, colors, detailed=False):
    """Return the end-of-quiz report as a list of lines."""
    if stats.accuracy >= 80:
        paint = colors.green
    elif stats.accuracy >= 50:
        paint = colors.yellow
    else:
        paint = colors.red
    lines = [paint(
        f"Score: {stats.correct}/{stats.answered} correct "
        f"({stats.accuracy:.1f}%)"
    )]
    if not detailed:
        return lines

    lines += [
        "",
        colors.bold("Session statistics"),
        f"  Questions answered: {stats.answered}",
        f"  Correct:            {stats.correct}",
        f"  Incorrect:          {stats.incorrect}",
        f"  Accuracy:           {stats.accuracy:.1f}%",
        f"  Unique cards seen:  {len(stats.cards_seen)}",
    ]
    if stats.misses:
        lines.append(colors.bold("Cards to review:"))
        for card, count in stats.misses.most_common():
            times = "time" if count == 1 else "times"
            lines.append(
                f"  - {card.front} -> {card.back} (missed {count} {times})"
            )
    elif stats.answered:
        lines.append(colors.green("No missed cards. Perfect run!"))
    return lines


def main(argv=None):
    """Parse CLI arguments, run the quiz session, and return an exit code."""
    args = build_parser().parse_args(argv)
    use_color = not args.no_color and supports_color(sys.stdout)
    colors = Colorizer(enabled=use_color)

    try:
        cards = load_flashcards(args.file)
    except FlashcardLoadError as exc:
        print(colors.red(f"Error: {exc}"), file=sys.stderr)
        return 1

    session = QuizSession(QuizModeFactory.create(args.mode, cards))
    count = len(cards)
    print(colors.bold(
        f"Flashcard Quizzer - {args.file.name} "
        f"({count} card{'s' if count != 1 else ''}, {args.mode} mode)"
    ))
    print("Type 'exit' or press Ctrl+C to quit.")

    try:
        quit_early = run_quiz(session, colors)
    except (KeyboardInterrupt, EOFError):
        print()  # finish the line left by the interrupted prompt
        quit_early = True

    print()
    if quit_early:
        print(colors.yellow("Quiz stopped. Goodbye!"))
    else:
        print(colors.bold("Deck complete!"))
    for line in format_summary(session.stats, colors, detailed=args.stats):
        print(line)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:  # Ctrl+C before the quiz loop started
        print()
        sys.exit(130)
