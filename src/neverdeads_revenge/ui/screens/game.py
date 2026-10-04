"""The main game screen.

Keeps no game rules of its own. Keys are mapped to a
:class:`~neverdeads_revenge.game.actions.Action`, handed to
:func:`~neverdeads_revenge.game.actions.perform_action`, and the resulting state is
pushed into the widgets. Every rule lives in ``game/``.

Movement keys are bound here rather than relying on focus traversal, because arrow
keys have to move Noxx rather than scroll a panel.
"""

from __future__ import annotations

import random

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Static

from ...game.actions import Action, perform_action
from ...game.actors import HEROES
from ...game.state import GameState, start_run
from ..widgets.hud import Hud
from ..widgets.legend import Legend
from ..widgets.map_view import MapView
from ..widgets.message_log import MessageLog
from .game_over import GameOverScreen

__all__ = ["GameScreen"]


#: Key -> action. Arrows are included so the map feels like a map.
KEY_BINDINGS: dict[str, Action] = {
    "up": Action.MOVE_NORTH,
    "k": Action.MOVE_NORTH,
    "w": Action.MOVE_NORTH,
    "down": Action.MOVE_SOUTH,
    "j": Action.MOVE_SOUTH,
    "s": Action.MOVE_SOUTH,
    "left": Action.MOVE_WEST,
    "h": Action.MOVE_WEST,
    "a": Action.MOVE_WEST,
    "right": Action.MOVE_EAST,
    "l": Action.MOVE_EAST,
    "d": Action.MOVE_EAST,
    "y": Action.MOVE_NW,
    "u": Action.MOVE_NE,
    "b": Action.MOVE_SW,
    "n": Action.MOVE_SE,
    "home": Action.MOVE_NW,
    "pageup": Action.MOVE_NE,
    "end": Action.MOVE_SW,
    "pagedown": Action.MOVE_SE,
    ".": Action.WAIT,
    "space": Action.WAIT,
    "g": Action.PICK_UP,
    ">": Action.DESCEND,
    # Enter and return take the stairs too, for players who expect enter to
    # mean "interact with what is under me". Both keys, like ``>``, only work
    # while standing on the staircase.
    "enter": Action.DESCEND,
    "return": Action.DESCEND,
}

HELP_TEXT = """\
[bold]movement   [/]w a s d  /  h j k l  /  arrows  /  y u b n   walk into a monster to attack
[bold]wait       [/].  or  space
[bold]pick up    [/]g
[bold]descend    [/]>   or  enter /  return  while standing on the stairs
[bold]help       [/]?          [bold]menu[/]escape
"""


class GameScreen(Screen[None]):
    """One run of the dungeon."""

    BINDINGS = [
        Binding("question_mark", "help", "Help"),
        Binding("f1", "help", "Help"),
        Binding("escape", "menu", "Menu"),
    ]

    def __init__(self, hero_key: str = "noxx", seed: int | None = None) -> None:
        super().__init__()
        self.hero = HEROES.get(hero_key, next(iter(HEROES.values())))
        self.seed = seed
        self.state: GameState | None = None

    # -- composition --------------------------------------------------------
    def compose(self) -> ComposeResult:
        with Vertical(id="game-screen"):
            with Horizontal(id="game-body"):
                yield MapView(id="map-view")
                yield Hud(id="sidebar")
            with Horizontal(id="game-footer"):
                yield MessageLog(id="message-log")
                yield Legend(id="legend")
        yield Footer()

    def on_mount(self) -> None:
        self._start_run()

    # -- run lifecycle ------------------------------------------------------
    def _start_run(self) -> None:
        seed = self.seed if self.seed is not None else _fresh_seed()
        self.state = start_run(self.hero, seed=seed)
        map_view = self.query_one(MapView)
        map_view.state = self.state
        self.query_one(Hud).state = self.state
        log = self.query_one(MessageLog)
        log.reset()
        log.show_new(self.state)
        self._update_footer()

    def _update_footer(self) -> None:
        assert self.state is not None
        self.sub_title = (
            f"floor {self.state.depth} · turn {self.state.turn} · kills {self.state.kills}"
        )

    def _refresh_all(self) -> None:
        assert self.state is not None
        self.query_one(MapView).refresh()
        self.query_one(Hud).redraw()
        self.query_one(MessageLog).show_new(self.state)
        # The legend quotes monster stats, which get worse every floor. Reactive,
        # so this only redraws the panel on an actual descent.
        self.query_one(Legend).depth = self.state.depth
        self._update_footer()

    # -- input --------------------------------------------------------------
    def on_key(self, event) -> None:
        """Turn a keypress into an action, if it maps to one.

        ``KEY_BINDINGS`` is keyed by what a human types, but Textual reports
        punctuation under its own names -- ``.`` arrives as ``full_stop`` and
        ``>`` as ``greater_than_sign``. Matching on ``character`` as well keeps
        the table honest.
        """
        if self.state is None:
            return

        action = KEY_BINDINGS.get(event.key) or KEY_BINDINGS.get(event.key.lower())
        if action is None and event.character:
            action = KEY_BINDINGS.get(event.character)
        if action is None:
            return  # let the bindings above have it

        event.stop()
        event.prevent_default()
        self._do(action)

    def _do(self, action: Action) -> None:
        assert self.state is not None
        result = perform_action(self.state, action)
        self._refresh_all()

        if result.died:
            self._game_over()

    def _game_over(self) -> None:
        assert self.state is not None
        state = self.state
        summary = Text(no_wrap=True)
        summary.append(f"Floor reached  {state.depth}\n", style="bold cyan")
        summary.append(f"Monsters slain  {state.kills}\n")
        summary.append(f"Turns taken     {state.total_turns}\n")
        summary.append(f"Cells walked    {state.player.steps}\n")
        summary.append(f"Score           {state.score}\n")

        self.app.push_screen(
            GameOverScreen(
                summary=str(summary),
                depth=state.depth,
                score=state.score,
            ),
            lambda _result: self.app.return_to_title(),
        )

    # -- actions ------------------------------------------------------------
    def action_help(self) -> None:
        self.notify(HELP_TEXT, title="Controls", timeout=8)

    def action_menu(self) -> None:
        self.app.push_screen("pause", self._pause_result)

    def _pause_result(self, result: str | None) -> None:
        """Quit from the pause menu ends the run without a death."""
        if result == "quit":
            self.app.return_to_title()


def _fresh_seed() -> int:
    """A new run seed.

    Uses system randomness on purpose: the run's own generator is seeded
    separately and deterministically, which is what a seed is for.
    """
    return random.SystemRandom().randrange(2**32)
