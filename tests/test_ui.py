"""Tests for the Textual layer.

These drive the real app through :meth:`App.run_test`, so they cover wiring that
unit tests cannot: that screens are registered, that keys reach the game, and
that the screen stack flows title -> hero select -> game -> game over -> title.

No test here reaches into private widget internals beyond ``query_one``; the
point is the flow, not the layout.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from neverdeads_revenge.game import actors as actors_module
from neverdeads_revenge.game.state import GameState, RunState
from neverdeads_revenge.ui.app import NeverdeadsRevenge
from neverdeads_revenge.ui.screens.game import GameScreen
from neverdeads_revenge.ui.screens.game_over import GameOverScreen
from neverdeads_revenge.ui.screens.hero_select import FUTURE_HEROES, HeroSelectScreen
from neverdeads_revenge.ui.screens.pause import PauseScreen
from neverdeads_revenge.ui.screens.title import TitleScreen

SIZE = (100, 34)


async def drive_to_game(app: NeverdeadsRevenge, pilot) -> GameScreen:
    """Title -> hero select -> game, leaving the pilot on a live ``GameScreen``."""
    await pilot.pause()
    assert isinstance(app.screen, TitleScreen)

    await pilot.press("x")
    await pilot.pause()
    assert isinstance(app.screen, HeroSelectScreen)

    await pilot.press("enter")
    await pilot.pause()
    assert isinstance(app.screen, GameScreen)
    return app.screen


# -- the happy path ----------------------------------------------------------
async def test_flow_reaches_a_playable_game():
    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        state = screen.state

        assert state is not None
        assert state.hero.key == "noxx"
        assert state.player.alive
        assert state.player.hp == state.player.max_hp
        assert len(state.enemies) > 0
        assert state.dungeon_map.visible


async def test_movement_advances_the_turn():
    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        state = screen.state
        assert state is not None

        before = state.turn
        start = state.player.position

        # Walk in whatever direction has floor; the dungeon start is never boxed in.
        moved = False
        for key in ("d", "s", "a", "w"):
            await pilot.press(key)
            await pilot.pause()
            if state.player.position != start:
                moved = True
                break
        assert moved, "player never moved in any of the four cardinal directions"
        assert state.turn > before


async def test_waiting_advances_the_world():
    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        state = screen.state
        assert state is not None

        before = state.turn
        await pilot.press(".")
        await pilot.pause()
        assert state.turn == before + 1


async def test_escape_opens_pause_and_escape_returns():
    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        await drive_to_game(app, pilot)

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, PauseScreen)

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, GameScreen)


async def test_quit_from_pause_returns_to_title():
    """``q`` in the pause menu has to unwind the whole stack.

    The pause screen only reports a result to the callback it was pushed with,
    so this guards the wiring rather than the menu itself.
    """
    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        await drive_to_game(app, pilot)

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, PauseScreen)

        await pilot.press("q")
        await pilot.pause()
        assert isinstance(app.screen, TitleScreen)
        assert len(app.screen_stack) == 2, "the run's screens should be gone"


async def test_a_second_run_can_be_started_after_quitting():
    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        await drive_to_game(app, pilot)
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("q")
        await pilot.pause()

        await drive_to_game(app, pilot)


# -- hero select -------------------------------------------------------------
async def test_hero_select_cycles_into_locked_slots():
    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("x")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, HeroSelectScreen)

        total = len(actors_module.HEROES) + len(FUTURE_HEROES)
        assert len(screen.slots) == total
        assert screen.current is not None

        await pilot.press("right")
        await pilot.pause()

        # A locked slot must not start a run.
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, HeroSelectScreen)


async def test_hero_select_wraps_around():
    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("x")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, HeroSelectScreen)

        total = len(screen.slots)
        for _ in range(total):
            await pilot.press("right")
            await pilot.pause()
        assert screen._index == 0


async def test_hero_select_back_returns_to_title():
    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("x")
        await pilot.pause()
        assert isinstance(app.screen, HeroSelectScreen)

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, TitleScreen)


# -- death -------------------------------------------------------------------
async def test_death_opens_game_over_and_returns_to_title():
    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        state = screen.state
        assert state is not None

        # Kill the hero directly: the point of this test is the screen flow, not
        # the combat maths (which has its own tests).
        state.player.stats.hp = 0
        state.player.alive = False
        state.run_state = RunState.DEAD
        screen._game_over()
        await pilot.pause()
        assert isinstance(app.screen, GameOverScreen)

        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, TitleScreen)


# -- widgets -----------------------------------------------------------------
async def test_hud_reports_health_and_speed():
    from neverdeads_revenge.ui.widgets.hud import Hud

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        state = screen.state
        assert state is not None

        hud = screen.query_one(Hud)
        text = hud.render().plain

        assert state.player.name in text
        assert f"{state.player.hp}/{state.player.max_hp}" in text
        assert f"{state.player.stats.speed:.2f}" in text


async def test_hud_survives_a_damaged_hero():
    from neverdeads_revenge.ui.widgets.hud import Hud

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        state = screen.state
        assert state is not None

        state.player.stats.hp = 1
        hud = screen.query_one(Hud)
        hud.redraw()
        assert "1/" in hud.render().plain


async def test_message_log_shows_the_opening_lines():
    from neverdeads_revenge.ui.widgets.message_log import MessageLog

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        state = screen.state
        assert state is not None

        log = screen.query_one(MessageLog)
        shown = " ".join(getattr(line, "plain", str(line)) for line in log.lines)
        assert state.log, "the run should open with at least one message"
        assert state.log[0].text in shown


async def test_map_view_renders_around_the_player():
    from neverdeads_revenge.ui.widgets.map_view import MapView

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        state = screen.state
        assert state is not None

        frame = screen.query_one(MapView).render().plain
        assert state.player.glyph in frame
        assert len(frame.splitlines()) > 5


# -- theming -----------------------------------------------------------------
def read_css() -> str:
    return (Path(__file__).parent.parent / "src/neverdeads_revenge/ui/app.tcss").read_text()


def test_stylesheet_parses():
    """The app must not fail to start because of a bad rule.

    Parsed here with the same theme the app runs under, so an invalid rule fails
    a fast test instead of a headless UI run.
    """
    from textual.css.stylesheet import Stylesheet
    from textual.theme import BUILTIN_THEMES

    variables = dict(BUILTIN_THEMES["textual-dark"].to_color_system().generate())
    sheet = Stylesheet(variables=variables)
    sheet.add_source(read_css(), read_from=("app.tcss", 1))
    sheet.parse()


def test_no_rich_only_greys_in_stylesheet():
    """``greyNN`` works in Rich styles but not in Textual CSS.

    Mixing the two up makes every screen fail to mount, which is an expensive
    way to learn a colour name.
    """
    body = "\n".join(
        line for line in read_css().splitlines() if not line.strip().startswith(("/*", "*"))
    )
    for name in ("grey", "gray"):
        for digit in "0123456789":
            assert f"{name}{digit}" not in body, (
                f"numbered {name} greys are Rich-only, not valid CSS colours"
            )


@pytest.mark.parametrize("key", ["ctrl+q"])
async def test_quit_binding_exists(key):
    """The app binds ctrl+q; pressing it must not raise."""
    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press(key)
        await pilot.pause()