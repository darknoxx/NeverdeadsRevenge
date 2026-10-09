"""Tests for the thing that comes looking for you.

Everything else in the dungeon waits to be walked into, or drifts at the player
once it can see them. The hunter knows where they are from the moment the floor
is built -- which is the whole of what it is, and the thing that has to be
tested: a hunter that only acted when it was visible would be a monster standing
still in the dark.
"""

from __future__ import annotations

from neverdeads_revenge.core.direction import chebyshev
from neverdeads_revenge.core.rng import Rng
from neverdeads_revenge.game.actions import advance_world, take_turn
from neverdeads_revenge.game.actors import ENEMIES, HEROES, NOXX, make_enemy
from neverdeads_revenge.game.state import start_run
from neverdeads_revenge.world.generator import HUNTER_CHANCE, generate_floor


def _far_from_player(state):
    """A walkable cell as far from the player as the floor allows."""
    return max(
        state.dungeon_map.walkable_positions(),
        key=lambda pos: chebyshev(pos, state.player.position),
    )


def _hunter(state):
    """Put a hunter a long way from the player, out of sight."""
    hunter = make_enemy(ENEMIES["hunter"], _far_from_player(state))
    state.enemies = [hunter]
    state.turn_queue = type(state.turn_queue)([hunter])
    return hunter


# -- where it comes from -----------------------------------------------------
def test_the_hunter_never_stands_on_the_first_floor():
    """Floor one is where a player learns what a monster looks like, and the
    first thing they learn should not be something they cannot kill."""
    for seed in range(200):
        floor = generate_floor(Rng(seed), depth=1)
        assert floor.hunter is None


def test_the_hunter_turns_up_about_one_floor_in_ten():
    floors = 400
    found = sum(
        1
        for seed in range(floors)
        if generate_floor(Rng(seed), depth=5).hunter is not None
    )
    assert 0.05 < found / floors < 0.18, found
    assert HUNTER_CHANCE == 0.10


def test_a_hunter_that_turns_up_is_at_the_floor_strength_and_not_floor_one():
    """It is not drawn from the table, so the potency curve has to be applied
    by hand -- and a hunter that skipped it would be a floor-one monster on
    floor nine."""
    from neverdeads_revenge.game.actors import scale_template

    base = ENEMIES["hunter"].stats.max_hp
    seen = 0
    for seed in range(60):
        state = start_run(NOXX, seed=seed)
        state.build_floor(8)
        for hunter in (e for e in state.enemies if e.glyph == "X"):
            seen += 1
            assert hunter.hp == scale_template(ENEMIES["hunter"], 8).stats.max_hp
            assert hunter.hp > base

    assert seen, "no hunter turned up in sixty floors"


# -- what it does ------------------------------------------------------------
def test_it_walks_at_the_player_from_out_of_sight():
    state = start_run(NOXX, seed=3)
    hunter = _hunter(state)
    before = chebyshev(hunter.position, state.player.position)
    assert not state.dungeon_map.is_visible(hunter.position)

    take_turn(state, hunter)

    assert chebyshev(hunter.position, state.player.position) < before, (
        "the hunter did not come"
    )


def test_an_ordinary_monster_still_waits_in_the_dark():
    """The fairness rule is only lifted for the hunter."""
    state = start_run(NOXX, seed=3)
    ghoul = make_enemy(ENEMIES["ghoul"], _far_from_player(state))
    before = ghoul.position

    take_turn(state, ghoul)

    assert ghoul.position == before, "a ghoul hunted from out of sight"


def test_it_is_still_slower_than_the_fastest_hero():
    """The one hard constraint in the balance. A hunter that outran Noxx would
    turn every other stat he has into decoration."""
    for depth in range(1, 12):
        from neverdeads_revenge.game.actors import scale_template

        assert scale_template(ENEMIES["hunter"], depth).stats.speed < NOXX.stats.speed


def test_the_glyph_is_free_and_is_not_a_hero_or_a_monster_letter():
    """``X`` reads as a warning without being any of the letters already on the
    map."""
    taken = {hero.glyph for hero in HEROES.values()}
    taken |= {t.glyph for key, t in ENEMIES.items() if key != "hunter"}
    taken |= {"8"}

    assert ENEMIES["hunter"].glyph == "X"
    assert ENEMIES["hunter"].glyph not in taken


def test_a_floor_with_a_hunter_is_still_winnable_by_leaving():
    """It is a decision, not a wall: it can be left behind on the stairs."""
    state = start_run(NOXX, seed=3)
    hunter = _hunter(state)
    hunter.stats.hp = 9999  # it is not going to be killed

    # Walk the player onto the exit and take it.
    state.player.position = state.exit_pos
    from neverdeads_revenge.game.actions import Action, perform_action

    perform_action(state, Action.DESCEND)

    assert state.depth == 2
    assert all(e.glyph != "X" for e in state.enemies), (
        "the hunter followed through the stairs"
    )
