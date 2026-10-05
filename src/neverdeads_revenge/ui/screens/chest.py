"""The chest dialog.

The one place the game stops and asks. Everything else a player does is
immediate; opening a chest costs something permanent, so it gets a moment.

What it shows is the price and nothing else. The reward stays behind the lid
until it is open -- that is what makes the chest daring rather than arithmetic.
Shown both, the player would be comparing two numbers and the answer would
always be the same one.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

__all__ = ["ChestScreen"]


class ChestScreen(ModalScreen[bool]):
    """Ask before opening. Returns ``True`` to go ahead."""

    BINDINGS = [
        Binding("enter", "open_it", "Open"),
        Binding("return", "open_it", "Open"),
        Binding("escape", "leave_it", "Leave"),
        Binding("n", "leave_it", "Leave"),
    ]

    DEFAULT_CSS = """
    ChestScreen {
        align: center middle;
        background: $background 70%;
    }
    """

    def __init__(self, price: str) -> None:
        super().__init__()
        self.price = price

    def compose(self) -> ComposeResult:
        with Vertical(id="chest"):
            yield Static("AN OMINOUS CHEST", id="chest-title")
            yield Static(
                "It glows. Whatever is inside is worth having, and it is not "
                "free.\n\n"
                f"[bold]{self.price}[/]",
                id="chest-body",
            )
            yield Static(
                "[bold]enter[/]  open it        [bold]escape[/]  walk away",
                id="chest-hint",
            )

    def action_open_it(self) -> None:
        self.dismiss(True)

    def action_leave_it(self) -> None:
        self.dismiss(False)
