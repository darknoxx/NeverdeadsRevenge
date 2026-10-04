"""The Textual application.

Owns the screen stack and nothing else. All game rules live in ``game/``, and the
widgets in ``ui/widgets`` only draw what they are handed.

Screens are registered by name so they can be pushed without importing every
screen at module load.

Navigation goes through the callback of :meth:`App.push_screen` rather than
result messages: a screen's return value is only delivered to the callback it was
pushed with, so ``pause -> title`` and ``hero select -> game`` are wired at the
push site, where the pairing is visible.
"""

from __future__ import annotations

from textual.app import App

from .screens.game import GameScreen
from .screens.game_over import GameOverScreen
from .screens.hero_select import HeroSelectScreen
from .screens.pause import PauseScreen
from .screens.prologue import PrologueScreen
from .screens.title import TitleScreen

__all__ = ["NeverdeadsRevenge"]


class NeverdeadsRevenge(App[None]):
    """Neverdead's Revenge."""

    TITLE = "Neverdead's Revenge"
    CSS_PATH = "app.tcss"

    #: Set once the prologue has been shown. Session state, not saved progress:
    #: the premise is not worth re-reading, but it is also not worth persisting.
    _prologue_seen = False

    SCREENS = {
        "title": TitleScreen,
        "hero_select": HeroSelectScreen,
        "game": GameScreen,
        "pause": PauseScreen,
        "game_over": GameOverScreen,
        "prologue": PrologueScreen,
    }

    BINDINGS = [("ctrl+q", "quit", "Quit")]

    def on_mount(self) -> None:
        self.push_screen("title")

    # -- navigation ---------------------------------------------------------
    def open_hero_select(self) -> None:
        """Ask for a hero, then start a run with the answer.

        Pushing the game from here rather than from the hero screen keeps the
        screens in a stack that unwinds cleanly.
        """
        self.push_screen("hero_select", self.start_run)

    def start_run(self, hero_key: str) -> None:
        """Begin a run with the hero that was picked.

        The prologue is shown the first time only. Told once per run it stops
        being a premise and becomes a toll, and players learn to skip past it.
        """
        if self._prologue_seen:
            self._begin(hero_key)
            return

        self._prologue_seen = True
        self.push_screen("prologue", lambda _result: self._begin(hero_key))

    def _begin(self, hero_key: str) -> None:
        self.push_screen("game", hero_key)

    def return_to_title(self) -> None:
        """Drop every screen above the base screen and show the title.

        Used when a run ends. Popping one screen at a time is not enough: the
        stack still holds the title, hero select and game underneath.
        """
        while len(self.screen_stack) > 1:
            self.pop_screen()
        self.push_screen("title")
