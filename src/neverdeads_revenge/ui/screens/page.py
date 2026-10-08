"""A page, read where it was found.

The chronicle screen in the menu is the collection; this is the moment of
finding. A page that went straight into a book the player has not opened yet
would be a collectible nobody ever read -- and the message log is no place for
it either, because a line in the log scrolls away in four turns and thirty-seven
fragments read that way are thirty-seven fragments nobody reads.

So the game stops for it, the way it stops for a chest and for somebody talking,
and for the same reason: this is prose, and prose in a log is prose nobody read.

It asks nothing. Any key closes it and the run carries on -- the page is already
in the book by the time it is shown, so there is nothing to lose by closing it
early and nothing to gain by staying.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from ...game.lore import PAGE_COUNT, numeral

__all__ = ["PageScreen"]


class PageScreen(ModalScreen[None]):
    """One page of the chronicle, open. Any key closes."""

    BINDINGS = [Binding("escape", "dismiss", "Close")]

    DEFAULT_CSS = """
    PageScreen {
        align: center middle;
        background: $background 70%;
    }
    """

    def __init__(self, number: int, text: str) -> None:
        super().__init__()
        self.number = number
        self.text = text

    def compose(self) -> ComposeResult:
        with Vertical(id="page"):
            yield Static("A TORN PAGE", id="page-title")
            yield Static(
                f"{numeral(self.number)} of {numeral(PAGE_COUNT)}",
                id="page-subtitle",
            )
            yield Static(self.text, id="page-body")
            yield Static("filed in the book   ·   press any key", id="page-hint")

    def on_key(self, event) -> None:
        # A key still repeating from the screen before this one must not close
        # this one on the way in: a page is picked up with ``enter``, and a held
        # ``enter`` would dismiss the page before a word of it was read. See
        # App.note_key.
        if self.app.note_key(event.key):
            event.stop()
            return
        event.stop()
        self.dismiss()
