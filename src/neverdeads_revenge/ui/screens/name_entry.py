"""Enter your name for the scoreboard.

Five slots, arcade style, because that is what a scoreboard wants: something
short enough to fit a column and to be worth reading twice.

Deliberately not a Textual ``Input``. A held key from the screen before this one
keeps arriving, and an ``Input`` would take those repeats as typing -- the same
bug that walked the hero around the first room, one screen later. Handling every
key here means the repeats can be recognised and dropped.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

__all__ = ["NameEntryScreen", "SLOTS", "clean_name"]

#: Letters in a name. Five, because it has to fit a column and be readable at a
#: glance; more would be a sentence.
SLOTS = 5

#: What a name may contain. Uppercase letters and digits, nothing else -- the
#: scoreboard is a table, and punctuation in a table is noise.
ALLOWED = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")


def clean_name(raw: str) -> str:
    """Whatever the player typed, as it goes on the board."""
    letters = [char for char in raw.upper() if char in ALLOWED]
    return "".join(letters[:SLOTS])


class NameEntryScreen(ModalScreen[str]):
    """Returns the name, never empty."""

    BINDINGS = [Binding("escape", "keep", "Keep")]

    DEFAULT_CSS = """
    NameEntryScreen {
        align: center middle;
        background: $background 70%;
    }
    """

    def __init__(self, score: int, previous: str = "") -> None:
        super().__init__()
        self.score = score
        self._name = clean_name(previous)

    def compose(self) -> ComposeResult:
        with Vertical(id="name-entry"):
            yield Static("ENTER YOUR NAME", id="name-entry-title")
            yield Static(f"for a score of {self.score}", id="name-entry-score")
            yield Static(id="name-entry-slots")
            yield Static(
                "letters and digits   [bold]backspace[/]   [bold]enter[/] to keep",
                id="name-entry-hint",
            )

    def on_mount(self) -> None:
        self._draw()

    # -- input --------------------------------------------------------------
    def on_key(self, event) -> None:
        # A key still repeating from the summary screen is not typing.
        if self.app.note_key(event.key):
            event.stop()
            return

        if event.key in ("enter", "return", "escape"):
            event.stop()
            self.action_keep()
            return

        if event.key in ("backspace", "delete"):
            event.stop()
            self._name = self._name[:-1]
            self._draw()
            return

        char = clean_name(event.character or "")
        if char:
            event.stop()
            if len(self._name) < SLOTS:
                self._name += char
            self._draw()
            return

        # Everything else is left alone, so ctrl+q still works.

    def action_keep(self) -> None:
        """Take the name as it stands, falling back to something readable."""
        self.dismiss(self._name or "???")

    # -- drawing ------------------------------------------------------------
    def _draw(self) -> None:
        cells = []
        for index in range(SLOTS):
            filled = index < len(self._name)
            char = self._name[index] if filled else " "
            if index == len(self._name):
                cells.append(f"[reverse]{char}[/reverse]")
            elif filled:
                cells.append(f"[bold]{char}[/bold]")
            else:
                cells.append(f"[#4a4a4a]{char}[/]")
        self.query_one("#name-entry-slots", Static).update("  ".join(cells))
