"""The map renderer.

Draws the dungeon as coloured glyphs. Three visibility states are drawn
differently, because telling them apart at a glance is what makes a text roguelite
readable:

    visible   full colour
    explored  dimmed -- you remember the room, but not what is in it now
    unseen    blank

The dungeon is larger than the terminal, so the view is a viewport centred on the
player. Actors are drawn on top of the terrain, and the player last of all.
"""

from __future__ import annotations

from rich.text import Text
from textual.reactive import reactive
from textual.widget import Widget

from neverdeads_revenge.game.state import GameState
from neverdeads_revenge.world.tiles import Tile

__all__ = ["MapView"]

#: Colour for terrain the player has seen before but cannot see right now.
MEMORY_COLOR = "grey30"
UNSEEN_COLOR = "black"

#: Keep a little of the surrounding map on screen even when it is bigger than
#: the viewport, so the player has spatial context.
VIEWPORT_MARGIN = 2


class MapView(Widget):
    """Renders the current floor, centred on the player."""

    DEFAULT_CSS = """
    MapView {
        width: 1fr;
        height: 1fr;
        min-width: 20;
        min-height: 10;
    }
    """

    state: reactive[GameState | None] = reactive(None, layout=True)

    def __init__(self, game_state: GameState | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        # A widget that never takes focus cannot swallow movement keys.
        self.can_focus = False
        self.state = game_state

    def watch_state(self) -> None:
        self.refresh()

    # -- viewport -----------------------------------------------------------
    def _viewport(self, state: GameState) -> tuple[int, int, int, int]:
        """Return ``(left, top, width, height)`` of the visible window."""
        dungeon = state.dungeon_map
        view_w, view_h = self.size.width, self.size.height
        if view_w <= 0 or view_h <= 0:
            view_w, view_h = 80, 24

        width = min(view_w, dungeon.width)
        height = min(view_h, dungeon.height)

        # Clamp rather than wrap, so the player is always on screen.
        left = state.player.position[0] - width // 2
        top = state.player.position[1] - height // 2
        left = max(0, min(left, dungeon.width - width))
        top = max(0, min(top, dungeon.height - height))
        return left, top, width, height

    # -- rendering ----------------------------------------------------------
    def render(self) -> Text:
        """Build the whole frame as one Rich ``Text``."""
        state = self.state
        if state is None:
            return Text("no dungeon loaded", style="dim")

        dungeon = state.dungeon_map
        left, top, width, height = self._viewport(state)

        lines: list[Text] = []
        for y in range(top, top + height):
            line = Text(no_wrap=True, tab_size=1, end="")
            for x in range(left, left + width):
                line.append(self._cell((x, y), state))
            lines.append(line)
        return Text("\n").join(lines)

    def _cell(self, position, state: GameState) -> Text:
        """One map cell: an actor if there is one, otherwise loot, else terrain."""
        dungeon = state.dungeon_map
        visible = dungeon.is_visible(position)

        actor = state.actor_at(position)
        if actor is not None and visible:
            style = f"bold {actor.color}" if not actor.is_player else actor.color
            return Text(actor.glyph, style=style)

        # Loot sits on the ground, so it is drawn over the terrain and under any
        # monster standing on it -- which is exactly the choice the player has to
        # make about whether the potion is worth the fight.
        item = dungeon.item_at(position)
        if item is not None and visible:
            return Text(item.glyph, style=f"bold {item.color}")

        tile = dungeon.tile_at(position)
        if visible:
            return Text(tile.glyph, style=tile.color)

        if dungeon.is_explored(position) and self._stays_legible(tile):
            # Remembered ground: walls and the way onward stay readable, the
            # rest fades. Remembered loot is deliberately not drawn: you know
            # the room, not what is still lying in it.
            return Text(tile.glyph, style=MEMORY_COLOR)

        return Text(" ", style=UNSEEN_COLOR)

    @staticmethod
    def _stays_legible(tile: Tile) -> bool:
        """Whether dimmed terrain should still be drawn.

        Walls and the exits give the player their mental map. Remembering the
        colour of floor tiles is noise.
        """
        return tile.blocks_movement or tile in (Tile.STAIRS_DOWN, Tile.RIFT)
