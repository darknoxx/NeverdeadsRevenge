"""The prologue screen.

Shown once, between the hero choice and floor 1. It exists because the game has
a premise that the mechanics cannot state: the hero is dead, came back anyway, and
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

from ...game.prologue import PROLOGUE, PROLOGUE_HINT, PROLOGUE_TITLE

__all__ = ["PrologueScreen"]


class PrologueScreen(Screen[None]):
    """The premise, once per session."""

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
            # Set apart from the story: the story is what happened, this is what
            # it means, and running them together buries the one line the player
            # is meant to leave with.
            yield Static(PROLOGUE_HINT, id="prologue-hint")
            yield Static("press any key", id="prologue-dismiss")

    def on_key(self, event) -> None:
        event.stop()
        self.dismiss()