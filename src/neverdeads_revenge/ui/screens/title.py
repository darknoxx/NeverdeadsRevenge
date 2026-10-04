"""Title screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen

from ... import __version__

__all__ = ["TitleScreen"]

TITLE_ART = r"""
 _   _                       _ __
| \ | | ___  _ __ ___  ___  | |__   ___ ___  ___
|  \| |/ _ \| '_ ` _ \/ _ \| '_ \ / __/ __|/ __|
| |\  | (_) | | | | | | (_) | |_) | (__\__ \ (__)
|_| \_|\___/|_| |_| |_|\___/|_.__/ \___|___/___/
"""

TAGLINE = "a terminal roguelite"


class TitleScreen(Screen[None]):
    """Press anything to begin."""

    BINDINGS = [
        Binding("escape", "quit", "Quit"),
        Binding("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield from _centered()

    def on_key(self, event) -> None:
        """Any key starts the game -- no hunting for the right one."""
        event.stop()
        self.app.open_hero_select()


def _centered():
    from textual.containers import Vertical
    from textual.widgets import Static

    with Vertical(id="title-screen"):
        yield Static(TITLE_ART.rstrip("\n"), id="title-art")
        yield Static(TAGLINE, id="title-subtitle")
        yield Static(f"\nversion {__version__}", id="title-version")
        yield Static("press any key", id="title-hint")
