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
        # The hero's own colour, so the name in the sidebar matches the glyph on
        # the map. Two different marks for the same character is a small thing
        # that makes the screen feel assembled rather than drawn.
        out.append(f"{player.glyph} {player.name}", style=f"bold {player.color}")
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

        # Damage, crit, speed, armour and evasion each get a share of two lines.
        # They are the numbers a fight turns on, and now that equipment moves
        # them the player has to be able to watch them move. The full sheet, with
        # what each piece contributes, is on the character screen behind ``c``.
        low, high = player.damage_range
        out.append("DMG ", style="dim")
        out.append(f"{low}-{high}", style="bold white")
        out.append("  CRT ", style="dim")
        out.append(f"{player.crit_chance:.0%}\n", style="bold yellow")

        out.append("SPD ", style="dim")
        out.append(f"{player.speed:.2f}", style="bold white")
        if player.speed_bonus:
            out.append(f"+{player.speed_bonus:.1f}", style="bold green")
        out.append("  ARM ", style="dim")
        out.append(f"{player.armor}", style="bold white")
        out.append("  EVA ", style="dim")
        out.append(f"{player.evasion}\n", style="bold white")

        if state.revenge_stacks:
            # Name the grant, not just the count. Three heroes collect three
            # different things from the same mechanic, so "REVENGE x3" alone
            # would mean a different number on each of them.
            out.append(f"REVENGE x{state.revenge_stacks}", style="bold green")
            out.append(
                f"  {player.trait.describe(state.revenge_stacks)}\n",
                style="green",
            )

        # What is being worn, by slot. Emptied slots are shown as a dash rather
        # than hidden, so the sidebar does not change height the first time
        # something is picked up.
        for slot, label in (("weapon", "W"), ("armour", "A")):
            item = player.equipment.get(slot)
            out.append(f"{label} ", style="dim")
            if item is None:
                out.append("—\n", style="dim")
            else:
                out.append(f"{item.name}\n", style="bold white")

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
