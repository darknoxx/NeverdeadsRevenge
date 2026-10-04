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

from ...game.prologue import legend_rows

__all__ = ["Legend", "PANEL_WIDTH", "USABLE_WIDTH"]

#: Width of the panel, set in ``app.tcss``. Named here so the fitting test has
#: something to check against instead of a magic number.
PANEL_WIDTH = 32

#: What is left of that once the border and the horizontal padding are gone.
USABLE_WIDTH = PANEL_WIDTH - 4


class Legend(Static):
    """What every glyph on the map means.

    The height is set by ``#game-footer`` in the stylesheet, not here: the log
    and this panel share one row, and the number of legend lines has to fit
    inside whatever the log gets.
    """

    DEFAULT_CSS = """
    Legend {
        width: 32;  /* PANEL_WIDTH */
        background: $surface;
    }
    """

    #: Which floor the monster numbers describe. Reactive so that a descent
    #: redraws the panel by assignment, with no call site that has to remember:
    #: a legend quoting floor-1 damage next to a floor-8 ghoul is worse than no
    #: legend at all.
    depth: reactive[int] = reactive(1)

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("markup", False)
        super().__init__(**kwargs)
        self.can_focus = False

    def on_mount(self) -> None:
        self.redraw()

    def watch_depth(self, depth: int) -> None:
        self.redraw()

    def redraw(self) -> None:
        """Rebuild the panel from the current game data.

        Named ``redraw`` rather than ``refresh`` on purpose: ``refresh`` is
        Textual's own method, and overwriting it breaks internal callers that
        expect the return value.
        """
        out = Text(no_wrap=True)
        out.append("LEGEND\n", style="bold")

        for glyph, meaning in legend_rows(self.depth):
            if not glyph:
                # An empty meaning is a section break; an empty glyph with text
                # is a continuation line, indented under the entry above it.
                if not meaning:
                    out.append("\n")
                else:
                    out.append(f" {meaning}\n", style="dim")
                continue
            out.append(f"{glyph} ", style=_glyph_style(glyph))
            # Truncation is a backstop, not the design: tests/test_ui.py asserts
            # every line fits, so a monster whose stats grow too wide fails
            # there instead of silently wrapping here.
            out.append(f"{meaning[:USABLE_WIDTH - 2]}\n", style="bold")

        out.append("\n? controls", style="dim")
        self.update(out)


def _glyph_style(glyph: str) -> str:
    """Colour a legend entry the way the map colours the same glyph."""
    from ...game.actors import ENEMIES, HEROES
    from ...world.tiles import Tile

    if glyph == HEROES["noxx"].glyph:
        return "bold white"
    for template in ENEMIES.values():
        if template.glyph == glyph:
            return template.color
    for tile in Tile:
        if tile.glyph == glyph:
            return tile.color
    return "dim"