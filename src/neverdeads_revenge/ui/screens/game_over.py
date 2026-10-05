"""Game over.

Shown as a modal over the final map state, so the dungeon you died in stays
visible behind the numbers.

It used to close on any key. The summary is the only place the run is added up,
and a stray press threw it away -- so now it takes a held enter, the same
gesture the prologue uses.
"""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from ..hold import BAR_CELLS, HoldToContinue

__all__ = ["GameOverScreen"]

_FILLED = "#a855f7"


class GameOverScreen(ModalScreen[None]):
    """Run summary. A held enter returns to the title."""

    # Escape is here for the same reason enter is: it is the key people reach for
    # when they want out, and it goes through the same hold.
    BINDINGS = [Binding("escape", "close", "Close")]

    DEFAULT_CSS = """
    GameOverScreen {
        align: center middle;
        /* Dim the final map, but not so far that the room you died in is lost. */
        background: $background 70%;
    }
    """

    def __init__(
        self,
        summary: str,
        depth: int,
        score: int,
        won: bool = False,
        best: int = 0,
    ) -> None:
        super().__init__()
        self.summary = summary
        self.depth = depth
        self.score = score
        self.won = won
        self.best = best
        self._hold = HoldToContinue()

    def compose(self) -> ComposeResult:
        with Vertical(id="game-over"):
            yield Static(
                "VICTORY" if self.won else "YOU DIED",
                id="game-over-title",
            )
            yield Static(self.summary, id="game-over-body")
            yield Static(f"Best  {self.best}", id="game-over-best")
            yield Static(self._hint(), id="game-over-hint")

    # -- input --------------------------------------------------------------
    def on_key(self, event) -> None:
        if event.key in (*self._hold.keys, "escape"):
            self.app.note_key(event.key)
            event.stop()
            if self._hold.press(event.key):
                self.app.arm_repeat_filter()
                self.dismiss()
                return
            self._draw_hint()
            return
        # Everything else is left alone: ctrl+q still has to work.

    def action_close(self) -> None:
        """The escape binding is a hold like any other, not an instant exit."""
        self.app.note_key("escape")
        if self._hold.press("escape"):
            self.app.arm_repeat_filter()
            self.dismiss()
            return
        self._draw_hint()

    def _draw_hint(self) -> None:
        self.query_one("#game-over-hint", Static).update(self._hint())

    def _hint(self) -> str:
        filled = round(self._hold.progress * BAR_CELLS)
        bar = self._hold.bar()
        return (
            "hold [bold]enter[/] to continue   "
            f"[{_FILLED}]{bar[:filled]}[/][#4a4a4a]{bar[filled:]}[/]"
        )
