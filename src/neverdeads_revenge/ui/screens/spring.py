"""The spring dialog.

The second place the game stops and asks. Everything else a player does is
immediate; washing a curse off costs coin that outlives the run, so it gets a
moment.

It shows the price and which curse is going, and nothing else. *Which* curse is
the water's decision rather than the player's -- the dialog says so when there is
more than one, and names it when there is not.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

__all__ = ["SpringScreen"]


class SpringScreen(ModalScreen[bool]):
    """Ask before the water takes a curse. Returns ``True`` to go ahead."""

    BINDINGS = [
        Binding("enter", "wash_it", "Wash"),
        Binding("return", "wash_it", "Wash"),
        Binding("escape", "leave_it", "Leave"),
        Binding("n", "leave_it", "Leave"),
    ]

    DEFAULT_CSS = """
    SpringScreen {
        align: center middle;
        background: $background 70%;
    }
    """

    def __init__(self, price: str) -> None:
        super().__init__()
        self.price = price

    def compose(self) -> ComposeResult:
        with Vertical(id="spring"):
            yield Static("A SPRING", id="spring-title")
            yield Static(
                "The water is still, and colder than it should be. It has come "
                "up through something that does not want to be here.\n\n"
                f"[bold]{self.price}[/]",
                id="spring-body",
            )
            yield Static(
                "[bold]enter[/]  wash it off        [bold]escape[/]  leave it",
                id="spring-hint",
            )

    # A key still repeating from the screen before this one must not answer this
    # one on the way in. See App.note_key. Only the repeats are stopped:
    # everything else has to reach the bindings, which is where the answer is.
    def on_key(self, event) -> None:
        if self.app.note_key(event.key):
            event.stop()

    def action_wash_it(self) -> None:
        if self.app.note_key("enter"):
            return
        self.dismiss(True)

    def action_leave_it(self) -> None:
        self.dismiss(False)
