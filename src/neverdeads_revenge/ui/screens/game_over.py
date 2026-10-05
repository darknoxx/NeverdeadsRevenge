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
from textual.css.query import NoMatches
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from ..hold import HoldToContinue

__all__ = ["GameOverScreen"]


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
            yield Static(id="game-over-hint")

    def on_mount(self) -> None:
        self._timer = self.set_interval(0.05, self._advance)
        self._draw_hint()

    def on_unmount(self) -> None:
        # A timer outliving its screen fires into a widget tree that is gone.
        self._timer.stop()

    # -- input --------------------------------------------------------------
    def on_key(self, event) -> None:
        if event.key in (*self._hold.keys, "escape"):
            event.stop()
            if self._hold.press(event.key):
                self.dismiss()
            return
        # Everything else is left alone: ctrl+q still has to work.

    def action_close(self) -> None:
        """The escape binding is a hold like any other, not an instant exit."""
        if self._hold.press("escape"):
            self.dismiss()

    def _advance(self) -> None:
        if not self.is_mounted:
            return
        if self._hold.tick():
            self.dismiss()
            return
        self._draw_hint()

    def _draw_hint(self) -> None:
        if not self.is_mounted:
            return
        filled = round(self._hold.progress * 10)
        bar = self._hold.bar()
        try:
            hint = self.query_one("#game-over-hint", Static)
        except NoMatches:
            # Teardown race: the screen is still "mounted" for a moment after
            # its children are gone, and the timer can land in that window.
            return
        hint.update(
            f"hold [bold]enter[/] to continue   "
            f"[{_FILLED}]{bar[:filled]}[/][#4a4a4a]{bar[filled:]}[/]"
        )


_FILLED = "#a855f7"
