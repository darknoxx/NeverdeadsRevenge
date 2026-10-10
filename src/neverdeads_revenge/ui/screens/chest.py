"""The chest dialog.

The one place the game stops and asks. Everything else a player does is
immediate; opening a chest costs something permanent, so it gets a moment.

What it shows is the price and nothing else. The reward stays behind the lid
until it is open -- that is what makes the chest daring rather than arithmetic.
Shown both, the player would be comparing two numbers and the answer would
always be the same one.

Three answers, and the third is the interesting one. The price is the same
either way; what changes is what is bought with it. The blade, or the name.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

__all__ = ["ChestScreen"]


#: What the dialog can come back with. ``None`` is walking away, which costs
#: nothing -- and is why it is not one of these.
OPEN = "open"
FAME = "fame"


class ChestScreen(ModalScreen[str | None]):
    """Ask before opening. Returns ``OPEN``, ``FAME``, or ``None``."""

    BINDINGS = [
        Binding("enter", "open_it", "Open"),
        Binding("return", "open_it", "Open"),
        Binding("f", "take_fame", "Fame"),
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
                f"[bold]{self.price}[/]\n\n"
                "Pay it and take what is in it. Or pay it and take nothing at "
                "all -- and the dark will remember your name.",
                id="chest-body",
            )
            yield Static(
                "[bold]enter[/]  open it      "
                "[bold]f[/]  the curse, for fame      "
                "[bold]escape[/]  walk away",
                id="chest-hint",
            )

    # A key still repeating from the screen before this one must not answer
    # this one on the way in. See App.note_key. Only the repeats are stopped:
    # everything else has to reach the bindings, which is where the answer is.
    def on_key(self, event) -> None:
        if self.app.note_key(event.key):
            event.stop()

    def action_open_it(self) -> None:
        # Enter is *bound*, so it never reaches ``on_key`` -- Textual checks the
        # bindings first. Holding enter on a chest used to open it before the
        # dialog had been read, which is the one thing this dialog exists to
        # prevent.
        if self.app.note_key("enter"):
            return
        self.dismiss(OPEN)

    def action_take_fame(self) -> None:
        # Bound rather than handled in ``on_key``, for the same reason enter is:
        # a key that is bound never reaches ``on_key`` at all.
        if self.app.note_key("f"):
            return
        self.dismiss(FAME)

    def action_leave_it(self) -> None:
        self.dismiss(None)
