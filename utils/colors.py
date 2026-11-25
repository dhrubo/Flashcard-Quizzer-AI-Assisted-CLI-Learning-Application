"""Minimal ANSI color helpers (no third-party dependency)."""

import os

RESET = "\033[0m"
CODES = {
    "bold": "\033[1m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "cyan": "\033[36m",
}


def supports_color(stream):
    """True if ``stream`` is an interactive terminal and NO_COLOR is unset.

    See https://no-color.org for the NO_COLOR convention.
    """
    if os.environ.get("NO_COLOR"):
        return False
    isatty = getattr(stream, "isatty", None)
    return bool(isatty and isatty())


class Colorizer:
    """Wraps text in ANSI codes, or returns it unchanged when disabled."""

    def __init__(self, enabled=True):
        """Initialize the colorizer with ANSI output enabled or disabled."""
        self.enabled = enabled

    def paint(self, text, color):
        """Wrap ``text`` in the named ANSI color code when enabled."""
        if not self.enabled:
            return text
        return f"{CODES[color]}{text}{RESET}"

    def bold(self, text):
        """Format ``text`` in bold."""
        return self.paint(text, "bold")

    def red(self, text):
        """Format ``text`` in red."""
        return self.paint(text, "red")

    def green(self, text):
        """Format ``text`` in green."""
        return self.paint(text, "green")

    def yellow(self, text):
        """Format ``text`` in yellow."""
        return self.paint(text, "yellow")

    def cyan(self, text):
        """Format ``text`` in cyan."""
        return self.paint(text, "cyan")
