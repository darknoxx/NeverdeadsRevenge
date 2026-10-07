"""Tests for the Textual layer.

These drive the real app through :meth:`App.run_test`, so they cover wiring that
unit tests cannot: that screens are registered, that keys reach the game, and
that the screen stack flows title -> hero select -> game -> game over -> title.

No test here reaches into private widget internals beyond ``query_one``; the
point is the flow, not the layout.
"""

from __future__ import annotations

import asyncio
import time

from pathlib import Path

import pytest

from neverdeads_revenge.game import actors as actors_module
from neverdeads_revenge.game.actions import Action
from neverdeads_revenge.game.state import RunState
from neverdeads_revenge.ui.app import NeverdeadsRevenge
from neverdeads_revenge.ui.hold import BAR_CELLS, HoldToContinue
from neverdeads_revenge.ui.screens.game import GameScreen
from neverdeads_revenge.ui.screens.game_over import GameOverScreen
from neverdeads_revenge.ui.screens.hero_select import FUTURE_HEROES, HeroSelectScreen
from neverdeads_revenge.ui.screens.name_entry import clean_name
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
        await hold_enter(pilot)

    assert isinstance(app.screen, GameScreen)
    return app.screen


async def hold_enter(pilot, gap: float = 0.3) -> None:
    """Do the hold-to-continue gesture the way a test can.

    The pilot sends one key event per press and never a repeat, so the held-key
    route cannot fire here. Three presses take the fallback route instead -- a
    path a real player on a terminal without key repeat uses, not a hook
    invented for the tests.

    Three taps, each after a real pause: that is what the fallback route asks
    for, and it is a path a real player on a terminal without key repeat uses
    rather than a hook invented for the tests.
    """
    for _ in range(3):
        await pilot.press("enter")
        await asyncio.sleep(gap)
    await pilot.pause()


async def finish_run(pilot) -> None:
    """Walk a finished run to the title.

    Every ending goes through two screens now: the summary says what happened,
    the name entry is what puts it on the board. Tests that only care about
    being back at the title use this rather than spelling out both.
    """
    await hold_enter(pilot)  # summary -> name entry
    await pilot.press("enter")  # keep the name (prefilled or empty)
    await pilot.pause()


async def drive_to_game_as(app: NeverdeadsRevenge, pilot, hero_key: str) -> GameScreen:
    """Same, but choosing a specific hero off the roster.

    Separate from :func:`drive_to_game` because most tests do not care who they
    are playing, and only the roster tests do.
    """
    from neverdeads_revenge.game.actors import HEROES

    await pilot.pause()
    assert isinstance(app.screen, TitleScreen)

    await pilot.press("x")
    await pilot.pause()
    screen = app.screen
    assert isinstance(screen, HeroSelectScreen)

    while screen.current is not None and screen.current.key != hero_key:
        await pilot.press("right")
        await pilot.pause()
    assert screen.current is not None, f"the roster has no {hero_key}"

    await pilot.press("enter")
    await pilot.pause()
    if isinstance(app.screen, PrologueScreen):
        await hold_enter(pilot)

    assert isinstance(app.screen, GameScreen)
    assert app.screen.state.hero is HEROES[hero_key]
    return app.screen


async def test_legend_lists_the_rift_and_the_loot():
    """The way out and every kind of loot have to be in the panel too.

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
            if item.kind == "draught":
                assert f"heals {item.heal}" in shown
        assert GOAL_HINT in shown, "the goal is not stated anywhere on screen"


async def test_the_legend_says_a_weapon_is_a_weapon():
    """Equipment is listed as a kind, not one row per blade.

    Eight items by name would push the way out off the bottom of a panel that is
    clipped rather than scrolled, and a player only needs to know what the
    glyph means before they have stepped on it.
    """
    from neverdeads_revenge.ui.widgets.legend import Legend
    from neverdeads_revenge.world.items import ITEMS

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        shown = screen.query_one(Legend).render().plain

        weapons = [i for i in ITEMS.values() if i.kind == "weapon"]
        assert len(weapons) > 1, "this test is pointless with one weapon"
        assert "weapon" in shown
        for weapon in weapons:
            assert weapon.name not in shown, (
                f"{weapon.name!r} is listed by name; equipment is grouped"
            )


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

        # And it returns to the title like every other ending -- through the
        # name entry, which every ending goes through now.
        await finish_run(pilot)
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
        await finish_run(pilot)

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


# -- title ------------------------------------------------------------------
def test_the_title_font_can_spell_the_whole_name():
    """Every character of the name has a glyph.

    A title that quietly drops a letter is the failure mode this file was
    rewritten to fix, so the alphabet it needs is asserted rather than assumed.
    """
    from neverdeads_revenge.ui.blocks import BLOCK

    for char in "NEVERDEAD'S REVENGE":
        if char == " ":
            continue
        assert char in BLOCK, f"the title font has no glyph for {char!r}"


def test_every_title_glyph_is_the_same_height():
    """Ragged glyphs would make the block art shear on its baseline."""
    from neverdeads_revenge.ui.blocks import BLOCK, ROWS

    for char, glyph in BLOCK.items():
        assert len(glyph) == ROWS, f"{char!r} is {len(glyph)} rows, not {ROWS}"
        assert all(isinstance(row, str) for row in glyph), char


def test_rendering_a_word_lines_the_glyphs_up():
    """One string per row, all the same width -- that is what makes it a block."""
    from neverdeads_revenge.ui.blocks import ROWS, render_word

    rows = render_word("NEVERDEAD")
    assert len(rows) == ROWS
    assert len(set(map(len, rows))) == 1, "the block art is not square"


def test_the_title_art_is_solid_blocks_and_nothing_else():
    """The old art's problem was `_|/\\`, not its size.

    Anything other than blocks and spaces in here is a character that turns
    letterforms into noise at five rows.
    """
    from neverdeads_revenge.ui.screens.title import TITLE_ART

    assert set(TITLE_ART) <= {"█", " ", "\n"}, "the title uses non-block characters"


def test_unknown_characters_are_skipped_rather_than_crashing():
    """A font that raises on an unknown letter takes the title screen with it."""
    from neverdeads_revenge.ui.blocks import render_word

    assert render_word("N?E") == render_word("NE")
    assert render_word("123") == []
    assert render_word("") == []


async def test_the_title_screen_draws_the_block_art_when_it_fits():
    from neverdeads_revenge.ui.screens.title import TITLE_ART

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, TitleScreen)
        shown = str(app.screen.query_one("#title-art").render())
        assert shown == TITLE_ART
        assert "█" in shown


async def test_the_title_falls_back_to_plain_text_when_it_is_too_narrow():
    """A wrapped block font is less readable than no block font.

    This is the exact complaint the rewrite answers, so the screen is checked at
    a width that cannot hold the art rather than only at the size it was
    designed for.
    """
    from neverdeads_revenge.ui.screens.title import ART_MIN_WIDTH, PLAIN_TITLE

    app = NeverdeadsRevenge()
    async with app.run_test(size=(ART_MIN_WIDTH - 8, 16)) as pilot:
        await pilot.pause()
        shown = str(app.screen.query_one("#title-art").render())
        assert shown == PLAIN_TITLE
        assert "█" not in shown
        # The name is still readable, just smaller.
        assert "N E V E R D E A D ' S" in shown
        assert "R E V E N G E" in shown


async def test_the_title_becomes_the_block_art_when_the_terminal_grows():
    """Width is not fixed at start-up: a resize has to redraw it."""
    from neverdeads_revenge.ui.screens.title import ART_MIN_WIDTH, PLAIN_TITLE, TITLE_ART

    app = NeverdeadsRevenge()
    async with app.run_test(size=(ART_MIN_WIDTH - 8, 16)) as pilot:
        await pilot.pause()
        assert str(app.screen.query_one("#title-art").render()) == PLAIN_TITLE

        await pilot.resize_terminal(ART_MIN_WIDTH + 20, 24)
        await pilot.pause()
        assert str(app.screen.query_one("#title-art").render()) == TITLE_ART


async def test_the_character_screen_shows_every_stat():
    """The sidebar has no room for the whole sheet, so this is where it lives."""
    from neverdeads_revenge.ui.screens.character import CharacterScreen

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        await pilot.press("c")
        await pilot.pause()

        assert isinstance(app.screen, CharacterScreen)
        sheet = str(app.screen.query_one("#character-body").render())
        for label in (
            "health",
            "speed",
            "damage",
            "crit",
            "accuracy",
            "evasion",
            "armour",
            "weapon",
            "armour",
            "carried",
        ):
            assert label in sheet, f"{label} missing from the character sheet"


async def test_the_character_screen_lists_what_is_worn_and_what_it_does():
    """A number that moved without saying why is not much better than no number."""
    from neverdeads_revenge.ui.screens.character import CharacterScreen
    from neverdeads_revenge.world.items import ITEMS, make_item

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        screen.state.player.equipment["weapon"] = make_item(ITEMS["bite"])
        await pilot.press("c")
        await pilot.pause()

        sheet = str(app.screen.query_one("#character-body").render())
        assert "the grey bite" in sheet
        # Derived from the item, so rebalancing it does not fail this.
        for change in ITEMS["bite"].modifiers.describe():
            assert change in sheet, f"{change!r} is not shown on the sheet"


async def test_the_character_screen_costs_no_turn_and_closes():
    from neverdeads_revenge.ui.screens.character import CharacterScreen

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        state = screen.state
        assert state is not None

        await pilot.press("c")
        await pilot.pause()
        assert isinstance(app.screen, CharacterScreen)

        await pilot.press("q")
        await pilot.pause()
        assert isinstance(app.screen, GameScreen)
        assert state.turn == 0, "looking at the sheet cost a turn"
        assert state.inventory == [], "the key was swallowed by the game"


async def test_the_character_screen_labels_do_not_run_into_their_values():
    """Aligned columns, checked rather than eyeballed.

    "accuracy" is eight characters, so a seven-or-eight-wide column puts the
    value straight against the label and the sheet reads as one long word.
    """
    from rich.text import Text

    from neverdeads_revenge.ui.screens.character import _row

    for label in ("health", "speed", "damage", "crit", "accuracy", "evasion", "armour"):
        plain = Text.from_markup(_row(label, "1")).plain
        assert plain.endswith(" 1"), f"{label!r} runs into its value: {plain!r}"


# -- chests -----------------------------------------------------------------
async def test_the_chest_dialog_shows_the_price_and_hides_the_reward():
    """The reward stays behind the lid, so the decision is daring, not sums."""
    from neverdeads_revenge.game.curses import CURSES
    from neverdeads_revenge.ui.screens.chest import ChestScreen
    from neverdeads_revenge.world.items import ITEMS, make_chest

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        screen.state.dungeon_map.add_item(
            screen.state.player.position, make_chest("dim", ITEMS["warden"])
        )
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, ChestScreen)
        body = str(app.screen.query_one("#chest-body").render())
        assert CURSES["dim"].price in body
        assert "warden" not in body and "plate" not in body


async def test_saying_yes_opens_the_chest():
    from neverdeads_revenge.ui.screens.chest import ChestScreen
    from neverdeads_revenge.world.items import ITEMS, make_chest

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        state = screen.state
        state.dungeon_map.add_item(state.player.position, make_chest("dim", ITEMS["warden"]))

        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, ChestScreen)

        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, GameScreen)
        assert [c.key for c in state.curses] == ["dim"]
        assert state.player.equipment["armour"].name == "warden plate"
        assert state.sight_radius == 5, "the price was not paid"


async def test_walking_away_costs_nothing():
    """Declining has to be free, or it is not a choice."""
    from neverdeads_revenge.world.items import ITEMS, make_chest

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        state = screen.state
        chest = make_chest("wither", ITEMS["edge"])
        state.dungeon_map.add_item(state.player.position, chest)

        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

        assert isinstance(app.screen, GameScreen)
        assert state.curses == []
        assert state.player.max_hp == actors_module.NOXX.stats.max_hp
        assert state.total_turns == 0, "the question cost a turn"
        assert state.dungeon_map.item_at(state.player.position) is chest, (
            "the chest vanished when it was declined"
        )


async def test_the_legend_lists_the_chest():
    from neverdeads_revenge.ui.widgets.legend import Legend
    from neverdeads_revenge.world.items import CHEST_GLYPH

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        shown = screen.query_one(Legend).render().plain
        assert CHEST_GLYPH in shown
        assert "chest" in shown


async def test_the_character_sheet_lists_what_has_been_done_to_you():
    from neverdeads_revenge.game.curses import CURSES
    from neverdeads_revenge.ui.screens.character import CharacterScreen

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        screen.state.add_curse(CURSES["bleed"])
        await pilot.press("c")
        await pilot.pause()

        assert isinstance(app.screen, CharacterScreen)
        sheet = str(app.screen.query_one("#character-body").render())
        assert "curses" in sheet
        assert "BLEED" in sheet
        assert CURSES["bleed"].price in sheet, "the price is not spelled out"


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

        await hold_enter(pilot)
        assert isinstance(app.screen, GameScreen)

        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("q")
        await pilot.pause()
        assert isinstance(app.screen, TitleScreen)

        await pilot.press("x")
        await pilot.pause()
        await hold_enter(pilot)
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

        await hold_enter(pilot)
        assert isinstance(app.screen, GameScreen)


async def test_the_whole_prologue_fits_without_scrolling():
    """The last line of the story is the point of the story, so it must show.

    It scrolls now, so a long story is no longer unreadable -- but a story that
    fits is still better than one that has to be scrolled, and this keeps a
    future line from quietly pushing the ending out of sight.
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


async def test_the_prologue_takes_a_held_enter_and_not_a_stray_key():
    """It used to close on any key, which cost the player the only prose here.

    Now the arrows scroll it and only a held enter lets it go -- so a keypress
    that was meant for something else cannot throw the story away.
    """
    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("x")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, PrologueScreen)

        # A stray key does nothing at all.
        for key in ("q", "a", "space", "escape"):
            await pilot.press(key)
            await pilot.pause()
            assert isinstance(app.screen, PrologueScreen), f"{key} closed it"

        # One enter is not enough either.
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, PrologueScreen), "a single press closed it"

        await hold_enter(pilot)
        assert isinstance(app.screen, GameScreen)


async def test_the_prologue_scrolls_with_the_arrows():
    """The story does not fit every terminal, so it has to be scrollable.

    And the keys that scroll it must not be the keys that close it, or the only
    way to read the end of it is to skip it.
    """
    from textual.containers import VerticalScroll

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("x")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, PrologueScreen)

        scroller = app.screen.query_one("#prologue-screen", VerticalScroll)
        # Force it scrollable, so the test does not depend on the terminal being
        # small enough to overflow.
        scroller.styles.max_height = 5
        await pilot.pause()
        scroller.scroll_home()
        await pilot.pause()

        await pilot.press("down")
        await pilot.pause()
        assert scroller.scroll_offset.y > 0, "the down arrow did not scroll"
        assert isinstance(app.screen, PrologueScreen), "scrolling closed the screen"





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


async def test_the_hud_names_what_revenge_is_granting():
    """``REVENGE x3`` means a different number on each hero.

    Without the grant named, three heroes share a status line that tells the
    player nothing about their own run.
    """
    from neverdeads_revenge.game.actors import HEROES
    from neverdeads_revenge.game.combat import apply_revenge
    from neverdeads_revenge.ui.widgets.hud import Hud

    for key, hero in HEROES.items():
        app = NeverdeadsRevenge()
        async with app.run_test(size=SIZE) as pilot:
            screen = await drive_to_game_as(app, pilot, key)
            state = screen.state
            state.revenge_stacks = apply_revenge(state.player, hero.trait.cap)
            await pilot.press(".")
            await pilot.pause()

            shown = screen.query_one(Hud).render().plain
            assert f"REVENGE x{hero.trait.cap}" in shown, key
            assert hero.trait.describe(hero.trait.cap) in shown, key
            # And not the other heroes' grants.
            for other in HEROES.values():
                if other.trait is hero.trait:
                    continue
                assert other.trait.describe(other.trait.cap) not in shown, (
                    f"{key} is shown with {other.key}'s grant"
                )


async def test_the_hero_select_screen_shows_each_trait():
    """The trait is the difference between three stat lines and three characters."""
    from neverdeads_revenge.game.actors import HEROES
    from neverdeads_revenge.ui.screens.hero_select import HeroSelectScreen

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("x")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, HeroSelectScreen)

        for _ in range(len(HEROES)):
            hero = screen.current
            assert hero is not None
            stats = str(screen.query_one("#hero-stats").render())
            assert "revenge" in stats
            assert hero.trait.label in stats, hero.key
            await pilot.press("right")
            await pilot.pause()


# -- hero select -------------------------------------------------------------
async def test_hero_select_cycles_into_locked_slots():
    """Every real hero first, then the locked slots, and locked ones do nothing.

    Cycled rather than hardcoded to "one press right" so the test keeps meaning
    something when the roster grows, which it already has once.
    """
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

        # Walk forward to the first locked slot.
        for _ in range(len(actors_module.HEROES)):
            assert screen.current is not None
            await pilot.press("right")
            await pilot.pause()
        assert screen.current is None, "the roster did not reach a locked slot"

        # A locked slot must not start a run.
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, HeroSelectScreen)


async def test_every_hero_can_actually_start_a_run():
    """The select screen is data-driven, so each entry has to be playable.

    A hero in the registry that the screen cannot start is worse than a missing
    one: it is visible, selectable and does nothing.
    """
    for key in actors_module.HEROES:
        app = NeverdeadsRevenge()
        async with app.run_test(size=SIZE) as pilot:
            screen = await drive_to_game_as(app, pilot, key)
            assert screen.state.hero.key == key


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

        await finish_run(pilot)
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

        # The "you" row is the hero who is playing, and only that one: the panel
        # has one row for the player, not one per entry in the roster.
        playing = screen.state.hero
        assert playing.glyph in shown
        for other in HEROES.values():
            if other.key != playing.key:
                assert other.glyph not in shown, (
                    f"{other.key} is in the legend but is not the one playing"
                )
        for template in ENEMIES.values():
            assert template.glyph in shown, f"{template.key} missing from legend"
            assert template.name in shown

        # Every glyph is listed, but not every item by name: equipment is
        # grouped by kind, because the sidebar has room for "a weapon" and not
        # for four of them by name. Draughts keep a row each -- the difference
        # between a potion and an elixir is the decision being made.
        for item in ITEMS.values():
            assert item.glyph in shown, f"{item.key} missing from legend"
            if item.kind == "draught":
                assert item.name in shown, f"{item.key} missing from legend"


async def test_the_legend_names_the_hero_you_actually_picked():
    """The "you" row has to follow the roster, not the first entry in it.

    Written because it did exactly the wrong thing: with three heroes the panel
    still said ``N you`` while you were playing Yeti.
    """
    from neverdeads_revenge.game.actors import HEROES
    from neverdeads_revenge.ui.widgets.legend import Legend

    for key in HEROES:
        app = NeverdeadsRevenge()
        async with app.run_test(size=SIZE) as pilot:
            await drive_to_game_as(app, pilot, key)

            legend = app.screen.query_one(Legend)
            assert legend.hero is not None and legend.hero.key == key
            assert f"{HEROES[key].glyph} you" in legend.render().plain


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
            # Every glyph of the row, its trailing space, and the indent on a
            # continuation line. A row may carry more than one glyph: the
            # wearable kinds share one.
            line = len(meaning) + (len(glyph) + 1 if glyph else 1)
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


async def test_the_sidebar_fits_for_every_hero():
    """Hero names differ in length and the sidebar is a fixed 34 columns.

    Both panels are clipped rather than scrolled, so a name that wraps costs the
    legend a row -- and the row it costs is at the bottom, where the goal is.
    """
    from neverdeads_revenge.game.actors import HEROES
    from neverdeads_revenge.ui.widgets.hud import Hud
    from neverdeads_revenge.ui.widgets.legend import Legend

    for key in HEROES:
        app = NeverdeadsRevenge()
        async with app.run_test(size=SIZE) as pilot:
            screen = await drive_to_game_as(app, pilot, key)
            # The worst case for the sidebar: a speed bonus and a full legend.
            screen.state.player.speed_bonus = 1.5
            screen.state.revenge_stacks = 5
            await pilot.press(".")
            await pilot.pause()

            hud = screen.query_one(Hud)
            width = hud.content_size.width
            for line in str(hud.render()).splitlines():
                assert len(line) <= width, (
                    f"{key}: HUD line wraps ({len(line)}>{width}): {line!r}"
                )

            legend = screen.query_one(Legend)
            lines = str(legend.render()).splitlines()
            assert legend.content_size.height >= len(lines), (
                f"{key}: the legend needs {len(lines)} rows and has "
                f"{legend.content_size.height}"
            )


# -- hold to continue --------------------------------------------------------
def test_holding_a_key_fills_the_bar_and_finishes():
    """A held key keeps sending repeats, and the fill is read off the clock."""
    hold = HoldToContinue(seconds=0.15, reset_after=0.5)
    assert hold.press("enter") is False

    done = False
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and not done:
        time.sleep(0.02)
        done = hold.press("enter")  # what the terminal sends while held

    assert done, "holding the key never completed"
    assert hold.bar() == "█" * BAR_CELLS


def test_letting_go_resets_the_fill():
    """Terminals never report a release; a moment of silence stands in for one."""
    hold = HoldToContinue(seconds=0.5, reset_after=0.05)
    hold.press("enter")
    time.sleep(0.08)

    assert hold.progress == 0.0, "the fill survived the key being let go"


def test_one_press_on_its_own_does_nothing():
    """The whole point: a stray key must not throw the screen away."""
    hold = HoldToContinue(seconds=0.1, reset_after=0.05)
    assert hold.press("enter") is False


def test_three_deliberate_presses_also_work():
    """For terminals with key repeat off, where the bar would never fill."""
    hold = HoldToContinue(seconds=10.0, reset_after=0.05)
    assert hold.press("enter") is False
    time.sleep(0.08)
    assert hold.press("enter") is False
    time.sleep(0.08)
    assert hold.press("enter") is True


def test_a_burst_of_presses_is_not_a_deliberate_one():
    """Mashing is the hold route's business; the fallback must not double-fire."""
    hold = HoldToContinue(seconds=10.0, reset_after=0.05)
    for _ in range(5):
        assert hold.press("enter") is False


def test_a_held_key_never_looks_deliberate():
    """A repeat arrives milliseconds after the last, so its span is nothing."""
    hold = HoldToContinue(seconds=10.0, reset_after=0.5)
    for _ in range(20):
        time.sleep(0.004)
        assert hold.press("enter") is False, "a repeat tripped the fallback"


def test_keys_that_are_not_the_hold_key_are_ignored():
    hold = HoldToContinue()
    for key in ("q", "a", "space", "escape"):
        assert hold.press(key) is False
    assert hold.progress == 0.0


def test_the_bar_is_a_bar():
    hold = HoldToContinue(seconds=0.4, reset_after=0.3)
    assert hold.bar() == "░" * BAR_CELLS

    hold.press("enter")
    time.sleep(0.1)
    bar = hold.bar()
    assert len(bar) == BAR_CELLS
    assert bar != "░" * BAR_CELLS, "the bar did not fill"
    assert "█" in bar


# -- a held key must not carry into the next screen --------------------------
def test_the_app_tells_a_repeat_from_a_new_press():
    """The terminal repeats a held key tens of times a second; nobody presses
    one twice on purpose that fast, so the gap is all it takes."""
    app = NeverdeadsRevenge()

    app.note_key("enter")  # the press that dismissed the last screen
    app.arm_repeat_filter()  # ...and the screen changed

    assert app.note_key("enter") is True, "the repeat right behind it"
    assert app.note_key("enter") is True

    time.sleep(0.2)
    assert app.note_key("enter") is False, "a later press is a new one"

    # And the filter is spent: nothing after the gap is swallowed.
    app.note_key("enter")
    assert app.note_key("enter") is False, "the filter stayed armed"


async def test_a_repeated_enter_does_not_carry_into_the_game():
    """The bug the player hit, in their words: "it should only happen on a new
    keystroke".

    Holding enter to leave the prologue keeps the terminal repeating it, and the
    leftovers used to land on the game screen as interactions -- walking the
    hero around the first room and printing "There is nothing here" until the
    key came up.
    """
    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        state = screen.state
        assert state is not None
        before = len(state.log)

        # Stand in for the terminal still repeating the key the prologue was
        # dismissed with. A test cannot make a terminal hold a key down.
        app.note_key = lambda key: True
        await pilot.press("enter")
        await pilot.pause()

        assert len(state.log) == before, "a repeat acted as a new press"


# -- the high score ----------------------------------------------------------
async def test_a_finished_run_is_written_down():
    """The score outlives the run, which is the point of writing it down."""
    from neverdeads_revenge.persistence import load_meta

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        screen.state.kills = 5
        screen.state.floors_cleared = 3
        screen._game_over()
        await pilot.pause()
        # The run is written down once the name is in, so the summary screen
        # alone does not do it yet.
        await finish_run(pilot)

        assert app.progress.best_score > 0

    # And it is on disk, not just in memory.
    assert load_meta().best_score == app.progress.best_score


async def test_the_best_score_only_ever_goes_up():
    from neverdeads_revenge.persistence import load_meta

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        screen.state.kills = 40
        screen.state.floors_cleared = 9
        screen._game_over()
        await pilot.pause()
        await finish_run(pilot)
        high = app.progress.best_score
        assert high > 0

        # Back to the title already: drive_to_game starts there.
        screen = await drive_to_game(app, pilot)
        screen.state.kills = 1
        screen._game_over()
        await pilot.pause()
        await finish_run(pilot)

        assert app.progress.best_score == high, "a worse run lowered the best"

    assert load_meta().best_score == high


async def test_the_title_screen_shows_the_best_run():
    from neverdeads_revenge.persistence import MetaProgress, save_meta

    save_meta(MetaProgress(best_score=4242))

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, TitleScreen)
        shown = str(app.screen.query_one("#title-best").render())
        assert "4242" in shown


async def test_the_title_screen_says_nothing_before_the_first_run():
    """\"best 0\" on a first launch is a worse welcome than saying nothing."""
    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        assert app.progress.best_score == 0
        assert str(app.screen.query_one("#title-best").render()).strip() == ""


async def test_the_summary_shows_the_best():
    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        screen.state.kills = 7
        screen._game_over()
        await pilot.pause()

        shown = str(app.screen.query_one("#game-over-best").render())
        assert str(app.progress.best_score) in shown


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

# -- the scoreboard and the name ---------------------------------------------
def test_a_name_is_cleaned_before_it_goes_on_the_board():
    """A table with punctuation in it is a table nobody can read."""
    assert clean_name("noxx") == "NOXX"
    assert clean_name("a b!c") == "ABC", "spaces and punctuation are not letters"
    assert clean_name("abcdefgh") == "ABCDE", "five slots, not eight"
    assert clean_name("") == ""
    assert clean_name("123") == "123"


async def test_h_opens_the_scoreboard_from_the_title():
    from neverdeads_revenge.ui.screens.scoreboard import ScoreboardScreen

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, TitleScreen)

        await pilot.press("h")
        await pilot.pause()
        assert isinstance(app.screen, ScoreboardScreen)

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, TitleScreen)


async def test_the_scoreboard_says_so_when_there_is_nothing_on_it():
    from neverdeads_revenge.ui.screens.scoreboard import ScoreboardScreen

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("h")
        await pilot.pause()

        assert isinstance(app.screen, ScoreboardScreen)
        body = str(app.screen.query_one("#scoreboard-body").render())
        assert "No runs yet" in body


async def test_the_scoreboard_lists_a_run_with_how_it_ended():
    from neverdeads_revenge.persistence import MetaProgress, save_meta
    from neverdeads_revenge.ui.screens.scoreboard import ScoreboardScreen

    progress = MetaProgress(gold=99)
    progress.record_run(
        depth=10, score=4200, kills=0, won=True, name="NOXX", hero="noxx"
    )
    progress.record_run(depth=4, score=900, kills=0, won=False, name="YETI", hero="yeti")
    save_meta(progress)

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("h")
        await pilot.pause()

        assert isinstance(app.screen, ScoreboardScreen)
        body = str(app.screen.query_one("#scoreboard-body").render())
        assert "NOXX" in body and "4200" in body
        assert "escaped" in body, "a win is not marked as one"
        assert "YETI" in body and "died" in body
        assert "99" in body, "the banked coin is not shown"


async def test_a_finished_run_asks_for_a_name():
    from neverdeads_revenge.ui.screens.name_entry import NameEntryScreen

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        screen.state.kills = 3
        screen._game_over()
        await pilot.pause()
        assert isinstance(app.screen, GameOverScreen)

        await hold_enter(pilot)
        assert isinstance(app.screen, NameEntryScreen)


async def test_the_name_goes_on_the_board_with_the_score():
    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        screen.state.floors_cleared = 4
        screen.state.total_turns = 0
        expected = screen.state.score

        screen._game_over()
        await pilot.pause()
        await hold_enter(pilot)          # summary -> name entry
        await pilot.press("a")
        await pilot.press("b")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, TitleScreen)
        assert [e.name for e in app.progress.scores] == ["AB"]
        assert app.progress.scores[0].score == expected
        assert app.progress.last_name == "AB"


async def test_a_death_is_recorded_just_like_a_win():
    """Both collected points, so both get a name."""
    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        screen.state.kills = 2
        screen._game_over(won=False)
        await pilot.pause()
        await hold_enter(pilot)
        await pilot.press("enter")
        await pilot.pause()

        assert app.progress.scores, "a losing run was not recorded"
        assert app.progress.scores[0].won is False


async def test_the_name_entry_is_prefilled_with_the_last_name():
    from neverdeads_revenge.persistence import MetaProgress, save_meta
    from neverdeads_revenge.ui.screens.name_entry import NameEntryScreen

    save_meta(MetaProgress(last_name="NXX"))

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        screen._game_over()
        await pilot.pause()
        await hold_enter(pilot)

        assert isinstance(app.screen, NameEntryScreen)
        assert app.screen._name == "NXX", "the last name was not offered"


async def test_an_empty_name_becomes_something_readable():
    from neverdeads_revenge.ui.screens.name_entry import NameEntryScreen

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        screen._game_over()
        await pilot.pause()
        await hold_enter(pilot)

        assert isinstance(app.screen, NameEntryScreen)
        # Nothing typed: enter alone must not leave a blank row on the board.
        await pilot.press("enter")
        await pilot.pause()

        assert app.progress.scores[0].name == "???"


async def test_backspace_takes_a_letter_back():
    from neverdeads_revenge.ui.screens.name_entry import NameEntryScreen

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        screen._game_over()
        await pilot.pause()
        await hold_enter(pilot)
        assert isinstance(app.screen, NameEntryScreen)

        await pilot.press("a")
        await pilot.press("b")
        await pilot.press("backspace")
        await pilot.pause()

        assert app.screen._name == "A"


async def test_the_name_entry_takes_five_letters_and_no_more():
    from neverdeads_revenge.ui.screens.name_entry import NameEntryScreen

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        screen._game_over()
        await pilot.pause()
        await hold_enter(pilot)
        assert isinstance(app.screen, NameEntryScreen)

        for letter in "ABCDEFGH":
            await pilot.press(letter)
        await pilot.pause()

        assert app.screen._name == "ABCDE"


async def test_a_repeated_enter_does_not_type_into_the_name():
    """The same leak as the game screen, one screen later.

    A held enter is still repeating when the name entry appears, and an ``Input``
    would take those as typing. This handles its own keys so it can drop them.
    """
    from neverdeads_revenge.ui.screens.name_entry import NameEntryScreen

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        screen._game_over()
        await pilot.pause()
        await hold_enter(pilot)
        assert isinstance(app.screen, NameEntryScreen)

        before = app.screen._name
        app.note_key = lambda key: True
        await pilot.press("a")
        await pilot.pause()

        assert app.screen._name == before, "a repeat typed a letter"


# -- the shop ----------------------------------------------------------------
async def _open_shop(app, pilot, gold: int):
    """Put coin in the purse and walk to the shop."""
    from neverdeads_revenge.ui.screens.shop import ShopScreen

    app.progress.gold = gold
    await pilot.pause()
    await pilot.press("s")
    await pilot.pause()
    assert isinstance(app.screen, ShopScreen), "s did not open the shop"
    return app.screen


async def test_s_opens_the_shop_from_the_title():
    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, TitleScreen)

        await _open_shop(app, pilot, 100)
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, TitleScreen)


async def test_the_shop_takes_the_coin_and_keeps_the_parcel():
    from neverdeads_revenge.game.shop import SUPPLIES

    price = SUPPLIES[0].price
    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        shop = await _open_shop(app, pilot, price * 4)

        # The first row is the cheapest draught.
        assert shop.offers[shop.index].key == "potion"
        await pilot.press("enter")
        await pilot.pause()

        assert app.progress.gold == price * 3
        assert app.progress.pending == ["potion"]
        assert "potion" in shop.message


async def test_the_shop_says_no_and_charges_nothing():
    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        shop = await _open_shop(app, pilot, 0)

        await pilot.press("enter")
        await pilot.pause()

        assert app.progress.gold == 0
        assert app.progress.pending == []
        assert "coins" in shop.message, "the refusal should mention the price"


async def test_a_maxed_upgrade_says_it_is_already_yours():
    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        app.progress.upgrades["lantern"] = 1
        shop = await _open_shop(app, pilot, 500)

        index = next(i for i, o in enumerate(shop.offers) if o.key == "lantern")
        for _ in range(index):
            await pilot.press("down")
        await pilot.pause()

        assert shop.offers[shop.index].key == "lantern"
        assert shop.offers[shop.index].maxed
        spent = app.progress.gold

        await pilot.press("enter")
        await pilot.pause()
        assert app.progress.gold == spent, "a maxed upgrade took coin anyway"


async def test_a_bought_draught_is_in_the_pack_when_the_run_starts():
    """The whole point of the shop, end to end."""
    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        await _open_shop(app, pilot, 400)
        await pilot.press("enter")  # potion
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

        screen = await drive_to_game(app, pilot)

        assert [item.item_id for item in screen.state.inventory] == ["potion"]
        assert app.progress.pending == [], "the parcel was not taken off the books"


async def test_bought_gear_is_worn_from_the_first_step():
    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        shop = await _open_shop(app, pilot, 400)
        index = next(i for i, o in enumerate(shop.offers) if o.key == "hide")
        for _ in range(index):
            await pilot.press("down")
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

        screen = await drive_to_game(app, pilot)

        assert screen.state.player.equipment["armour"].item_id == "hide"


async def test_an_upgrade_bought_in_the_shop_reaches_the_next_run():
    from neverdeads_revenge.game.shop import META_UPGRADES

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        shop = await _open_shop(app, pilot, 900)
        index = next(i for i, o in enumerate(shop.offers) if o.key == "vigour")
        for _ in range(index):
            await pilot.press("down")
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

        screen = await drive_to_game(app, pilot)

        assert (
            screen.state.player.max_hp
            == screen.hero.stats.max_hp + META_UPGRADES["vigour"].max_hp
        )


async def test_the_shelf_turns_over_after_a_run():
    """Otherwise there is no reason to walk past the shop a second time."""
    from neverdeads_revenge.core.rng import Rng
    from neverdeads_revenge.game.shop import roll_wild_stock

    app = NeverdeadsRevenge(seed=3)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        assert app.progress.wild_stock == roll_wild_stock(Rng(3))

        screen = await drive_to_game(app, pilot)
        screen._game_over()
        await pilot.pause()
        await finish_run(pilot)

        assert app.progress.runs_started == 1
        assert app.progress.wild_stock == roll_wild_stock(Rng(4))


async def test_a_wild_offer_bought_in_the_shop_is_felt_in_the_run():
    app = NeverdeadsRevenge(seed=3)
    async with app.run_test(size=SIZE) as pilot:
        app.progress.wild_stock = ["second_wind", "greed"]
        shop = await _open_shop(app, pilot, 900)

        index = next(i for i, o in enumerate(shop.offers) if o.key == "second_wind")
        for _ in range(index):
            await pilot.press("down")
        await pilot.press("enter")
        await pilot.pause()
        assert app.progress.wilds == ["second_wind"]

        await pilot.press("escape")
        await pilot.pause()
        screen = await drive_to_game(app, pilot)

        assert screen.state.extra_lives == 1


# -- the spring --------------------------------------------------------------
async def _stand_in_a_spring(app, pilot, gold: int, *curses):
    from neverdeads_revenge.game.curses import CURSES
    from neverdeads_revenge.world.tiles import Tile

    screen = await drive_to_game(app, pilot)
    state = screen.state
    state.dungeon_map.set_tile(state.player.position, Tile.SPRING)
    for key in curses:
        state.add_curse(CURSES[key])
    state.gold = gold
    return screen, state


async def test_the_legend_lists_the_spring():
    """The one tile with a rule attached, so it earns a row next to the map."""
    from neverdeads_revenge.ui.widgets.legend import Legend
    from neverdeads_revenge.world.tiles import Tile

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        shown = screen.query_one(Legend).render().plain
        assert Tile.SPRING.glyph in shown
        assert "spring" in shown


async def test_standing_in_a_spring_asks_before_spending_coin():
    from neverdeads_revenge.game.state import CLEANSE_COST
    from neverdeads_revenge.ui.screens.spring import SpringScreen

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen, state = await _stand_in_a_spring(app, pilot, CLEANSE_COST, "heavy")

        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, SpringScreen)
        body = str(app.screen.query_one("#spring-body").render())
        assert str(CLEANSE_COST) in body
        assert state.gold == CLEANSE_COST, "asking must not cost anything yet"


async def test_washing_a_curse_off_in_the_ui():
    from neverdeads_revenge.game.state import CLEANSE_COST

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen, state = await _stand_in_a_spring(app, pilot, 100, "heavy")
        before = state.player.speed

        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert state.gold == 100 - CLEANSE_COST
        assert state.curses == []
        assert state.player.speed > before, "the speed came back"
        assert isinstance(app.screen, GameScreen)


async def test_leaving_the_spring_alone_costs_nothing():
    from neverdeads_revenge.game.state import CLEANSE_COST

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen, state = await _stand_in_a_spring(app, pilot, 100, "heavy")

        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

        assert state.gold == 100
        assert len(state.curses) == 1
        assert isinstance(app.screen, GameScreen)
        assert state.turn == 0, "walking away must not cost a turn"


async def test_a_spring_you_cannot_afford_never_opens_a_dialog():
    """Stating the price beats offering something and then refusing it."""
    from neverdeads_revenge.game.state import CLEANSE_COST

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen, state = await _stand_in_a_spring(
            app, pilot, CLEANSE_COST - 1, "heavy"
        )

        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, GameScreen), "a dialog opened anyway"
        assert str(CLEANSE_COST) in state.log[-1].text


async def test_a_clean_hero_gets_no_dialog_either():
    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen, state = await _stand_in_a_spring(app, pilot, 100)

        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, GameScreen)
        assert "nothing on you" in state.log[-1].text


# -- the hero portrait -------------------------------------------------------
def test_the_font_carries_every_heros_letter():
    """A hero whose letter the font lacks would draw a card with no portrait,
    which is the one thing this screen exists to show."""
    from neverdeads_revenge.game.actors import HEROES
    from neverdeads_revenge.ui.blocks import BLOCK

    for hero in HEROES.values():
        assert hero.glyph in BLOCK, hero.key


def test_the_font_carries_the_letters_the_locked_slots_will_need():
    """Revenant and warden are two dictionary entries away from being real."""
    from neverdeads_revenge.ui.blocks import BLOCK

    for letter in "REVENANTWARDEN":
        assert letter in BLOCK, letter


def test_render_letter_colours_one_character():
    from neverdeads_revenge.ui.blocks import render_letter

    art = render_letter("N", "bold #a855f7")
    assert art.startswith("[bold #a855f7]")
    assert art.endswith("[/]")
    assert "█" in art
    assert render_letter("?") == "", "a letter the font lacks draws nothing"


async def test_the_hero_select_draws_the_hero_letter_in_blocks():
    """The glyph, at the size the title spells its own name in."""
    from neverdeads_revenge.game.actors import HEROES
    from neverdeads_revenge.ui.blocks import render_word

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("x")
        await pilot.pause()

        for _ in range(len(HEROES)):
            hero = app.screen.current
            assert hero is not None
            art = str(app.screen.query_one("#hero-art").render())
            assert [line.rstrip() for line in art.splitlines()] == [
                line.rstrip() for line in render_word(hero.glyph)
            ], hero.key
            await pilot.press("right")
            await pilot.pause()


async def test_the_card_is_the_same_size_on_every_slot():
    """Including the locked ones, which have no stat table to show at all.

    A card that grew and shrank as the player cycled would move the roster --
    the thing they are reading to work out where they are -- under their hands,
    and it would move furthest on the slots with the least to say.
    """
    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("x")
        await pilot.pause()

        seen = set()
        for _ in range(len(actors_module.HEROES) + len(FUTURE_HEROES)):
            card = app.screen.query_one("#hero-card")
            seen.add((card.region.y, card.size.height))
            await pilot.press("right")
            await pilot.pause()

        assert len(seen) == 1, f"the card moves between slots: {seen}"


def test_the_stat_table_is_the_row_count_the_css_pins_it_to():
    """``app.tcss`` gives the widget a fixed height, so a row added to the table
    without one added to the CSS is a row that silently gets clipped."""
    from neverdeads_revenge.game.actors import HEROES
    from neverdeads_revenge.ui.screens.hero_select import STAT_ROWS

    for hero in HEROES.values():
        assert len(HeroSelectScreen._stat_block(hero).splitlines()) == STAT_ROWS, hero.key


async def test_the_hero_prose_and_numbers_start_on_the_same_column():
    """The complaint this rewrite answers: the prose sat against the left wall.

    Both are in one centred card now, so both start on its left edge, and the
    card sits in the middle of the screen rather than at column zero.
    """
    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("x")
        await pilot.pause()

        blurb = app.screen.query_one("#hero-blurb")
        stats = app.screen.query_one("#hero-stats")
        card = app.screen.query_one("#hero-card")

        assert blurb.region.x == stats.region.x, "the prose and the table disagree"
        assert card.region.x > 0, "the card is still against the left wall"
        centre = card.region.x + card.region.width / 2
        assert abs(centre - app.size.width / 2) <= 1, "the card is not centred"


async def test_the_hero_name_is_centred_over_the_numbers():
    from neverdeads_revenge.ui.blocks import ROWS

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("x")
        await pilot.pause()

        art = app.screen.query_one("#hero-art")
        name = app.screen.query_one("#hero-name")
        assert art.size.height == ROWS
        assert art.region.x + art.region.width / 2 == pytest.approx(
            name.region.x + name.region.width / 2, abs=1
        ), "the portrait and the name are not on the same axis"


# -- the shop column ---------------------------------------------------------
async def test_the_shop_column_constants_match_the_panel_it_draws():
    """The fitting test below measures against arithmetic; this checks it.

    The same split the legend uses: one test that the numbers match the real
    widget, one that the catalogue fits the numbers. Without the first, the
    second would happily pass against a panel that no longer exists.
    """
    from neverdeads_revenge.ui.screens.shop import CONTENT_WIDTH

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("s")
        await pilot.pause()

        assert app.screen.query_one("#shop").size.width == CONTENT_WIDTH
        assert app.screen.query_one("#shop-list").size.width == CONTENT_WIDTH


def test_every_wild_offer_fits_the_shop_column():
    """A pitch and a catch each get exactly one line, and the panel is fixed.

    A line that wraps drops its remainder at the left edge of the panel, under
    the cursor and outside the column it belongs to, and reads as a broken row
    rather than as a long sentence. Two of these were over the limit: the pact's
    catch and greed's, both of which wrapped onto a line of their own.
    """
    from neverdeads_revenge.game.shop import WILD_OFFERS
    from neverdeads_revenge.ui.screens.shop import CATCH_WIDTH, PITCH_WIDTH

    for key, offer in WILD_OFFERS.items():
        assert len(offer.pitch) <= PITCH_WIDTH, (
            f"{key}: pitch is {len(offer.pitch)}, the column is {PITCH_WIDTH}"
        )
        assert len(offer.catch) <= CATCH_WIDTH, (
            f"{key}: catch is {len(offer.catch)}, the column is {CATCH_WIDTH}"
        )


def test_every_amulet_blurb_fits_the_shop_column():
    """An amulet's ability is a sentence, and a sentence is easier to write too
    long than a list of numbers is. One already was."""
    from neverdeads_revenge.game.amulets import AMULETS
    from neverdeads_revenge.ui.screens.shop import PITCH_WIDTH

    for key, passive in AMULETS.items():
        assert len(passive.blurb) <= PITCH_WIDTH, (
            f"{key}: the blurb is {len(passive.blurb)}, the column is {PITCH_WIDTH}"
        )


async def test_the_shop_has_a_shelf_for_amulets():
    from neverdeads_revenge.game.amulets import AMULETS
    from neverdeads_revenge.game.shop import AMULETS_FOR_SALE
    from neverdeads_revenge.ui.screens.shop import ShopScreen

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        app.progress.gold = 999
        await pilot.press("s")
        await pilot.pause()

        assert isinstance(app.screen, ShopScreen)
        assert app.screen.query_one("#shop-rows").render()
        shown = {offer.key for offer in app.screen.offers}
        for item in AMULETS_FOR_SALE:
            assert item.key in shown, item.key
        assert set(AMULETS_FOR_SALE[i].key for i in range(len(AMULETS_FOR_SALE))) <= set(
            AMULETS
        )


async def test_the_shop_scrolls_to_whatever_is_selected():
    """Fourteen amulets do not fit a terminal, and a cursor the player cannot
    see is a cursor that is not there."""
    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        app.progress.gold = 999
        await pilot.press("s")
        await pilot.pause()

        for _ in range(len(app.screen.offers) - 1):
            await pilot.press("down")
        await pilot.pause()

        assert app.screen.index == len(app.screen.offers) - 1
        # The last offer is a wild one, at the very bottom of the shelf.
        rows = app.screen.query_one("#shop-rows")
        assert rows.region.y < app.screen.query_one("#shop").size.height


async def test_a_remembered_spring_stays_on_the_map():
    """It is a one-use resource, so it is a place worth remembering the way to.

    It was missing from the list of terrain that stays legible when it is out of
    sight, so a room the player had already found the water in went blank the
    moment they stepped out of it -- and the whole point of the spring is that
    you walk back to it.
    """
    from neverdeads_revenge.ui.widgets.map_view import MapView
    from neverdeads_revenge.world.tiles import Tile

    assert MapView._stays_legible(Tile.SPRING)
    assert MapView._stays_legible(Tile.STAIRS_DOWN)
    assert MapView._stays_legible(Tile.WALL)
    assert not MapView._stays_legible(Tile.FLOOR)


def test_the_terrain_reference_only_lists_terrain_that_exists():
    """A reference that lists a thing no floor contains teaches the player to
    look for something that is not there.

    DOOR is the one: fully specified, transparent on purpose, and never placed
    by the generator. When a floor gets doors, this list gets a door.
    """
    from neverdeads_revenge.game.prologue import LEGEND_TERRAIN
    from neverdeads_revenge.world.tiles import Tile

    assert Tile.DOOR not in LEGEND_TERRAIN
    for tile in LEGEND_TERRAIN:
        assert tile is not Tile.DOOR
