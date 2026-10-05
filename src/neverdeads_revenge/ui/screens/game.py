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
from ...game.prologue import GOAL_HINT, terrain_help
from ...game.state import GameState, start_run
from ..widgets.hud import Hud
from ..widgets.legend import Legend
from ..widgets.map_view import MapView
from ..widgets.message_log import MessageLog
from .character import CharacterScreen
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
    "i": Action.INVENTORY,
    "q": Action.QUAFF,
    ">": Action.DESCEND,
    # Enter is the interaction key: it takes what is under the player, or takes
    # the stairs if there is nothing to take. One key for "do the thing here",
    # because the alternative is a separate key per verb and a player looking
    # down at the keyboard to find it.
    "enter": Action.INTERACT,
    "return": Action.INTERACT,
}

HELP_TEXT = f"""\
[bold]movement   [/]w a s d  /  h j k l  /  arrows  /  y u b n   walk into a monster to attack
[bold]wait       [/].  or  space
[bold]interact   [/]enter      pick up what you are standing on, or take the stairs
[bold]descend    [/]>          the same, when you already know you want to go down
[bold]drink      [/]q          [bold]character [/]c          [bold]carried [/]i
[bold]the way out[/]  {GOAL_HINT}; step into it to win
[bold]help       [/]?          [bold]menu[/]  escape

[bold]terrain[/]
{terrain_help()}
"""


class GameScreen(Screen[None]):
    """One run of the dungeon."""

    BINDINGS = [
        Binding("question_mark", "help", "Help"),
        Binding("f1", "help", "Help"),
        Binding("c", "character", "Character"),
        Binding("escape", "menu", "Menu"),
    ]

    def __init__(self, hero_key: str = "noxx", seed: int | None = None) -> None:
        super().__init__()
        # Loud on an unknown key rather than falling back to the first hero. The
        # old fallback is precisely what hid a wiring bug that made every run
        # play Noxx no matter who was chosen: a silent default turns a broken
        # connection into a working-looking game.
        self.hero = HEROES[hero_key]
        self.seed = seed
        self.state: GameState | None = None

    # -- composition --------------------------------------------------------
    def compose(self) -> ComposeResult:
        with Vertical(id="game-screen"):
            with Horizontal(id="game-body"):
                yield MapView(id="map-view")
                with Vertical(id="sidebar"):
                    yield Hud(id="hud")
                    yield Legend(id="legend")
            yield MessageLog(id="message-log")
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
        legend = self.query_one(Legend)
        # Who is playing, before the first redraw: the "you" row is the hero's
        # glyph, and the panel would otherwise show the roster's first entry.
        legend.hero = self.hero
        legend.depth = self.state.depth
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
        # The legend quotes monster stats, which get worse every floor, and the
        # hero's own glyph, which depends on who is playing. Reactive, so this
        # only redraws the panel when one of them actually changes.
        legend = self.query_one(Legend)
        legend.depth = self.state.depth
        legend.hero = self.state.hero
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

        if result.died or result.escaped:
            self._game_over(won=result.escaped)

    def _game_over(self, won: bool = False) -> None:
        assert self.state is not None
        state = self.state
        summary = Text(no_wrap=True)
        if won:
            summary.append(f"Out of the dark on floor {state.depth}\n", style="bold bright_cyan")
        else:
            summary.append(f"Floor reached  {state.depth}\n", style="bold cyan")
        summary.append(f"Monsters slain  {state.kills}\n")
        summary.append(f"Turns taken     {state.total_turns}\n")
        summary.append(f"Cells walked    {state.player.steps}\n")
        # Shown on its own line, with a sign, so it reads as something earned
        # rather than another statistic. Speed is now part of the score and the
        # player should be able to see that it was.
        summary.append(
            f"Speed bonus     {state.speed_bonus:+d}\n",
            style="bold green" if state.speed_bonus else "dim",
        )
        summary.append(f"Score           {state.score}\n")
        if won:
            # The prologue opened by telling the player death was not granted to
            # them. This is the answer: they went and found the other way out.
            summary.append("\nYou were not granted death.\n", style="italic")

        self.app.push_screen(
            GameOverScreen(
                summary=str(summary),
                depth=state.depth,
                score=state.score,
                won=won,
            ),
            lambda _result: self.app.return_to_title(),
        )

    # -- actions ------------------------------------------------------------
    def action_help(self) -> None:
        self.app.push_screen("help")

    def action_character(self) -> None:
        """The full sheet. Costs no turn -- it is only a look."""
        assert self.state is not None
        self.app.push_screen(CharacterScreen(self.state))

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
