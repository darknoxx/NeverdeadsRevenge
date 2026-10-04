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
from neverdeads_revenge.ui.screens.prologue import PrologueScreen
from neverdeads_revenge.ui.screens.title import TitleScreen

SIZE = (100, 34)


async def drive_to_game(app: NeverdeadsRevenge, pilot) -> GameScreen:
    """Title -> hero select -> game, ending on a live ``GameScreen``.

    Walks through the prologue if it is showing. It only appears on the first
    run of a session, so a test that drives the app twice needs this rather
    than a hardcoded keypress.
    """
    await pilot.pause()
    assert isinstance(app.screen, TitleScreen)

    await pilot.press("x")
    await pilot.pause()
    assert isinstance(app.screen, HeroSelectScreen)

    await pilot.press("enter")
    await pilot.pause()
    if isinstance(app.screen, PrologueScreen):
        await pilot.press("enter")
        await pilot.pause()

    assert isinstance(app.screen, GameScreen)
    return app.screen


# -- prologue ---------------------------------------------------------------
async def test_prologue_appears_on_the_first_run_only():
    """The premise is stated once per session, not once per run.

    Told every run it stops being a premise and becomes a toll, and players
    learn to press through it without reading.
    """
    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("x")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, PrologueScreen), "first run must tell the story"

        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, GameScreen)

        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("q")
        await pilot.pause()
        assert isinstance(app.screen, TitleScreen)

        await pilot.press("x")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, GameScreen), "prologue shown twice"


async def test_prologue_sits_between_the_hero_and_the_dungeon():
    """The premise is told before floor 1, not after.

    Read on the title screen it is skimming; read on floor 1 it is too late to
    still care.
    """
    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("x")
        await pilot.pause()
        assert isinstance(app.screen, HeroSelectScreen)

        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, PrologueScreen)

        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, GameScreen)


async def test_prologue_shows_every_line_of_the_story():
    from neverdeads_revenge.game.prologue import PROLOGUE, PROLOGUE_TITLE

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("x")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, PrologueScreen)
        shown = " ".join(
            str(widget.render()) for widget in screen.query("Static")
        )
        for line in (PROLOGUE_TITLE, *PROLOGUE):
            assert line in shown


async def test_prologue_is_skipped_by_any_key():
    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("x")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        await pilot.press("q")
        await pilot.pause()
        assert isinstance(app.screen, GameScreen)





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


# -- legend ------------------------------------------------------------------
async def test_legend_lists_every_monster_and_useful_terrain():
    """The legend is generated from the game data, so it cannot drift.

    Terrain and enemies are read from ``tiles.py`` and ``actors.py`` at render
    time. Adding either without touching the UI has to show up here.
    """
    from neverdeads_revenge.game.actors import ENEMIES
    from neverdeads_revenge.game.prologue import LEGEND_TERRAIN
    from neverdeads_revenge.ui.widgets.legend import Legend

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        shown = screen.query_one(Legend).render().plain

        assert "@" in shown
        for template in ENEMIES.values():
            assert template.glyph in shown, f"{template.key} missing from legend"
            assert template.name in shown
        for tile in LEGEND_TERRAIN:
            assert tile.glyph in shown, f"{tile.name} missing from legend"
            assert tile.description in shown


async def test_legend_fits_its_panel_without_wrapping():
    """Every legend line has to fit the panel width.

    A line that wraps pushes the rest of the legend down and quietly truncates
    the terrain half, which is the half a new player needs. Checked across
    depths, because the monster numbers are the part that grows.
    """
    from neverdeads_revenge.game.prologue import legend_rows
    from neverdeads_revenge.ui.widgets.legend import PANEL_WIDTH, USABLE_WIDTH

    assert USABLE_WIDTH == PANEL_WIDTH - 4, "padding and borders accounted for"
    for depth in range(1, 20):
        for glyph, meaning in legend_rows(depth):
            # 2 columns for the glyph and its trailing space, 1 for the indent
            # on a continuation line.
            line = len(meaning) + (2 if glyph else 1)
            assert line <= USABLE_WIDTH, (
                f"legend line too long at floor {depth} ({line}): {glyph} {meaning}"
            )


async def test_legend_shows_monster_numbers():
    """HP, damage and pace are what a player needs mid-fight."""
    from neverdeads_revenge.game.actors import ENEMIES
    from neverdeads_revenge.ui.widgets.legend import Legend

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        shown = screen.query_one(Legend).render().plain

        ghoul = ENEMIES["ghoul"]
        assert f"{ghoul.stats.max_hp} hp" in shown
        low, high = ghoul.stats.damage
        assert f"{low}-{high} dmg" in shown
        assert "slow" in shown, "ghoul is slower than the player"


async def test_legend_follows_the_player_down_the_floors():
    """Monster numbers on the legend have to describe the current floor.

    A sidebar that kept quoting floor-1 damage next to a floor-8 ghoul would be
    lying at exactly the moment the player needs the truth.
    """
    from neverdeads_revenge.game.actors import ENEMIES, scale_template
    from neverdeads_revenge.ui.widgets.legend import Legend

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        state = screen.state
        assert state is not None

        legend = screen.query_one(Legend)
        assert legend.depth == 1

        # Floor 1 is where the legend starts, so the map and the panel agree.
        first = scale_template(ENEMIES["ghoul"], 1).stats.damage
        assert f"{first[0]}-{first[1]} dmg" in legend.render().plain

        state.build_floor(8)
        await pilot.press(".")
        await pilot.pause()

        assert legend.depth == 8
        deep = scale_template(ENEMIES["ghoul"], 8).stats.damage
        assert deep != first, "the test is not looking at a floor that scales"
        shown = legend.render().plain
        assert f"{deep[0]}-{deep[1]} dmg" in shown
        assert f"{first[0]}-{first[1]} dmg" not in shown


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