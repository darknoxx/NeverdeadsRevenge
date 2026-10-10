"""A question with two answers.

Used for the one thing in the game that cannot be undone by pressing another
key: leaving it. Everything else a player does -- open a chest, take a curse,
walk through stone -- happens *inside* a run and can be lived with or lifted.
Quitting the program cannot.

So it is a dialog with the two words on it rather than a keypress and a hope,
and it names the game, because "are you sure?" over a black screen is a question
about nothing.

It answers ``True`` or ``False``; the caller decides what yes means, because
"yes" is the only part of this that is ever different.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

__all__ = ["ConfirmScreen"]


class ConfirmScreen(ModalScreen[bool]):
    """Yes or no. ``escape`` is no, because that is what it means everywhere."""

    BINDINGS = [
        Binding("y", "yes", "Yes"),
        Binding("n", "no", "No"),
        Binding("escape", "no", "No"),
    ]

    DEFAULT_CSS = """
    ConfirmScreen {
        align: center middle;
        background: $background 70%;
    }
    """

    def __init__(self, title: str, body: str) -> None:
        super().__init__()
        self.title = title
        self.body = body

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm"):
            yield Static(self.title, id="confirm-title")
            yield Static(self.body, id="confirm-body")
            yield Static(
                "[bold]y[/]  yes          [bold]n[/]  no", id="confirm-hint"
            )

    def on_key(self, event) -> None:
        # A key still repeating from the screen before this one must not answer
        # the question on the way in: the dialog is opened with ``escape`` or
        # ``q``, and a held ``escape`` would read as "no" and close it before it
        # was read. Only the repeats are stopped -- everything else has to reach
        # the bindings, which is where the answer is. See App.note_key.
        if self.app.note_key(event.key):
            event.stop()

    def action_yes(self) -> None:
        self.dismiss(True)

    def action_no(self) -> None:
        self.dismiss(False)
