"""Autoplay tests.

A roguelite is a turn loop with a lot of state, and the interesting bugs live in
the seams: an enemy that kills the player mid-frame, a descent that rebuilds the
map while a monster still stands on it, a log line referencing a removed actor.

Rather than assert on each of those separately, these tests let a bot play long,
deterministic runs and assert only that the app stays alive and coherent. Seeds
are fixed, so a failure is reproducible.
"""

from __future__ import annotations

import random

import pytest

from neverdeads_revenge.game.state import RunState
from neverdeads_revenge.ui.app import NeverdeadsRevenge
from neverdeads_revenge.ui.screens.game import GameScreen
from neverdeads_revenge.ui.screens.game_over import GameOverScreen
from neverdeads_revenge.ui.screens.title import TitleScreen
from neverdeads_revenge.world.tiles import Tile

from .test_ui import drive_to_game

SIZE = (100, 34)

MOVEMENT_KEYS = ["w", "a", "s", "d", "h", "j", "k", "l", "y", "u", "b", "n"]


async def autoplay(pilot, state, turns: int, seed: int, descend_every: int = 40) -> None:
    """Press keys at random for a while, pausing so the app can process them."""
    rng = random.Random(seed)
    for turn in range(turns):
        roll = rng.random()
        if roll < 0.06:
            key = "."
        elif roll < 0.10:
            key = "g"
        elif roll < 0.13:
            key = "q"
        elif roll < 0.15:
            key = "i"
        elif roll < 0.19:
            key = ">"
        elif roll < 0.21:
            key = "?"
        else:
            key = rng.choice(MOVEMENT_KEYS)

        await pilot.press(key)
        await pilot.pause()

        if state.run_state is not RunState.PLAYING:
            break
        if descend_every and turn and turn % descend_every == 0:
            # Stand on the stairs and take them, to exercise floor changes. Only
            # where there are stairs: the last floor holds a rift instead, and
            # taking that would end the run the test is trying to prolong.
            found = state.dungeon_map.find_tile(Tile.STAIRS_DOWN)
            if found:
                state.player.position = found[0]
                await pilot.press(">")
                await pilot.pause()


def assert_coherent(state) -> None:
    """Invariants that must hold no matter what the bot did."""
    player = state.player
    assert state.dungeon_map.tile_at(player.position).blocks_movement is False
    assert len(state.enemies) == len([e for e in state.enemies if e.alive])
    for enemy in state.enemies:
        if enemy.alive:
            assert not state.dungeon_map.tile_at(
                enemy.position
            ).blocks_movement, "a live monster is standing inside a wall"
            assert enemy.position != player.position, "two actors share a cell"
    if state.run_state is RunState.PLAYING:
        assert player.stats.hp > 0
    # Whatever the bot picked up, it is still holding it.
    for item in state.inventory:
        assert item.heal >= 0
    assert state.turn >= 0
    assert state.depth >= 1


async def test_a_bot_that_escapes_finishes_the_run_cleanly():
    """The victory path has to survive the same invariants as the death path.

    An escape leaves the map in a state no other ending produces -- a live
    player and a live floor under a finished run -- so it gets its own pass.
    """
    from neverdeads_revenge.world.generator import ESCAPE_DEPTH

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        state = screen.state
        assert state is not None

        state.build_floor(ESCAPE_DEPTH)
        assert state.at_the_rift is False, "the player spawns away from the rift"
        state.player.position = state.exit_pos
        assert state.at_the_rift

        # Drink whatever is carried first, to exercise the quaff path in a real
        # frame and make sure a win mid-turn is not mistaken for a death.
        await pilot.press("q")
        await pilot.pause()
        await pilot.press(">")
        await pilot.pause()

        assert state.run_state is RunState.ESCAPED
        assert isinstance(app.screen, GameOverScreen)
        assert app.screen.won
        assert getattr(app, "_exception", None) is None
        assert state.player.alive, "escaping must not kill the hero"
        assert_coherent(state)


async def test_a_won_run_can_be_restarted():
    """The title screen has to be reachable from a victory, not just a death."""
    from neverdeads_revenge.world.generator import ESCAPE_DEPTH

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        screen.state.build_floor(ESCAPE_DEPTH)
        screen.state.player.position = screen.state.exit_pos
        await pilot.press(">")
        await pilot.pause()
        await pilot.press(" ")
        await pilot.pause()

        assert isinstance(app.screen, TitleScreen)
        await pilot.press("x")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, GameScreen)


@pytest.mark.parametrize("seed", [1, 7, 99])
async def test_random_play_never_crashes(seed):
    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        state = screen.state
        assert state is not None

        await autoplay(pilot, state, turns=120, seed=seed)

        assert getattr(app, "_exception", None) is None
        assert_coherent(state)


async def test_descending_rebuilds_the_floor():
    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        state = screen.state
        assert state is not None

        before_depth = state.depth
        before_player = state.player.position
        for _ in range(5):
            await pilot.press(".")
            await pilot.pause()
        assert state.turn == 5

        stairs = state.dungeon_map.find_tile(Tile.STAIRS_DOWN)
        assert stairs, "floor 1 must contain stairs"
        state.player.position = stairs[0]

        await pilot.press(">")
        await pilot.pause()

        assert state.depth == before_depth + 1
        assert state.player.position != before_player
        assert state.floors_cleared == 1
        assert state.revenge_stacks == 0, "REVENGE lapses on a new floor"
        assert state.enemies, "a new floor has monsters"
        assert state.turn == 0, "the per-floor clock restarts"
        assert state.total_turns == 5, "but the run total keeps counting"
        assert_coherent(state)


@pytest.mark.parametrize("key", [">", "enter", "return"])
async def test_every_descend_key_works(key):
    """All three ways down must reach the next floor.

    ``>`` is for players who know the game; ``enter`` and ``return`` are what
    most people press when standing on something they want to use.
    """
    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        state = screen.state
        assert state is not None

        before = state.depth
        state.player.position = state.dungeon_map.find_tile(Tile.STAIRS_DOWN)[0]
        await pilot.press(key)
        await pilot.pause()

        assert state.depth == before + 1


async def test_descend_keys_do_nothing_away_from_the_stairs():
    """Standing next to the staircase, ``enter`` must not teleport you down.

    Otherwise ``enter`` becomes a no-cost descent trigger wherever the stairs
    happen to be on screen.
    """
    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        state = screen.state
        assert state is not None

        stairs = state.dungeon_map.find_tile(Tile.STAIRS_DOWN)[0]
        beside = (stairs[0] + 1, stairs[1])
        state.player.position = beside
        assert not state.on_stairs

        before = state.depth
        for key in ("enter", "return", ">"):
            await pilot.press(key)
            await pilot.pause()
            assert state.depth == before
            assert state.player.position == beside

        assert state.log[-1].text == "There are no stairs here."
        assert state.total_turns == 0, "a refused descent costs no turn"


async def test_waiting_does_not_kill_an_untouched_player():
    """A bot that only waits must survive: enemies cannot act unseen."""
    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        state = screen.state
        assert state is not None

        start_hp = state.player.stats.hp
        for _ in range(30):
            await pilot.press(".")
            await pilot.pause()

        assert state.player.stats.hp == start_hp
        assert state.turn == 30


async def test_killing_a_monster_stacks_revenge():
    """The trait that defines the hero has to actually fire in a real run."""
    from neverdeads_revenge.game.actors import ENEMIES, make_enemy

    app = NeverdeadsRevenge()
    async with app.run_test(size=SIZE) as pilot:
        screen = await drive_to_game(app, pilot)
        state = screen.state
        assert state is not None

        # Put a monster next to the player and let the bot find it.
        enemy = make_enemy(ENEMIES["ghoul"], (state.player.position[0] + 1, state.player.position[1]))
        state.enemies = [enemy]
        state.turn_queue = type(state.turn_queue)([state.player, enemy])
        state.refresh_vision()

        base_speed = state.player.speed
        for _ in range(60):
            if not enemy.alive:
                break
            await pilot.press("d")
            await pilot.pause()

        assert not enemy.alive, "the bot failed to land a hit in 60 tries"
        assert state.kills == 1
        assert state.revenge_stacks == 1
        assert state.player.speed_bonus == pytest.approx(0.3)
        assert state.player.speed > base_speed