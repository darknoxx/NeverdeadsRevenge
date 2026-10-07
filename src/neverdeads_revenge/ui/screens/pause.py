"""Pause menu.

Deliberately thin: resume, quit to title, and the sound. Saving a run
mid-dungeon is later work.

The sound toggle lives here because this is the only menu in the game, and a
sound you cannot turn off in a library is a sound that stops you playing.
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
        Binding("m", "toggle_sound", "Sound"),
        Binding("q", "quit_game", "Quit to title"),
    ]

    DEFAULT_CSS = """
    PauseScreen {
        align: center middle;
        /* Dim the dungeon behind the menu so the dialog reads as a layer. */
        background: $background 70%;
    }
    """

    def __init__(self, sfx=None) -> None:
        super().__init__()
        #: The session's sound, or ``None`` when the screen is pushed by name
        #: from somewhere that has no business knowing about audio.
        self.sfx = sfx

    def compose(self) -> ComposeResult:
        with Vertical(id="pause"):
            yield Static("PAUSED", id="pause-title")
            yield Static(id="pause-body")

    def on_mount(self) -> None:
        self._draw()

    def _draw(self) -> None:
        self.query_one("#pause-body", Static).update(
            "[bold]r[/] / [bold]escape[/]  resume\n"
            "[bold]q[/]                quit to title\n"
            f"[bold]m[/]                sound: {self._sound_line()}\n"
        )

    def _sound_line(self) -> str:
        if self.sfx is None or not self.sfx.available:
            # Said out loud rather than shown as "off": a player who presses the
            # key and hears nothing deserves to know it is the machine and not
            # the game.
            return "[dim]no player found[/]"
        return "[dim]off[/]" if self.sfx.muted else "[bold green]on[/]"

    def action_toggle_sound(self) -> None:
        if self.sfx is not None:
            # Through the app when there is one, so the choice is written down
            # and survives the next launch; the bare toggle is for the tests
            # that push this screen without an app behind it.
            if hasattr(self.app, "set_muted"):
                self.app.set_muted(not self.sfx.muted)
            else:
                self.sfx.toggle()
            self._draw()

    def action_resume(self) -> None:
        self.dismiss("resume")

    def action_quit_game(self) -> None:
        self.dismiss("quit")
