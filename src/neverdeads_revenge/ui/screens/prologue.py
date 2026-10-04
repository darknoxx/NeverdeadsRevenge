"""The prologue screen.

Shown once, between the hero choice and floor 1. It exists because the game has
a premise that the mechanics cannot state: Noxx is dead, he came back anyway, and
the dungeon is the way out. Everything after this has to work without repeating
it.

Dismissal is deliberately easy -- any key, like the title screen. A player who
wants to read it twice has to go looking for it, which is fine; a player who is
skipped past a story they have already read is annoyed every time.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Static

from ...game.prologue import PROLOGUE, PROLOGUE_TITLE

__all__ = ["PrologueScreen"]


class PrologueScreen(Screen[None]):
    """The premise, once per run."""

    BINDINGS = [Binding("escape", "begin", "Begin")]

    DEFAULT_CSS = """
    PrologueScreen {
        align: center middle;
    }
    """

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="prologue-screen"):
            yield Static(PROLOGUE_TITLE, id="prologue-title")
            for line in PROLOGUE:
                # A class rather than a per-line id: ids must be unique, and a
                # class survives the prologue growing a line.
                yield Static(line, classes="prologue-line")
            yield Static("weiter mit enter  ·  press enter", id="prologue-hint")

    def on_key(self, event) -> None:
        """Any key continues, but not one that is bound to something else.

        The prose is German while the game's own text is English, so the hint
        says both.
        """
        event.stop()
        self.dismiss()