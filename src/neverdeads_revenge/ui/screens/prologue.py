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
from textual.css.query import NoMatches
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Static

from ...game.prologue import PROLOGUE, PROLOGUE_HINT, PROLOGUE_TITLE
from ..hold import HoldToContinue

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
            yield Static(id="prologue-dismiss")

    def on_mount(self) -> None:
        # The bar is driven by a clock rather than by key presses, so a held key
        # fills it smoothly instead of in jumps.
        self._timer = self.set_interval(0.05, self._advance)
        self._draw_hint()

    def on_unmount(self) -> None:
        # A timer outliving its screen fires into a widget tree that is gone.
        self._timer.stop()

    # -- input --------------------------------------------------------------
    def on_key(self, event) -> None:
        scroller = self.query_one("#prologue-screen", VerticalScroll)

        method = SCROLL_KEYS.get(event.key)
        if method is not None:
            getattr(scroller, method)()
            event.stop()
            return

        if event.key in (*self._hold.keys, "escape"):
            event.stop()
            if self._hold.press(event.key):
                self.dismiss()
            return

        # Anything else is left alone. Swallowing it would take ctrl+q with it,
        # and there is nothing here worth trapping somebody in.

    def _advance(self) -> None:
        if not self.is_mounted:
            return
        if self._hold.tick():
            self.dismiss()
            return
        self._draw_hint()

    def _draw_hint(self) -> None:
        if not self.is_mounted:
            return
        filled = round(self._hold.progress * 10)
        bar = self._hold.bar()
        try:
            hint = self.query_one("#prologue-dismiss", Static)
        except NoMatches:
            # Teardown race: the screen is still "mounted" for a moment after
            # its children are gone, and the timer can land in that window.
            return
        hint.update(
            f"hold [bold]enter[/] to begin   "
            f"[{_FILLED}]{bar[:filled]}[/][#4a4a4a]{bar[filled:]}[/]"
        )


_FILLED = "#a855f7"
