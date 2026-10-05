"""Tests for tiles, the map container and map generation."""

from __future__ import annotations

import pytest

from neverdeads_revenge.core.direction import Direction
from neverdeads_revenge.core.rng import Rng
from neverdeads_revenge.world.generator import (
    ESCAPE_DEPTH,
    Rect,
    _reachable,
    generate_floor,
)
from neverdeads_revenge.world.map import DungeonMap
from neverdeads_revenge.world.tiles import Tile

SEEDS = range(60)


# -- tiles -----------------------------------------------------------------
def test_walls_block_movement_and_sight():
    assert Tile.WALL.blocks_movement
    assert Tile.WALL.blocks_sight


def test_floor_neither_blocks_movement_nor_sight():
    assert not Tile.FLOOR.blocks_movement
    assert not Tile.FLOOR.blocks_sight


def test_rubble_is_walkable_but_opaque():
    assert not Tile.RUBBLE.blocks_movement
    assert Tile.RUBBLE.blocks_sight


def test_every_tile_has_glyph_colour_and_description():
    for tile in Tile:
        assert len(tile.glyph) == 1
        assert tile.color
        assert tile.background
        assert tile.description


def test_glyphs_are_unique_so_the_map_stays_readable():
    glyphs = [tile.glyph for tile in Tile]
    assert len(set(glyphs)) == len(glyphs)


def test_no_actor_shares_a_glyph_with_anything_else():
    """One glyph, one kind of thing. The map is read at a glance or not at all.

    Per *kind*, not per item: every weapon is a ``)`` and every coat is a ``[``,
    which is the old roguelike convention and costs nothing to follow. What must
    never happen is a weapon looking like a wall.
    """
    from neverdeads_revenge.game.actors import ENEMIES, HEROES
    from neverdeads_revenge.world.items import ITEMS

    meanings: dict[str, set[str]] = {}
    for tile in Tile:
        meanings.setdefault(tile.glyph, set()).add("terrain")
    for hero in HEROES.values():
        meanings.setdefault(hero.glyph, set()).add("hero")
    for template in ENEMIES.values():
        meanings.setdefault(template.glyph, set()).add("monster")
    for item in ITEMS.values():
        meanings.setdefault(item.glyph, set()).add(item.kind)

    clashes = {glyph: kinds for glyph, kinds in meanings.items() if len(kinds) > 1}
    assert not clashes, f"these glyphs mean more than one thing: {clashes}"


def test_equipment_of_a_kind_looks_alike_on_purpose():
    """Every weapon is a ``)`` and every coat is a ``[``.

    Draughts are the deliberate exception: a potion and an elixir look different
    because the difference between them is the decision -- do I spend the small
    one or the big one. A weapon is a weapon, and which blade it is belongs on
    the character sheet, not on the map.

    Asserted so a future weapon does not quietly get its own glyph and turn the
    floor into a wall of punctuation nobody can learn.
    """
    from neverdeads_revenge.world.items import ITEMS

    by_kind: dict[str, set[str]] = {}
    for item in ITEMS.values():
        if item.kind == "draught":
            continue
        by_kind.setdefault(item.kind, set()).add(item.glyph)
    for kind, glyphs in by_kind.items():
        assert len(glyphs) == 1, f"{kind} items use several glyphs: {glyphs}"


# -- map container ---------------------------------------------------------
def test_tile_grid_roundtrips():
    dungeon = DungeonMap(width=10, height=6)
    assert dungeon.tile_at((0, 0)) is Tile.VOID
    dungeon.set_tile((3, 4), Tile.GRASS)
    assert dungeon.tile_at((3, 4)) is Tile.GRASS


def test_out_of_bounds_access_is_safe():
    dungeon = DungeonMap(width=5, height=5)
    assert not dungeon.in_bounds((-1, 0))
    assert not dungeon.in_bounds((5, 0))
    assert not dungeon.in_bounds((0, 5))
    assert dungeon.tile_at((99, 99)) is Tile.VOID
    dungeon.set_tile((99, 99), Tile.FLOOR)  # must not raise


def test_size_mismatch_raises():
    with pytest.raises(ValueError):
        DungeonMap(width=5, height=5, tiles=[0, 0])


def test_walkable_and_opaque_respect_bounds():
    dungeon = DungeonMap(width=5, height=5)
    assert not dungeon.is_walkable((-1, -1))
    assert dungeon.is_opaque((-1, -1))  # outside counts as solid


# -- rect ------------------------------------------------------------------
def test_rect_center_contains_intersects():
    a = Rect(2, 2, 6, 4)
    assert a.center == (5, 4)
    assert a.contains((2, 2))
    assert not a.contains((8, 6))
    assert a.intersects(Rect(7, 5, 3, 3))
    assert not a.intersects(Rect(8, 6, 3, 3))


def test_rect_inner_excludes_the_wall_ring():
    a = Rect(0, 0, 5, 5)
    assert a.inner.width == 3
    assert a.inner.height == 3
    assert len(a.inner_positions) == 9


# -- generation ------------------------------------------------------------
def test_generation_is_reproducible_from_a_seed():
    a = generate_floor(Rng(4242))
    b = generate_floor(Rng(4242))
    assert a.map.tiles == b.map.tiles
    assert a.player_start == b.player_start
    assert a.stairs_down == b.stairs_down
    assert a.spawn_points == b.spawn_points
    assert a.exit_tile is b.exit_tile
    assert set(a.items) == set(b.items)
    assert [i.name for i in a.items.values()] == [i.name for i in b.items.values()]


def test_different_seeds_give_different_layouts():
    tiles = {tuple(generate_floor(Rng(seed)).map.tiles) for seed in SEEDS}
    assert len(tiles) > len(SEEDS) // 2


@pytest.mark.parametrize("seed", SEEDS)
def test_stairs_are_always_reachable_from_the_player(seed):
    floor = generate_floor(Rng(seed))
    reachable = _reachable(floor.player_start, floor.map)
    assert floor.stairs_down in reachable, "player cannot reach the exit"


@pytest.mark.parametrize("seed", SEEDS)
def test_every_spawn_point_is_reachable(seed):
    floor = generate_floor(Rng(seed))
    reachable = _reachable(floor.player_start, floor.map)
    assert all(pos in reachable for pos in floor.spawn_points)


@pytest.mark.parametrize("seed", SEEDS)
def test_player_and_stairs_never_collide(seed):
    floor = generate_floor(Rng(seed))
    assert floor.player_start != floor.stairs_down
    assert floor.stairs_down not in floor.spawn_points


@pytest.mark.parametrize("seed", SEEDS)
def test_nothing_spawns_on_top_of_the_player(seed):
    floor = generate_floor(Rng(seed))
    assert floor.player_start not in floor.spawn_points


@pytest.mark.parametrize("seed", SEEDS)
def test_spawn_points_are_unique_and_standable(seed):
    floor = generate_floor(Rng(seed))
    assert len(set(floor.spawn_points)) == len(floor.spawn_points)
    assert all(floor.map.is_walkable(pos) for pos in floor.spawn_points)


@pytest.mark.parametrize("seed", SEEDS)
def test_borders_are_always_solid(seed):
    """Nothing should be walkable on the outer ring."""
    floor = generate_floor(Rng(seed))
    dungeon = floor.map
    for x in range(dungeon.width):
        assert not dungeon.is_walkable((x, 0))
        assert not dungeon.is_walkable((x, dungeon.height - 1))
    for y in range(dungeon.height):
        assert not dungeon.is_walkable((0, y))
        assert not dungeon.is_walkable((dungeon.width - 1, y))


@pytest.mark.parametrize("seed", SEEDS)
def test_player_stands_on_walkable_ground(seed):
    floor = generate_floor(Rng(seed))
    assert floor.map.is_walkable(floor.player_start)


def test_enemy_count_grows_with_depth():
    counts = [len(generate_floor(Rng(7), depth=d).spawn_points) for d in (1, 3, 6)]
    assert counts == sorted(counts)


def test_map_too_small_for_any_room_fails_loudly():
    # 5x5 leaves a 3x3 interior, smaller than the minimum room of 5x4.
    with pytest.raises(RuntimeError, match="failed to generate"):
        generate_floor(Rng(1), width=5, height=5)


def test_cramped_map_still_produces_a_usable_floor():
    """One room is allowed -- player and stairs then share it."""
    floor = generate_floor(Rng(1), width=12, height=12)
    assert floor.map.is_walkable(floor.player_start)
    assert floor.map.is_walkable(floor.stairs_down)
    assert floor.stairs_down in _reachable(floor.player_start, floor.map)


def test_decor_never_covers_the_stairs():
    for seed in SEEDS:
        floor = generate_floor(Rng(seed))
        assert floor.map.tile_at(floor.stairs_down) is Tile.STAIRS_DOWN


def test_flood_fill_respects_walls():
    dungeon = DungeonMap(width=7, height=3)
    for x in range(7):
        dungeon.set_tile((x, 1), Tile.WALL)
    dungeon.set_tile((0, 1), Tile.FLOOR)
    dungeon.set_tile((6, 1), Tile.FLOOR)
    reachable = _reachable((0, 1), dungeon)
    assert (0, 1) in reachable
    assert (6, 1) not in reachable


# -- chests -----------------------------------------------------------------
CURSE_KEYS = ("wither", "bleed", "frail", "heavy", "dim", "famine")


def test_chest_contents_are_decided_when_the_floor_is_built():
    """Determinism: the seed fixes what is in the chest before anyone looks.

    Rolled at generation rather than at the lid, so a run is still reproducible
    from its seed and the player cannot reroll a chest by walking off and back.
    """
    first = generate_floor(Rng(9), depth=3, curse_keys=CURSE_KEYS)
    second = generate_floor(Rng(9), depth=3, curse_keys=CURSE_KEYS)

    def chests(floor):
        return sorted(
            (item.curse, item.contents.item_id)
            for item in floor.items.values()
            if item.kind == "chest"
        )

    assert chests(first), "no chests on this floor to compare"
    assert chests(first) == chests(second)


def test_the_strong_tier_is_a_chest_reward_and_a_rare_find():
    """What a chest pays for -- and, deep down, occasionally a find of its own.

    Free strong loot on the shallow floors would make the chest the fool's
    bargain, so the rare find is fenced off below floor four. Both halves are
    asserted: that it happens at all, and that it stays rare enough to be worth
    the surprise.
    """
    from neverdeads_revenge.world.items import ITEMS, RARE_FIND_DEPTH

    strong = {t.key for t in ITEMS.values() if t.chest_only}
    assert strong, "there is no strong tier"

    for seed in range(20):
        floor = generate_floor(Rng(seed), depth=6, curse_keys=CURSE_KEYS)
        for item in floor.items.values():
            if item.kind == "chest":
                assert item.contents is not None
                assert item.contents.item_id in strong, "a chest held weak loot"

    for seed in range(40):
        for depth in range(1, RARE_FIND_DEPTH):
            floor = generate_floor(Rng(seed), depth=depth, curse_keys=CURSE_KEYS)
            for item in floor.items.values():
                assert item.item_id not in strong, (
                    f"the strong tier was lying around on floor {depth}"
                )

    found = sum(
        1
        for seed in range(40)
        if any(
            item.item_id in strong
            for item in generate_floor(
                Rng(seed), depth=8, curse_keys=CURSE_KEYS
            ).items.values()
        )
    )
    assert found, "the rare find never happens at all"
    assert found < 40, "the rare find is not rare"


@pytest.mark.parametrize("seed", range(20))
def test_chests_are_reachable_and_never_on_the_exit(seed):
    floor = generate_floor(Rng(seed), depth=5, curse_keys=CURSE_KEYS)
    reachable = _reachable(floor.player_start, floor.map)
    for pos, item in floor.items.items():
        if item.kind == "chest":
            assert pos in reachable, "a chest is walled off"
            assert pos != floor.stairs_down


def test_chests_get_more_common_deeper():
    def chests(depth: int) -> int:
        floor = generate_floor(Rng(5), depth=depth, curse_keys=CURSE_KEYS)
        return len([i for i in floor.items.values() if i.kind == "chest"])

    assert chests(1) <= chests(6)


def test_a_floor_with_no_curses_has_no_chests():
    """The generator is told which curses exist; told about none, it places none.

    Better an empty floor than a chest that costs nothing, which would make the
    whole bargain a lie.
    """
    floor = generate_floor(Rng(4), depth=3)
    assert not [i for i in floor.items.values() if i.kind == "chest"]


def test_every_chest_names_a_curse_the_game_knows():
    """A typo in a key would be a chest that opens for free."""
    from neverdeads_revenge.game.curses import CURSES

    for seed in range(20):
        floor = generate_floor(Rng(seed), depth=4, curse_keys=CURSE_KEYS)
        for item in floor.items.values():
            if item.kind == "chest":
                assert item.curse in CURSES


# -- the way out -----------------------------------------------------------
def test_the_rift_only_appears_on_the_escape_floor():
    """Every floor before the last holds stairs down, not a win condition.

    A rift on floor 3 would end the run the moment the player found it, and the
    player has no way of knowing that from the map.
    """
    for depth in range(1, ESCAPE_DEPTH):
        floor = generate_floor(Rng(depth), depth=depth)
        assert floor.exit_tile is Tile.STAIRS_DOWN
        assert not floor.is_final
        assert floor.map.tile_at(floor.stairs_down) is Tile.STAIRS_DOWN
        assert not floor.map.find_tile(Tile.RIFT)


def test_the_escape_floor_holds_a_rift_instead_of_stairs():
    for depth in (ESCAPE_DEPTH, ESCAPE_DEPTH + 3):
        floor = generate_floor(Rng(depth), depth=depth)
        assert floor.exit_tile is Tile.RIFT
        assert floor.is_final
        assert floor.map.tile_at(floor.stairs_down) is Tile.RIFT
        assert not floor.map.find_tile(Tile.STAIRS_DOWN)


def test_the_rift_is_walkable_and_neither_hides_nor_hides_behind_anything():
    assert not Tile.RIFT.blocks_movement
    assert not Tile.RIFT.blocks_sight


@pytest.mark.parametrize("seed", SEEDS)
def test_the_rift_is_reachable(seed):
    floor = generate_floor(Rng(seed), depth=ESCAPE_DEPTH)
    assert floor.stairs_down in _reachable(floor.player_start, floor.map)


# -- loot ------------------------------------------------------------------
@pytest.mark.parametrize("seed", SEEDS)
def test_loot_lands_on_open_ground_that_can_be_reached(seed):
    for depth in (1, 5, ESCAPE_DEPTH):
        floor = generate_floor(Rng(seed), depth=depth)
        reachable = _reachable(floor.player_start, floor.map)
        for pos, item in floor.items.items():
            assert floor.map.tile_at(pos) is Tile.FLOOR, "loot landed on decor"
            assert pos in reachable, "loot is walled off"
            assert floor.map.item_at(pos) is item


@pytest.mark.parametrize("seed", SEEDS)
def test_loot_never_lands_on_the_players_room_or_the_exit(seed):
    """An item you start on, or that sits on the stairs, is not a decision."""
    floor = generate_floor(Rng(seed))
    assert floor.player_start not in floor.items
    assert floor.stairs_down not in floor.items


def test_every_floor_holds_something_to_find():
    """A floor with no loot at all makes the healing curve a lie."""
    for depth in range(1, ESCAPE_DEPTH + 1):
        for seed in range(10):
            floor = generate_floor(Rng(seed), depth=depth)
            assert floor.items, f"floor {depth} seed {seed} had no loot"


def test_loot_gets_more_plentiful_deeper():
    counts = [
        len(generate_floor(Rng(11), depth=d).items)
        for d in (1, 4, 7, ESCAPE_DEPTH)
    ]
    assert counts == sorted(counts)


def test_the_elixir_becomes_more_common_deeper():
    from neverdeads_revenge.world.items import ITEMS, roll_item, _weight_at

    assert _weight_at(ITEMS["elixir"], 9) > _weight_at(ITEMS["elixir"], 1)
    assert _weight_at(ITEMS["potion"], 9) == _weight_at(ITEMS["potion"], 1)

    # And it shows up in the actual rolls, not just the weight table.
    early = [roll_item(Rng(s), 1).key for s in range(400)]
    deep = [roll_item(Rng(s), 9).key for s in range(400)]
    assert deep.count("elixir") > early.count("elixir")
