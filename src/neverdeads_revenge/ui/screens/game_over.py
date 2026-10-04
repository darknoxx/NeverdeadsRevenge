"""Game over.

Shown as a modal over the final map state, so the dungeon you died in stays
visible behind the numbers.
"""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

__all__ = ["GameOverScreen"]


class GameOverScreen(ModalScreen[None]):
    """Run summary. Any key returns to the title."""

    BINDINGS = [Binding("escape", "dismiss", "Close")]

    DEFAULT_CSS = """
    GameOverScreen {
        align: center middle;
        /* Dim the final map, but not so far that the room you died in is lost. */
        background: $background 70%;
    }
    """

    def __init__(self, summary: str, depth: int, score: int, won: bool = False) -> None:
        super().__init__()
        self.summary = summary
        self.depth = depth
        self.score = score
        self.won = won

    def compose(self) -> ComposeResult:
        with Vertical(id="game-over"):
            yield Static(
                "VICTORY" if self.won else "YOU DIED",
                id="game-over-title",
            )
            yield Static(self.summary, id="game-over-body")
            yield Static("press any key", id="game-over-hint")

    def on_key(self, event) -> None:
        event.stop()
        self.dismiss()
