"""Somebody talking.

The third box the game stops for, after a chest and a spring, and the only one
that asks nothing. It exists because a line of lore with no dialog would be a
line in the message log, and a line in the message log scrolls away in four
turns.

Takes the name and the line rather than the person: the domain has already
decided who is speaking and what they are saying, and a screen that went looking
for them again could disagree with the domain about it.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

__all__ = ["NpcScreen"]


class NpcScreen(ModalScreen[None]):
    """Somebody says one thing. Any key closes."""

    BINDINGS = [Binding("escape", "dismiss", "Close")]

    DEFAULT_CSS = """
    NpcScreen {
        align: center middle;
        background: $background 70%;
    }
    """

    def __init__(self, speaker: str, line: str) -> None:
        super().__init__()
        self.speaker = speaker
        self.line = line

    def compose(self) -> ComposeResult:
        with Vertical(id="npc"):
            yield Static(self.speaker.upper(), id="npc-title")
            yield Static(f"[italic]{self.line}[/]", id="npc-body")
            yield Static("press any key", id="npc-hint")

    def on_key(self, event) -> None:
        # A key still repeating from the screen before this one must not close
        # this one on the way in: holding ``c`` used to open and close the sheet
        # thirty times a second. See App.note_key.
        if self.app.note_key(event.key):
            event.stop()
            return
        event.stop()
        self.dismiss()
