"""The side panel: who you are, how fast you are moving, and where the run stands.

Speed is shown next to the REVENGE stacks, because it is the stat that actually
changes how the game plays. A player who does not notice the bonus kicking in
after a kill never sees what Noxx is good at.

The panel shares the sidebar with the legend, and the sidebar is clipped rather
than scrolled, so keeping this short is a gameplay concern: every row this panel
grows is a legend row that falls off the bottom, and the line that must never
fall off is the one saying where the way out is. ``tests/test_ui.py`` asserts
both that no line here wraps and that the whole legend still fits.
"""

from __future__ import annotations

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

from neverdeads_revenge.game.state import GameState
from neverdeads_revenge.world.generator import ESCAPE_DEPTH

__all__ = ["Hud"]

#: Width of the health bar, in cells. Fits the sidebar without wrapping.
BAR_CELLS = 12


class Hud(Static):
    """Hero name, health, speed, and run stats."""

    DEFAULT_CSS = """
    Hud {
        height: auto;
    }
    """

    state: reactive[GameState | None] = reactive(None, layout=True)

    def __init__(self, game_state: GameState | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.can_focus = False
        self.state = game_state

    def watch_state(self) -> None:
        self.redraw()

    def redraw(self) -> None:
        """Rebuild the panel text from the current state.

        Named ``redraw`` rather than ``refresh`` on purpose: ``refresh`` is
        Textual's own method and overwriting it breaks internal callers that
        expect the return value.
        """
        state = self.state
        if state is None:
            self.update(Text(""))
            return

        player = state.player
        out = Text(no_wrap=True)
        out.append(f"{player.glyph} {player.name}", style="bold")
        out.append(f"  {state.hero.title}\n", style="dim")

        # Health bar. 12 cells keeps the line inside the sidebar's content box,
        # so health never wraps onto a line of its own.
        ratio = player.hp / player.max_hp if player.max_hp else 0.0
        filled = max(0, min(BAR_CELLS, round(ratio * BAR_CELLS)))
        colour = "green" if ratio > 0.5 else "yellow" if ratio > 0.25 else "red"
        out.append("HP  ", style="dim")
        out.append("█" * filled, style=colour)
        out.append("░" * (BAR_CELLS - filled), style="grey30")
        out.append(f"  {player.hp}/{player.max_hp}\n", style=colour)

        # Speed and crit get a line each: together they are 34 columns and the
        # sidebar's content box is 30, so sharing one wraps the crit multiplier
        # onto a line of its own. The legend below has slack now that the terrain
        # reference moved to the help.
        bonus = player.speed_bonus
        out.append("SPD ", style="dim")
        out.append(f"{player.stats.speed:.2f}", style="bold white")
        if bonus:
            out.append(f" +{bonus:.1f}", style="bold green")
        out.append(f"\nCRT ", style="dim")
        out.append(f"{player.stats.crit_chance:.0%}", style="bold yellow")
        out.append(f"  x{player.stats.crit_multiplier:.1f}\n", style="dim")

        if state.revenge_stacks:
            out.append(f"REVENGE x{state.revenge_stacks}\n", style="bold green")

        out.append(f"Floor {state.depth}", style="bold cyan")
        out.append(f"/{ESCAPE_DEPTH}\n", style="dim cyan")
        if state.at_the_rift:
            out.append("The rift hums.\n", style="bold bright_cyan")

        potions = sum(1 for item in state.inventory if item.heal > 0)
        out.append("Draughts ", style="dim")
        out.append(f"{potions}", style="bold bright_red" if potions else "dim")
        if potions:
            out.append("  q", style="dim")
        out.append("\n")

        out.append(f"Kills {state.kills}  Turns {state.total_turns}\n", style="dim")
        out.append(f"Score {state.score}\n", style="dim")

        self.update(out)
