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
from neverdeads_revenge.world.tiles import Tile

from .test_ui import drive_to_game

SIZE = (100, 34)

MOVEMENT_KEYS = ["w", "a", "s", "d", "h", "j", "k", "l", "y", "u", "b", "n"]


async def autoplay(pilot, state, turns: int, seed: int, descend_every: int = 40) -> None:
    """Press keys at random for a while, pausing so the app can process them."""
    rng = random.Random(seed)
    for turn in range(turns):
        roll = rng.random()
        if roll < 0.08:
            key = "."
        elif roll < 0.14:
            key = "g"
        elif roll < 0.18:
            key = ">"
        elif roll < 0.20:
            key = "?"
        else:
            key = rng.choice(MOVEMENT_KEYS)

        await pilot.press(key)
        await pilot.pause()

        if state.run_state is not RunState.PLAYING:
            break
        if descend_every and turn and turn % descend_every == 0:
            # Stand on the stairs and take them, to exercise floor changes.
            state.player.position = state.dungeon_map.find_tile(Tile.STAIRS_DOWN)[0]
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
    assert state.turn >= 0
    assert state.depth >= 1


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
        assert state.revenge_stacks == 0, "REVENGE lapses on a new floor"
        assert state.enemies, "a new floor has monsters"
        assert state.turn == 0, "the per-floor clock restarts"
        assert state.total_turns == 5, "but the run total keeps counting"
        assert_coherent(state)


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