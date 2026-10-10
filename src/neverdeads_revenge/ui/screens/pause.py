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
        Binding("s", "save_and_quit", "Save and quit"),
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
            "[bold]s[/]                save and quit\n"
            "[bold]q[/]                quit to title, and lose the run\n"
            f"[bold]m[/]                sound: {self._sound_line()}\n"
        )

    def _sound_line(self) -> str:
        if self.sfx is None or not self.sfx.available:
            # Said out loud rather than shown as "off": a player who presses the
            # key and hears nothing deserves to know it is the machine and not
            # the game.
            return "[dim]no player found[/]"
        return "[dim]off[/]" if self.sfx.muted else "[bold green]on[/]"

    # A key still repeating from the screen before this one must not answer this
    # one on the way in. See App.note_key. Only the repeats are stopped:
    # everything else has to reach the bindings, which is where the answer is.
    def on_key(self, event) -> None:
        if self.app.note_key(event.key):
            event.stop()

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

    def action_save_and_quit(self) -> None:
        self.dismiss("save")

    def action_quit_game(self) -> None:
        """``q`` asks first, because the run does not come back.

        The pause menu's ``q`` throws the run away without writing it down --
        ``s`` is the one that saves -- so it gets the same question the title
        gets before it closes the game, and for the same reason: it is not
        something another keypress can undo.
        """
        from .confirm import ConfirmScreen

        # Armed first: ``q`` is still down, and a dialog that answers its own
        # opening keypress answers a question nobody read.
        self.app.arm_repeat_filter()
        self.app.push_screen(
            ConfirmScreen(
                "QUIT TO THE TITLE?",
                "The run is not written down. Everything you are carrying "
                "goes with it.",
            ),
            self._quit_confirmed,
        )

    def _quit_confirmed(self, answer: bool | None) -> None:
        if answer:
            self.dismiss("quit")
