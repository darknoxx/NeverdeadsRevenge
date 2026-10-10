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
from textual.widgets import Footer

from ...core.direction import Direction
from ...game.actions import Action, perform_action
from ...game.actors import HEROES
from ...game.lore import page
from ...game.shop import Loadout
from ...game.prologue import GOAL_HINT, terrain_help
from ...game.state import GameState, start_run
from ..audio import loudest_kind, sound_for_kind
from ..widgets.hud import Hud
from ..widgets.legend import Legend
from ..widgets.marks import Marks
from ..widgets.map_view import MapView
from ..widgets.message_log import MessageLog
from .character import CharacterScreen
from .chest import OPEN, ChestScreen
from .game_over import REWIND, GameOverScreen
from .inventory import InventoryScreen
from .name_entry import NameEntryScreen
from .npc import NpcScreen
from .page import PageScreen
from .pause import PauseScreen
from .spring import SpringScreen

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
    # The borrowed hour. Bound always, and does nothing without the gift --
    # ``perform_action`` refuses it when there is no hour in hand, which is the
    # same place every other refusal lives.
    "r": Action.REWIND,
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

    def __init__(
        self,
        hero_key: str = "noxx",
        seed: int | None = None,
        loadout: Loadout | None = None,
        state: GameState | None = None,
        pages: tuple[int, ...] | None = None,
    ) -> None:
        super().__init__()
        # Loud on an unknown key rather than falling back to the first hero. The
        # old fallback is precisely what hid a wiring bug that made every run
        # play Noxx no matter who was chosen: a silent default turns a broken
        # connection into a working-looking game.
        self.hero = HEROES[hero_key]
        self.seed = seed
        #: What the shop sold for this run. Empty for a run that bought nothing.
        self.loadout = loadout or Loadout()
        #: A run picked up from the disk rather than started fresh. Handed in
        #: ready-made, because the whole point of a save is that the floor is the
        #: floor you left.
        self.state: GameState | None = state
        #: Which pages of the chronicle are still out there. Handed in from the
        #: book rather than read off it here, so the screen has no opinion
        #: about what has been found -- it only says what to scatter.
        self.pages = pages

    # -- composition --------------------------------------------------------
    def compose(self) -> ComposeResult:
        with Horizontal(id="game-screen"):
            # The map column: the map, and the log and the marks beneath it.
            with Vertical(id="main"):
                yield MapView(id="map-view")
                # The log and the marks share this row: the log, then what is
                # being done to you (curses, statuses), then what you have been
                # given (gifts, effects). Names only, so the columns are narrow
                # and the whole of it fits in the glance.
                with Horizontal(id="bottom"):
                    yield MessageLog(id="message-log")
                    yield Marks(("curses", "statuses"), id="curses")
                    yield Marks(("gifts", "effects"), id="marks")
            # The sidebar runs the full height, beside the log as well as the
            # map. Not decoration: the legend needs thirteen rows, and while the
            # sidebar stopped at the log it could not give them -- which is what
            # quietly pushed the draughts off the bottom of the panel.
            with Vertical(id="sidebar"):
                yield Hud(id="hud")
                yield Legend(id="legend")
        yield Footer()

    def on_mount(self) -> None:
        self._start_run()

    # -- run lifecycle ------------------------------------------------------
    def _start_run(self) -> None:
        if self.state is None:
            seed = self.seed if self.seed is not None else _fresh_seed()
            self.state = start_run(
                self.hero, seed=seed, loadout=self.loadout, pages=self.pages
            )
        map_view = self.query_one(MapView)
        map_view.state = self.state
        self.query_one(Hud).state = self.state
        for column in self.query(Marks):
            column.state = self.state
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
        # The columns are redrawn by call rather than by assignment: the run is
        # mutated in place, so setting the same object back would not fire the
        # reactive. A curse and a gift arrive at the same moment, and a descent
        # lifts one and changes what the borrowed hour is worth, so this is one
        # call for all of it.
        for column in self.query(Marks):
            column.redraw()
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

        # A key still being repeated from the screen before this one is not a
        # new press and must not act. See App.note_key.
        if event.key in ("enter", "return") and self.app.note_key(event.key):
            event.stop()
            return

        action = KEY_BINDINGS.get(event.key) or KEY_BINDINGS.get(event.key.lower())
        if action is None and event.character:
            action = KEY_BINDINGS.get(event.character)
        if action is None:
            return  # let the bindings above have it

        event.stop()
        event.prevent_default()
        # Only *movement* is throttled, and the narrowness is the point.
        #
        # A direction held down is the terminal talking at thirty-three words a
        # second, and that is the thing that made a fight an unreadable blur and
        # dropped two sounds in three. Every other key is a deliberate press
        # that a player may well make twice in quick succession -- take the
        # draught and then the stairs, wait and then wait again -- and swallowing
        # one of those would be the throttle costing more than it pays for.
        #
        # There is no way to tell a repeat from a fast press: Textual's key
        # event carries only ``key`` and ``character``, and the two are the same
        # event. So the rule is the one that is *safe* to apply to both.
        if (
            action.direction is not Direction.NONE
            and not self.app.allows_action(event.key, self.state.player.speed)
        ):
            return
        self._do(action)

    def _do(self, action: Action) -> None:
        assert self.state is not None

        if action is Action.INVENTORY:
            # A look, not a turn. The domain verb still exists and is still
            # headless -- it reports the pack as a line of text -- and the screen
            # is what the UI does with the same question.
            self.app.arm_repeat_filter()
            self.app.push_screen(InventoryScreen(self.state))
            return

        before_log = len(self.state.log)
        before_depth = self.state.depth
        before_level = self.state.level

        result = perform_action(self.state, action)
        self._refresh_all()
        self._file_pages()
        self._sound_after(before_log, before_depth, before_level)

        if result.prompt is not None:
            # The domain says a decision is needed; the UI asks for it. The deed
            # happens only if the answer comes back yes, which is why neither
            # opening a chest nor washing a curse is bound to a key.
            #
            # Armed before every dialog: whatever key opened it is still down,
            # and a dialog that reads its own opening keypress answers a question
            # the player has not been asked yet.
            self.app.arm_repeat_filter()
            if result.prompt_kind == "spring":
                self.app.push_screen(SpringScreen(result.prompt), self._spring_answer)
            elif result.prompt_kind == "npc":
                self.app.push_screen(NpcScreen(result.speaker, result.prompt))
            else:
                self.app.push_screen(ChestScreen(result.prompt), self._chest_answer)
            return

        if result.died or result.escaped:
            self._game_over(won=result.escaped)

    def _spring_answer(self, wash_it: bool | None) -> None:
        """Act on the answer. Walking away costs nothing at all."""
        if not wash_it or self.state is None:
            return
        result = perform_action(self.state, Action.CLEANSE)
        self._refresh_all()
        if result.died or result.escaped:
            self._game_over(won=result.escaped)

    def _sound_after(
        self, before_log: int, before_depth: int, before_level: int
    ) -> None:
        """Make the noise the last thing that happened deserves.

        A descent and a level are events rather than messages, so they are
        checked first and take the turn's sound for themselves. Everything else
        is read off the log, which already knows whether a line was a hit, a
        crit or a wound -- so the rules are not written down a second time.

        Nothing at all while the run is ending: ``_game_over`` has a sound of its
        own and two at once is one too many.
        """
        assert self.state is not None
        if self.state.over:
            return
        if self.state.depth != before_depth:
            self._play("stairs")
            return
        if self.state.level != before_level:
            self._play("level")
            return
        kind = loudest_kind(entry.kind for entry in self.state.log[before_log:])
        self._play(sound_for_kind(kind) if kind is not None else None)

    def _play(self, name: str | None) -> None:
        if name:
            self.app.sfx.play(name)

    def _file_pages(self) -> None:
        """Put whatever the run has found into the book -- and open it.

        At once rather than at the end of the run, and that is a decision worth
        writing down: gold is banked when a run ends because gold is a *price*,
        and a run that dies still spent it. A page is knowledge -- a player who
        dies on the next step should not have to find the same page again.

        The screen is the other half of that. A page that went silently into a
        book the player has not opened yet is a collectible nobody read, so the
        game stops and shows it, the way it stops for a chest: this is prose, and
        prose in the message log scrolls away in four turns.

        ``record_page`` answers whether the page was new, which is what makes
        this safe to run over the whole list every time *and* what keeps the
        screen from appearing twice -- a run picked up from a save has its pages
        already in the book, and it stays quiet about them.
        """
        assert self.state is not None
        for number in self.state.found_pages:
            if not self.app.progress.record_page(number):
                continue
            self._play("item")
            self.app.save_progress()
            text = page(number)
            if text is None:
                continue
            # Armed first: the page was picked up with a key that is still down,
            # and the screen closes on any key. Without this the page opens and
            # shuts before a word of it is read.
            self.app.arm_repeat_filter()
            self.app.push_screen(PageScreen(number, text))

    def _chest_answer(self, answer: str | None) -> None:
        """Act on the answer. Walking away costs nothing at all.

        The price is the same either way; what changes is what is bought with
        it -- the blade behind the lid, or the name at the end of the run.
        """
        if not answer or self.state is None:
            return
        self._play("chest")
        action = Action.OPEN_CHEST if answer == OPEN else Action.TAKE_FAME
        result = perform_action(self.state, action)
        self._refresh_all()
        if result.died or result.escaped:
            self._game_over(won=result.escaped)

    def _game_over(self, won: bool = False) -> None:
        assert self.state is not None
        state = self.state
        self._play("victory" if won else "death")
        summary = Text(no_wrap=True)
        if won:
            summary.append(f"Out of the dark on floor {state.depth}\n", style="bold bright_cyan")
        else:
            summary.append(f"Floor reached  {state.depth}\n", style="bold cyan")
        summary.append(f"Monsters slain  {state.kills}\n")
        # The score has four parts now, so the summary names them all: a number
        # nobody can break down is a number nobody can play for.
        summary.append(
            f"Kill score      {state.kill_score}\n",
            style="bold white" if state.kill_score else "dim",
        )
        summary.append(f"Level reached   {state.level}\n")
        # The purse, not the total picked up: a spring costs forty and the toll
        # five a floor, and both come out of it before this line is written. It
        # said "gathered", which read as a lifetime total and was the balance.
        summary.append(f"Coins banked    {state.gold}\n")
        summary.append(f"Turns taken     {state.total_turns}\n")
        summary.append(f"Cells walked    {state.player.steps}\n")
        # Shown on its own line, with a sign, so it reads as something earned
        # rather than another statistic. Speed is now part of the score and the
        # player should be able to see that it was.
        summary.append(
            f"Speed bonus     {state.speed_bonus:+d}\n",
            style="bold green" if state.speed_bonus else "dim",
        )
        if state.fame:
            summary.append(
                f"Fame            {state.fame}  "
                f"(the run is worth {state.score_multiplier:.2f}x)\n",
                style="bold green",
            )
        summary.append(f"Score           {state.score}\n")
        if won:
            # The prologue opened by telling the player death was not granted to
            # them. This is the answer: they went and found the other way out.
            summary.append("\nYou were not granted death.\n", style="italic")

        # The best *including* this run, which is what the player is looking
        # for. The run itself is written down after the name, so the file is
        # touched once.
        best = max(self.app.progress.best_score, state.score)

        self.app.push_screen(
            GameOverScreen(
                summary=str(summary),
                depth=state.depth,
                score=state.score,
                won=won,
                best=best,
                can_rewind=state.rewind_ready and not won,
            ),
            lambda answer: self._after_summary(state, answer),
        )

    def _after_summary(self, state: GameState, answer: str | None) -> None:
        """The hour, or the name.

        The only way back into a run that has ended, and it is deliberately the
        *first* thing offered: a player who has just died is looking at the
        number, not at the hint, and the hour is spent the moment they carry on.
        """
        if answer != REWIND:
            self._ask_for_a_name(state)
            return
        self.app.arm_repeat_filter()
        perform_action(state, Action.REWIND)
        self._refresh_all()

    def _ask_for_a_name(self, state: GameState) -> None:
        """Every run gets a name, win or lose -- both collected points."""
        self.app.push_screen(
            NameEntryScreen(state.score, self.app.progress.last_name),
            lambda name: self._record(state, name),
        )

    def _record(self, state: GameState, name: str) -> None:
        self.app.record_run(state, name or "???")
        self.app.return_to_title()

    # -- actions ------------------------------------------------------------
    def action_help(self) -> None:
        # A binding, not a key event: the app never saw the ``?``, so the filter
        # has to be told what to look for.
        self.app.arm_repeat_filter("?")
        self.app.push_screen("help")

    def action_character(self) -> None:
        """The full sheet. Costs no turn -- it is only a look."""
        assert self.state is not None
        self.app.arm_repeat_filter("c")
        self.app.push_screen(CharacterScreen(self.state))

    def action_menu(self) -> None:
        # An instance rather than a name, so the menu can be told whether the
        # sound is on before it draws itself. And the opening key is recorded:
        # ``escape`` opens this menu *and* is ``resume`` in it, so a held
        # ``escape`` would otherwise close the menu it just opened.
        self.app.arm_repeat_filter("escape")
        self.app.push_screen(PauseScreen(self.app.sfx), self._pause_result)

    def _pause_result(self, result: str | None) -> None:
        """Quit from the pause menu ends the run without a death.

        Two ways out, and the difference matters: one writes the floor down and
        one does not. Neither is a death, so neither is recorded as a run.
        """
        if result == "save":
            self.app.save_run()
            self.app.return_to_title()
        elif result == "quit":
            self.app.return_to_title()


def _fresh_seed() -> int:
    """A new run seed.

    Uses system randomness on purpose: the run's own generator is seeded
    separately and deterministically, which is what a seed is for.
    """
    return random.SystemRandom().randrange(2**32)
