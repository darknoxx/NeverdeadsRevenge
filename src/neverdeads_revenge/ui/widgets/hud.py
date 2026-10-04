"""The side panel: who you are, and how fast you are moving.

Speed is shown prominently and next to the REVENGE stacks, because it is the stat
that actually changes how the game plays. A player who does not notice the bonus
kicking in after a kill never sees what Noxx is good at.
"""

from __future__ import annotations

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

from neverdeads_revenge.game.state import GameState

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

        # Health bar. 12 cells keeps the line inside the 26-column sidebar,
        # so health never wraps onto a line of its own.
        ratio = player.hp / player.max_hp if player.max_hp else 0.0
        filled = max(0, min(BAR_CELLS, round(ratio * BAR_CELLS)))
        colour = "green" if ratio > 0.5 else "yellow" if ratio > 0.25 else "red"
        out.append("HP  ", style="dim")
        out.append("█" * filled, style=colour)
        out.append("░" * (BAR_CELLS - filled), style="grey30")
        out.append(f"  {player.hp}/{player.max_hp}\n", style=colour)

        # Speed is the point of this hero, so it gets its own line.
        bonus = player.speed_bonus
        out.append("SPD ", style="dim")
        out.append(f"{player.stats.speed:.2f}", style="bold white")
        if bonus:
            out.append(f" +{bonus:.1f}", style="bold green")
        out.append(f"  ({1 / player.speed:.1f}/turn)\n", style="dim")

        out.append("CRT ", style="dim")
        out.append(f"{player.stats.crit_chance:.0%}", style="bold yellow")
        out.append(f"  x{player.stats.crit_multiplier:.1f}\n", style="dim")

        if state.revenge_stacks:
            out.append(f"\nREVENGE x{state.revenge_stacks}\n", style="bold green")

        out.append("\n")
        out.append(f"Floor {state.depth}\n", style="bold cyan")
        out.append(f"Kills  {state.kills}\n", style="dim")
        # Run total, not the per-floor clock: the floor number is right above it.
        out.append(f"Turns  {state.total_turns}\n", style="dim")
        out.append(f"Score  {state.score}\n", style="dim")

        self.update(out)
