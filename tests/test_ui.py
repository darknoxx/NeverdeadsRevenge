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
from neverdeads_revenge.game.actions import Action
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


async def test_legend_lists_the_rift_and_the_loot():
    """The way out and the draughts have to be in the panel too.

    A player who cannot look up what ``!`` is will walk past the thing that keeps
    them alive, and one who cannot look up ``%`` will not know what they are
    looking for.
    """
    from neverdeads_revenge.game.prologue import GOAL_HINT
    from neverdeads_revenge.ui.widgets.legend import Legend
    from neverdeads_revenge.world.items import ITEMS
    from neverdeads_revenge.world.tiles import Tile

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        shown = screen.query_one(Legend).render().plain

        assert Tile.RIFT.glyph in shown, "the way out is not on the legend"
        for item in ITEMS.values():
            assert item.glyph in shown, f"{item.key} missing from legend"
            assert f"heals {item.heal}" in shown
        assert GOAL_HINT in shown, "the goal is not stated anywhere on screen"


async def test_hud_shows_how_deep_the_run_has_to_go():
    """The goal, as a number the player can plan against."""
    from neverdeads_revenge.ui.widgets.hud import Hud
    from neverdeads_revenge.world.generator import ESCAPE_DEPTH

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        shown = screen.query_one(Hud).render().plain
        assert f"Floor 1/{ESCAPE_DEPTH}" in shown


async def test_hud_counts_the_draughts_you_are_carrying():
    from neverdeads_revenge.ui.widgets.hud import Hud
    from neverdeads_revenge.world.items import ITEMS, make_item

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        state = screen.state
        assert state is not None

        assert "Draughts 0" in screen.query_one(Hud).render().plain

        state.inventory.append(make_item(ITEMS["elixir"]))
        await pilot.press(".")
        await pilot.pause()

        assert "Draughts 1" in screen.query_one(Hud).render().plain


async def test_enter_picks_up_and_q_drinks():
    """``enter`` has to do the thing, and ``q`` has to drink it.

    Both keys are checked through the real key path rather than by calling the
    action, because the interesting failure is a key that never reaches the game
    layer at all.
    """
    from neverdeads_revenge.world.items import ITEMS, make_item

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        state = screen.state
        assert state is not None
        state.player.stats.hp = 10

        # An elixir on the floor, under the player.
        state.dungeon_map.add_item(state.player.position, make_item(ITEMS["elixir"]))
        await pilot.press("enter")
        await pilot.pause()
        assert [item.name for item in state.inventory] == ["elixir"]

        await pilot.press("q")
        await pilot.pause()
        assert state.player.hp == state.player.max_hp
        assert state.inventory == []


async def test_enter_does_the_useful_thing_wherever_you_stand():
    """One key, three outcomes, and picking up wins over leaving.

    The order matters more than it looks: if the exit were checked first, an item
    that ever landed on the staircase would be silently abandoned the moment the
    player pressed enter to take it.
    """
    from neverdeads_revenge.game.state import RunState
    from neverdeads_revenge.world.generator import ESCAPE_DEPTH
    from neverdeads_revenge.world.items import ITEMS, make_item

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        state = screen.state
        assert state is not None

        # Nothing here: says so, costs nothing.
        await pilot.press("enter")
        await pilot.pause()
        assert state.log[-1].text == "There is nothing here."
        assert state.depth == 1
        assert state.total_turns == 0

        # On the stairs: goes down.
        state.player.position = state.stairs
        await pilot.press("enter")
        await pilot.pause()
        assert state.depth == 2

        # On an item on the stairs: takes the item, does not leave the floor.
        state.player.position = state.stairs
        state.dungeon_map.add_item(state.stairs, make_item(ITEMS["potion"]))
        depth = state.depth
        await pilot.press("enter")
        await pilot.pause()
        assert [item.name for item in state.inventory] == ["potion"]
        assert state.depth == depth, "enter left the floor with loot still on it"

        # Second press, item gone: now it goes down.
        await pilot.press("enter")
        await pilot.pause()
        assert state.depth == depth + 1
        assert [item.name for item in state.inventory] == ["potion"]

        # On the rift: wins.
        state.build_floor(ESCAPE_DEPTH)
        state.player.position = state.exit_pos
        await pilot.press("enter")
        await pilot.pause()
        assert state.run_state is RunState.ESCAPED


async def test_g_is_no_longer_a_key():
    """The old pick-up key is gone, not merely undocumented.

    A key that still works but is not in the help is worse than no key: it is a
    second way to do something, known only to players who read the source.
    """
    from neverdeads_revenge.ui.screens.game import KEY_BINDINGS

    assert "g" not in KEY_BINDINGS
    assert KEY_BINDINGS["enter"] is Action.INTERACT
    assert KEY_BINDINGS["return"] is Action.INTERACT
    assert KEY_BINDINGS["q"] is Action.QUAFF
    assert KEY_BINDINGS["i"] is Action.INVENTORY


# -- winning ----------------------------------------------------------------
async def test_stepping_into_the_rift_shows_victory_not_death():
    """The ending the whole run exists for, end to end through the UI."""
    from neverdeads_revenge.ui.screens.game_over import GameOverScreen
    from neverdeads_revenge.world.generator import ESCAPE_DEPTH

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        state = screen.state
        assert state is not None

        state.build_floor(ESCAPE_DEPTH)
        state.player.position = state.exit_pos
        await pilot.press(">")
        await pilot.pause()

        assert isinstance(app.screen, GameOverScreen)
        assert app.screen.won, "the rift ended the run as a death"
        assert "VICTORY" in str(app.screen.query_one("#game-over-title").render())
        assert state.run_state is RunState.ESCAPED

        # And it returns to the title like every other ending.
        await pilot.press(" ")
        await pilot.pause()
        assert isinstance(app.screen, TitleScreen)


async def test_the_rift_does_not_win_the_run_early():
    """Descending on floor 1 must still be a descent, not an escape."""
    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        state = screen.state
        assert state is not None

        state.player.position = state.stairs
        await pilot.press(">")
        await pilot.pause()

        assert state.depth == 2
        assert state.run_state is RunState.PLAYING
        assert isinstance(app.screen, GameScreen)


async def test_the_victory_screen_answers_the_prologue():
    """The premise was that death was denied; the win is the other way out.

    A story that opens on a question and never returns to it is just set
    dressing. This is the one place the game closes the loop.
    """
    from neverdeads_revenge.world.generator import ESCAPE_DEPTH

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        screen.state.build_floor(ESCAPE_DEPTH)
        screen.state.player.position = screen.state.exit_pos
        await pilot.press(">")
        await pilot.pause()

        body = str(app.screen.query_one("#game-over-body").render())
        assert "You were not granted death" in body

        # And the death screen must not say it: it would be a cruel lie there.
        assert "Out of the dark" in body
        await pilot.press(" ")
        await pilot.pause()

        # A death gets the plain summary.
        screen = await drive_to_game(app, pilot)
        screen.state.player.stats.hp = 1
        from neverdeads_revenge.game.actors import ENEMIES, make_enemy
        from neverdeads_revenge.game.actions import Action, perform_action

        enemy = make_enemy(
            ENEMIES["ghoul"],
            (screen.state.player.position[0] + 1, screen.state.player.position[1]),
        )
        screen.state.enemies = [enemy]
        screen.state.turn_queue = type(screen.state.turn_queue)([screen.state.player, enemy])
        screen.state.refresh_vision()
        for _ in range(80):
            if screen.state.over:
                break
            perform_action(screen.state, Action.WAIT)
        screen._game_over(won=False)
        await pilot.pause()

        body = str(app.screen.query_one("#game-over-body").render())
        assert "You were not granted death" not in body
        assert "Floor reached" in body


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


async def test_the_whole_prologue_fits_without_scrolling():
    """The last line of the story is the point of the story, so it must show.

    The pane does not scroll: any key dismisses the screen, so a player who
    needed to scroll could not. That makes the story's length a layout
    constraint, not just an editorial one, and this is the assertion that keeps
    a future line from silently pushing the ending off the bottom.
    """
    from neverdeads_revenge.ui.screens.prologue import PrologueScreen

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("x")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, PrologueScreen)
        panel = app.screen.query_one("#prologue-screen")
        assert panel.virtual_size.height <= panel.size.height, (
            f"the prologue needs {panel.virtual_size.height} rows and has "
            f"{panel.size.height}: the last line is cut off"
        )


async def test_the_prologue_shows_every_line_of_the_story():
    from neverdeads_revenge.game.prologue import (
        PROLOGUE,
        PROLOGUE_HINT,
        PROLOGUE_TITLE,
    )

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
        for line in (PROLOGUE_TITLE, *PROLOGUE, PROLOGUE_HINT):
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
async def test_legend_lists_every_monster_and_every_draught():
    """The legend is generated from the game data, so it cannot drift.

    Monsters are read from ``actors.py`` and loot from ``items.py`` at render
    time. Adding either without touching the UI has to show up here.
    """
    from neverdeads_revenge.game.actors import ENEMIES, HEROES
    from neverdeads_revenge.ui.widgets.legend import Legend
    from neverdeads_revenge.world.items import ITEMS

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        shown = screen.query_one(Legend).render().plain

        for hero in HEROES.values():
            assert hero.glyph in shown, f"{hero.key} missing from the legend"
        for template in ENEMIES.values():
            assert template.glyph in shown, f"{template.key} missing from legend"
            assert template.name in shown
        for item in ITEMS.values():
            assert item.glyph in shown, f"{item.key} missing from legend"
            assert item.name in shown


async def test_the_terrain_reference_lives_in_the_help_screen():
    """Static terrain is looked up once, so it belongs in the help, not the panel.

    Every row spent on decoration in the always-on legend is a row that can push
    the goal off the bottom of the sidebar.
    """
    from neverdeads_revenge.game.prologue import LEGEND_TERRAIN
    from neverdeads_revenge.ui.screens.help import HelpScreen

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        await pilot.press("?")
        await pilot.pause()

        assert isinstance(app.screen, HelpScreen)
        shown = str(app.screen.query_one("#help-body").render())
        assert "terrain" in shown.lower()
        for tile in LEGEND_TERRAIN:
            assert tile.glyph in shown, f"{tile.name} missing from the help"
            assert tile.description in shown, f"{tile.name} missing from the help"


async def test_the_help_screen_closes_on_any_key():
    """A reference you cannot get out of is a trap, not a reference."""
    from neverdeads_revenge.ui.screens.help import HelpScreen

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        state = screen.state
        assert state is not None

        await pilot.press("?")
        await pilot.pause()
        assert isinstance(app.screen, HelpScreen)

        await pilot.press("q")
        await pilot.pause()
        assert isinstance(app.screen, GameScreen)
        assert state.turn == 0, "closing the help must not cost a turn"
        assert state.inventory == [], "the key was swallowed by the game instead"


async def test_the_help_screen_does_not_clip_its_reference():
    """It scrolls, so a short terminal shows a window rather than losing the end.

    The terrain half was moved out of the legend because the sidebar had no room
    for it. A box that silently cut it off would have been the same problem in a
    different place.
    """
    from neverdeads_revenge.ui.screens.help import HelpScreen

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        await drive_to_game(app, pilot)
        await pilot.press("f1")
        await pilot.pause()

        body = app.screen.query_one("#help-body")
        assert isinstance(app.screen, HelpScreen)
        assert body.size.height >= body.content_size.height or body.is_vertical_scroll_end, (
            "the help body is taller than its box and cannot be scrolled to the end"
        )


async def test_the_legend_does_not_waste_rows_on_decoration():
    """Grass and water have no rules attached, so they need no legend row."""
    from neverdeads_revenge.ui.widgets.legend import Legend
    from neverdeads_revenge.world.tiles import Tile

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        shown = screen.query_one(Legend).render().plain
        assert Tile.GRASS.description not in shown
        assert Tile.WATER.description not in shown


async def test_legend_fits_its_panel_without_wrapping():
    """Every legend line has to fit the panel width.

    A line that wraps pushes the rest of the legend down and quietly truncates
    the terrain half, which is the half a new player needs. Checked across
    depths, because the monster numbers are the part that grows.
    """
    from neverdeads_revenge.game.prologue import legend_rows
    from neverdeads_revenge.ui.widgets.legend import (
        SIDEBAR_CHROME,
        PANEL_WIDTH,
        USABLE_WIDTH,
    )

    assert USABLE_WIDTH == PANEL_WIDTH - SIDEBAR_CHROME - 1, "border, padding, indent"
    for depth in range(1, 20):
        for glyph, meaning in legend_rows(depth):
            # 2 columns for the glyph and its trailing space, 1 for the indent
            # on a continuation line.
            line = len(meaning) + (2 if glyph else 1)
            assert line <= USABLE_WIDTH, (
                f"legend line too long at floor {depth} ({line}): {glyph} {meaning}"
            )


async def test_legend_shows_monster_numbers():
    """Health, damage and pace are what a player needs mid-fight."""
    from neverdeads_revenge.game.actors import ENEMIES
    from neverdeads_revenge.ui.widgets.legend import Legend

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        shown = screen.query_one(Legend).render().plain

        ghoul = ENEMIES["ghoul"]
        assert f"{ghoul.stats.max_hp}hp" in shown
        low, high = ghoul.stats.damage
        assert f"{low}-{high}d" in shown
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
        assert f"{first[0]}-{first[1]}d" in legend.render().plain

        state.build_floor(8)
        await pilot.press(".")
        await pilot.pause()

        assert legend.depth == 8
        deep = scale_template(ENEMIES["ghoul"], 8).stats.damage
        assert deep != first, "the test is not looking at a floor that scales"
        shown = legend.render().plain
        assert f"{deep[0]}-{deep[1]}d" in shown
        assert f"{first[0]}-{first[1]}d" not in shown


async def test_the_whole_legend_fits_the_sidebar_without_being_cut_off():
    """The panel is clipped, not scrolled, so every line has to fit.

    This is the failure that is invisible in a unit test and obvious to a player:
    the loot and the goal live at the bottom of the panel, and they are exactly
    what falls off the screen first. Checked with REVENGE active, because that is
    when the HUD above the legend is at its tallest.
    """
    from neverdeads_revenge.ui.widgets.legend import Legend

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        state = screen.state
        assert state is not None

        # The worst case: five stacks of REVENGE add two lines to the HUD.
        state.revenge_stacks = 5
        await pilot.press(".")
        await pilot.pause()

        legend = screen.query_one(Legend)
        lines = str(legend.render()).splitlines()
        assert legend.content_size.height >= len(lines), (
            f"legend needs {len(lines)} rows, the sidebar gives it "
            f"{legend.content_size.height}: the bottom of the panel is cut off"
        )


async def test_every_hud_line_fits_the_sidebar_without_wrapping():
    """A wrapped HUD line eats a legend row and pushes the goal off the bottom.

    The sidebar does not scroll, so the two panels are competing for a fixed
    number of rows, and a line that silently wraps costs both of them.
    """
    from neverdeads_revenge.ui.widgets.hud import Hud

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        state = screen.state
        assert state is not None

        # Longest realistic state: a speed bonus, five stacks, a full score.
        state.player.speed_bonus = 1.5
        state.revenge_stacks = 5
        state.kills = 99
        state.total_turns = 9999
        await pilot.press(".")
        await pilot.pause()

        hud = screen.query_one(Hud)
        width = hud.content_size.width
        for line in str(hud.render()).splitlines():
            assert len(line) <= width, f"HUD line wraps ({len(line)}>{width}): {line!r}"


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