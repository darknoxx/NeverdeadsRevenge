"""The prologue screen.

Shown once, between the hero choice and floor 1. It exists because the game has
a premise that the mechanics cannot state: the hero is dead, came back anyway, and
the dungeon is the way out. Everything after this has to work without repeating
it.

It used to close on any key, which meant a stray press cost the player the only
prose in the game. Now the arrows scroll it and only a held enter lets it go.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Static

from ...game.prologue import PROLOGUE, PROLOGUE_HINT, PROLOGUE_TITLE
from ..hold import BAR_CELLS, HoldToContinue

__all__ = ["PrologueScreen"]

#: Key -> what it does to the story. Everything here scrolls; nothing closes.
SCROLL_KEYS: dict[str, str] = {
    "down": "scroll_down",
    "up": "scroll_up",
    "pagedown": "scroll_page_down",
    "pageup": "scroll_page_up",
    "space": "scroll_page_down",
    "home": "scroll_home",
    "end": "scroll_end",
}

_FILLED = "#a855f7"


class PrologueScreen(Screen[None]):
    """The premise, once per session."""

    DEFAULT_CSS = """
    PrologueScreen {
        align: center middle;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._hold = HoldToContinue()

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="prologue-screen"):
            yield Static(PROLOGUE_TITLE, id="prologue-title")
            for line in PROLOGUE:
                # A class rather than a per-line id: ids must be unique, and a
                # class survives the prologue growing a line.
                yield Static(line, classes="prologue-line")
            # Set apart from the story: the story is what happened, this is what
            # it means, and running them together buries the one line the player
            # is meant to leave with.
            yield Static(PROLOGUE_HINT, id="prologue-hint")
            yield Static(self._hint(), id="prologue-dismiss")

    # -- input --------------------------------------------------------------
    def on_key(self, event) -> None:
        method = SCROLL_KEYS.get(event.key)
        if method is not None:
            getattr(self.query_one("#prologue-screen", VerticalScroll), method)()
            event.stop()
            return

        if event.key in (*self._hold.keys, "escape"):
            # Told to the app as well, so the screen that comes next can tell a
            # repeat of this press from a new one. Without that, holding enter
            # here goes on to walk the hero around the first room.
            self.app.note_key(event.key)
            event.stop()
            if self._hold.press(event.key):
                self.app.arm_repeat_filter()
                self.dismiss()
                return
            self._draw_hint()
            return

        # Anything else is left alone. Swallowing it would take ctrl+q with it,
        # and there is nothing here worth trapping somebody in.

    def _draw_hint(self) -> None:
        self.query_one("#prologue-dismiss", Static).update(self._hint())

    def _hint(self) -> str:
        filled = round(self._hold.progress * BAR_CELLS)
        bar = self._hold.bar()
        return (
            "hold [bold]enter[/] to begin   "
            f"[{_FILLED}]{bar[:filled]}[/][#4a4a4a]{bar[filled:]}[/]"
        )
