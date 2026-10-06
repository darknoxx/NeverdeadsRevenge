"""The legend panel.

Permanent, always visible, built from the game's own data. The point is not
that the glyphs are listed once but that a terrain type or a monster added to
``tiles.py`` or ``actors.py`` appears here without anyone remembering to add it.

Rendered as one Rich ``Text`` so the glyphs keep their own colours, matching what
the player sees on the map.
"""

from __future__ import annotations

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

from ...game.actors import Hero
from ...game.prologue import GOAL_HINT, legend_rows
from ...world.tiles import Tile

__all__ = ["Legend", "PANEL_WIDTH", "USABLE_WIDTH", "SIDEBAR_CHROME"]

#: Width of the sidebar the panel lives in, set in ``app.tcss``. Named here so
#: the fitting test has something to check against instead of a magic number.
PANEL_WIDTH = 34

#: Columns the sidebar itself spends on its border (2) and padding (2). Not the
#: panel's business, but the panel has to account for it.
SIDEBAR_CHROME = 4

#: What a legend line may actually occupy: the sidebar's content box, minus this
#: panel's own left padding.
USABLE_WIDTH = PANEL_WIDTH - SIDEBAR_CHROME - 1


class Legend(Static):
    """What you have to act on: the goal, the monsters, and the loot.

    Lives in the sidebar, under the HUD, rather than in a row of its own at the
    bottom. The map is the thing that needs height, and a bottom legend competes
    with it for every row. Beside the map it costs width the sidebar was already
    spending.

    Terrain is not shown here, only in the help screen. This panel is clipped
    rather than scrolled -- the sidebar has a fixed height and the map will not
    give any up -- so a row spent on something static is a row that can push the
    goal off the bottom. Everything here is either a number that changes every
    descent or a glyph you act on.
    """

    DEFAULT_CSS = """
    Legend {
        width: 100%;
        height: 1fr;
        border-top: solid $panel;
        padding: 0 0 0 1;
        background: $surface;
    }
    """

    #: Which floor the monster numbers describe. Reactive so that a descent
    #: redraws the panel by assignment, with no call site that has to remember:
    #: a legend quoting floor-1 damage next to a floor-8 ghoul is worse than no
    #: legend at all.
    depth: reactive[int] = reactive(1)

    #: Which hero the "you" row is describing. Reactive for the same reason as
    #: ``depth``: the roster is data, so the panel has to be told who is playing
    #: rather than assuming, or every hero is labelled with the first one's glyph.
    hero: reactive[Hero | None] = reactive(None)

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("markup", False)
        super().__init__(**kwargs)
        self.can_focus = False

    def on_mount(self) -> None:
        self.redraw()

    def watch_depth(self, depth: int) -> None:
        self.redraw()

    def watch_hero(self, hero: Hero | None) -> None:
        self.redraw()

    def redraw(self) -> None:
        """Rebuild the panel from the current game data.

        Named ``redraw`` rather than ``refresh`` on purpose: ``refresh`` is
        Textual's own method, and overwriting it breaks internal callers that
        expect the return value.
        """
        out = Text(no_wrap=True)
        out.append("LEGEND\n", style="bold")

        # The goal first, directly under the heading. It is the one line that
        # must never be the thing that gets clipped off the bottom when the
        # sidebar runs short.
        out.append(f"{Tile.RIFT.glyph} ", style="bold bright_cyan")
        out.append(f"{GOAL_HINT}\n", style="bold")

        for glyph, meaning in legend_rows(self.depth, self.hero):
            if not glyph:
                # An empty meaning is a section break; an empty glyph with text
                # is a continuation line, indented under the entry above it.
                if not meaning:
                    out.append("\n")
                else:
                    out.append(f" {meaning}\n", style="dim")
                continue
            # A row may carry several glyphs -- the wearable kinds share one --
            # and each is coloured like the thing it stands for on the map.
            # A single-glyph row goes through exactly the same path.
            for char in glyph:
                out.append(
                    char, style=_glyph_style(char) if char.strip() else "dim"
                )
            out.append(" ")
            # Truncation is a backstop, not the design: tests/test_ui.py asserts
            # every line fits, so a monster whose stats grow too wide fails
            # there instead of silently wrapping here.
            out.append(
                f"{meaning[: USABLE_WIDTH - len(glyph) - 1]}\n", style="bold"
            )

        self.update(out)


def _glyph_style(glyph: str) -> str:
    """Colour a legend entry the way the map colours the same glyph.

    Every registry is searched rather than a single hero being special-cased:
    the old version hardcoded ``HEROES["noxx"]`` and painted every hero's row
    white, which would have been wrong the day a second hero has a different
    colour.
    """
    from ...game.actors import ENEMIES, HEROES
    from ...world.items import ITEMS
    from ...world.tiles import Tile

    for hero in HEROES.values():
        if hero.glyph == glyph:
            return f"bold {hero.color}"
    for template in ENEMIES.values():
        if template.glyph == glyph:
            return f"bold {template.color}"
    for item in ITEMS.values():
        if item.glyph == glyph:
            return f"bold {item.color}"
    for tile in Tile:
        if tile.glyph == glyph:
            return tile.color
    return "dim"