"""Terrain types.

Each tile knows how it looks (glyph + colour) and how it behaves (blocks
movement, blocks sight). Keeping presentation next to the terrain data means the
renderer has nothing to look up and the two can never drift apart.
"""

from __future__ import annotations

from enum import Enum

__all__ = ["Tile", "Terrain", "is_wall", "blocks_sight", "is_walkable"]


class Tile(Enum):
    """A single terrain type."""

    VOID = " "
    FLOOR = "."
    WALL = "#"
    DOOR = "+"
    STAIRS_DOWN = ">"
    RUBBLE = ","
    GRASS = '"'
    WATER = "~"
    #: The way out. Only the deepest floor has one, and standing on it ends the
    #: run in a victory rather than a death. A different tile from the stairs on
    #: purpose: the map should not make the player wonder whether pressing down
    #: here drops them another floor or takes them home.
    RIFT = "%"

    # -- presentation -------------------------------------------------------
    @property
    def glyph(self) -> str:
        """The character used to draw this tile."""
        return self.value

    @property
    def color(self) -> str:
        """A Rich/Textual colour name for the glyph."""
        return _COLORS[self]

    @property
    def background(self) -> str:
        """A Rich/Textual background colour name."""
        return _BACKGROUNDS[self]

    @property
    def blocks_movement(self) -> bool:
        return self in _BLOCKS_MOVEMENT

    @property
    def blocks_sight(self) -> bool:
        return self in _BLOCKS_SIGHT

    @property
    def description(self) -> str:
        return _DESCRIPTIONS[self]


_COLORS: dict[Tile, str] = {
    Tile.VOID: "black",
    Tile.FLOOR: "grey50",
    Tile.WALL: "grey37",
    Tile.DOOR: "tan",
    Tile.STAIRS_DOWN: "cyan",
    Tile.RUBBLE: "grey42",
    Tile.GRASS: "green",
    Tile.WATER: "blue",
    Tile.RIFT: "bright_cyan",
}

_BACKGROUNDS: dict[Tile, str] = {
    Tile.VOID: "black",
    Tile.FLOOR: "grey11",
    Tile.WALL: "grey19",
    Tile.DOOR: "grey11",
    Tile.STAIRS_DOWN: "grey11",
    Tile.RUBBLE: "grey11",
    Tile.GRASS: "grey11",
    Tile.WATER: "grey11",
    Tile.RIFT: "grey11",
}

_DESCRIPTIONS: dict[Tile, str] = {
    Tile.VOID: "solid darkness",
    Tile.FLOOR: "bare floor",
    Tile.WALL: "a rough wall",
    Tile.DOOR: "a wooden door",
    Tile.STAIRS_DOWN: "stairs leading down",
    Tile.RUBBLE: "a pile of rubble",
    Tile.GRASS: "patchy grass",
    Tile.WATER: "shallow water",
    Tile.RIFT: "a rift out of the dark",
}

# Rubble is walkable but opaque; everything else opaque is solid.
_BLOCKS_MOVEMENT = frozenset({Tile.VOID, Tile.WALL, Tile.WATER})
_BLOCKS_SIGHT = frozenset({Tile.VOID, Tile.WALL, Tile.WATER, Tile.RUBBLE})

# Terrain that a generator is allowed to carve rooms out of.
CARVABLE = frozenset({Tile.VOID})


def is_wall(tile: Tile) -> bool:
    """True for tiles that stop movement."""
    return tile.blocks_movement


def blocks_sight(tile: Tile) -> bool:
    """True for tiles that stop line of sight."""
    return tile.blocks_sight


def is_walkable(tile: Tile) -> bool:
    """True for tiles an actor may stand on."""
    return not tile.blocks_movement
