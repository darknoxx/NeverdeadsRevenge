"""The dungeon grid and the things scattered across it."""

from __future__ import annotations

from dataclasses import dataclass, field

from neverdeads_revenge.core.direction import CARDINALS, Direction, Pos

from .tiles import Tile

__all__ = ["GroundItem", "DungeonMap"]


@dataclass(slots=True)
class GroundItem:
    """An item lying on the floor.

    ``heal`` is the health a drink restores. Every item in the game is currently
    a healing draught, so the field is named for what it does rather than for
    some future general case: when a wand or a scroll exists it will need a real
    effect, not this field stretched to fit it.
    """

    item_id: str
    name: str
    glyph: str = "*"
    color: str = "yellow"
    heal: int = 0


@dataclass(slots=True)
class DungeonMap:
    """A rectangular grid of :class:`Tile`.

    Tiles are stored as a flat list of ints (the enum values) rather than a list
    of enums: it is smaller, compares fast, and FOV touches every cell.
    """

    width: int
    height: int
    depth: int = 1
    tiles: list[int] = field(default_factory=list)
    items: dict[Pos, GroundItem] = field(default_factory=dict)
    explored: set[Pos] = field(default_factory=set)
    visible: set[Pos] = field(default_factory=set)

    def __post_init__(self) -> None:
        if not self.tiles:
            self.tiles = [Tile.VOID.value] * (self.width * self.height)
        expected = self.width * self.height
        if len(self.tiles) != expected:
            raise ValueError(f"expected {expected} tiles, got {len(self.tiles)}")

    # -- bounds -------------------------------------------------------------
    @property
    def bounds(self) -> tuple[Pos, Pos]:
        """Inclusive ``(top_left, bottom_right)``."""
        return (0, 0), (self.width - 1, self.height - 1)

    def in_bounds(self, pos: Pos) -> bool:
        x, y = pos
        return 0 <= x < self.width and 0 <= y < self.height

    def _index(self, pos: Pos) -> int:
        return pos[1] * self.width + pos[0]

    # -- tiles --------------------------------------------------------------
    def tile_at(self, pos: Pos) -> Tile:
        if not self.in_bounds(pos):
            return Tile.VOID
        return Tile(self.tiles[self._index(pos)])

    def set_tile(self, pos: Pos, tile: Tile) -> None:
        if self.in_bounds(pos):
            self.tiles[self._index(pos)] = tile.value

    # -- movement -----------------------------------------------------------
    def is_walkable(self, pos: Pos) -> bool:
        """True if an actor could stand here."""
        if not self.in_bounds(pos):
            return False
        return self.tile_at(pos).blocks_movement is False

    def is_opaque(self, pos: Pos) -> bool:
        """True if this tile stops line of sight."""
        if not self.in_bounds(pos):
            return True
        return self.tile_at(pos).blocks_sight

    def neighbours(self, pos: Pos) -> list[Pos]:
        """The four orthogonal neighbours that are in bounds."""
        return [n for n in (d.step(pos) for d in CARDINALS) if self.in_bounds(n)]

    def neighbours8(self, pos: Pos) -> list[Pos]:
        """All eight neighbours that are in bounds."""
        return [n for n in (d.step(pos) for d in Direction if d is not Direction.NONE) if self.in_bounds(n)]

    # -- perception ---------------------------------------------------------
    def is_visible(self, pos: Pos) -> bool:
        return pos in self.visible

    def is_explored(self, pos: Pos) -> bool:
        return pos in self.explored

    def clear_visibility(self) -> None:
        self.visible.clear()

    # -- items --------------------------------------------------------------
    def item_at(self, pos: Pos) -> GroundItem | None:
        return self.items.get(pos)

    def add_item(self, pos: Pos, item: GroundItem) -> None:
        self.items[pos] = item

    def remove_item(self, pos: Pos) -> GroundItem | None:
        return self.items.pop(pos, None)

    # -- queries ------------------------------------------------------------
    def walkable_positions(self) -> list[Pos]:
        """Every position an actor could stand on."""
        return [
            (x, y)
            for y in range(self.height)
            for x in range(self.width)
            if self.is_walkable((x, y))
        ]

    def floor_positions(self) -> list[Pos]:
        """Walkable positions that are plain floor, excluding stairs and doors."""
        return [
            pos
            for pos in self.walkable_positions()
            if self.tile_at(pos) is Tile.FLOOR
        ]

    def find_tile(self, tile: Tile) -> list[Pos]:
        """Every position holding the given tile."""
        return [
            (x, y)
            for y in range(self.height)
            for x in range(self.width)
            if self.tile_at((x, y)) is tile
        ]

    def __repr__(self) -> str:
        return f"DungeonMap({self.width}x{self.height}, depth={self.depth})"
