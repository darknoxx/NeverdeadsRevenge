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

from ..game.state import GameState, RunState
from ..persistence import load_meta, save_meta
from .screens.game import GameScreen
from .screens.game_over import GameOverScreen
from .screens.help import HelpScreen
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
        "help": HelpScreen,
    }

    BINDINGS = [("ctrl+q", "quit", "Quit")]

    def __init__(self, seed: int | None = None) -> None:
        super().__init__()
        #: Fixes the dungeon for every run this app starts. Without it a run is
        #: seeded from system randomness, which makes any test that asserts on
        #: the floor a coin flip -- one of them was failing about once in
        #: seventy, on the seeds where an enemy can see the player from across a
        #: corridor at spawn.
        self.run_seed = seed
        #: What outlives a run. Loaded once, written on every ending. The file
        #: has been sitting there unread since the persistence layer was built.
        self.progress = load_meta()

    def record_run(self, state: GameState) -> int:
        """Fold a finished run into the saved progress. Returns the best score.

        Saving is best-effort on purpose: a home directory that cannot be
        written to is worth a shrug, and it is certainly not worth losing the
        summary screen over.
        """
        self.progress.record_run(
            depth=state.depth,
            score=state.score,
            kills=state.kills,
            won=state.run_state is RunState.ESCAPED,
        )
        try:
            save_meta(self.progress)
        except OSError:
            pass
        return self.progress.best_score

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
        # The screen is built here rather than pushed by name. A named push takes
        # no arguments -- ``push_screen``'s second parameter is the dismiss
        # callback, not a constructor argument -- so ``push_screen("game",
        # hero_key)`` silently passed the hero key as a callback and the screen
        # fell back to its default hero. That was invisible for as long as the
        # roster held exactly one.
        self.push_screen(GameScreen(hero_key, seed=self.run_seed))

    def return_to_title(self) -> None:
        """Drop every screen above the base screen and show the title.

        Used when a run ends. Popping one screen at a time is not enough: the
        stack still holds the title, hero select and game underneath.
        """
        while len(self.screen_stack) > 1:
            self.pop_screen()
        self.push_screen("title")
