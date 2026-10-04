"""Pause menu.

Deliberately thin: quit to title, or keep going. Saving a run mid-dungeon is
later work.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

__all__ = ["PauseScreen"]


class PauseScreen(ModalScreen[str]):
    """Returns ``"resume"`` or ``"quit"``."""

    BINDINGS = [
        Binding("escape", "resume", "Resume"),
        Binding("r", "resume", "Resume"),
        Binding("q", "quit_game", "Quit to title"),
    ]

    DEFAULT_CSS = """
    PauseScreen {
        align: center middle;
        /* Dim the dungeon behind the menu so the dialog reads as a layer. */
        background: $background 70%;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="pause"):
            yield Static("PAUSED", id="pause-title")
            yield Static(
                "[bold]r[/] / [bold]escape[/]  resume\n"
                "[bold]q[/]                quit to title\n",
                id="pause-body",
            )

    def action_resume(self) -> None:
        self.dismiss("resume")

    def action_quit_game(self) -> None:
        self.dismiss("quit")
