"""The controls and the terrain reference.

A screen rather than a toast on purpose. Textual's notifications are sized to a
few lines and clip the rest, and the terrain half of this text is the half that
was moved *out* of the always-on legend precisely because the sidebar had no room
for it. Putting it in a box that silently cuts it off would have been the same
problem wearing a different hat.

The body scrolls, so a short terminal shows a window onto the reference rather
than losing the end of it.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

from .game import HELP_TEXT

__all__ = ["HelpScreen"]


class HelpScreen(ModalScreen[None]):
    """Everything the game knows that does not fit on the sidebar. Any key closes."""

    BINDINGS = [Binding("escape", "dismiss", "Close")]

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
        background: $background 70%;
    }
    """

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="help"):
            yield Static("CONTROLS & REFERENCE", id="help-title")
            yield Static(HELP_TEXT, id="help-body")
            yield Static("press any key", id="help-hint")

    def on_key(self, event) -> None:
        event.stop()
        self.dismiss()
