"""The character sheet.

The sidebar shows the numbers a fight turns on and has no room for more. This is
where the rest lives: what each piece of equipment is contributing, what is being
carried, and what a curse has done to you.

A modal rather than a screen, so the map stays visible behind it -- somebody
checking their stats mid-fight should not lose sight of what is standing next to
them. Any key closes it, and it costs no turn.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

from ...game.levels import KILLS_PER_LEVEL, MAX_LEVEL
from ...game.pace import MAX_ACTIONS_PER_SECOND, actions_per_second
from ...game.shop import describe_item
from ...world.items import ITEMS

from ...game.state import GameState

__all__ = ["CharacterScreen"]

#: Slots, in the order they are shown.
SLOTS: tuple[str, ...] = ("weapon", "armour", "amulet")


class CharacterScreen(ModalScreen[None]):
    """Everything the sidebar has no room for. Any key closes."""

    BINDINGS = [Binding("escape", "dismiss", "Close")]

    DEFAULT_CSS = """
    CharacterScreen {
        align: center middle;
        background: $background 70%;
    }
    """

    def __init__(self, state: GameState) -> None:
        super().__init__()
        self.state = state

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="character"):
            yield Static("CHARACTER", id="character-title")
            yield Static(self._sheet(), id="character-body")
            yield Static("press any key", id="character-hint")

    def on_key(self, event) -> None:
        # A key still repeating from the screen before this one must not close
        # this one on the way in: holding ``c`` used to open and close the sheet
        # thirty times a second. See App.note_key.
        if self.app.note_key(event.key):
            event.stop()
            return
        event.stop()
        self.dismiss()

    # -- the sheet ----------------------------------------------------------
    def _sheet(self) -> str:
        """The whole sheet as markup.

        Built here rather than in the widget tree because it is a block of text
        with aligned columns, and a dozen ``Static`` widgets would be a dozen
        things to keep in sync for no gain.
        """
        state = self.state
        player = state.player
        low, high = player.damage_range

        lines = [
            f"[bold {player.color}]{player.name}[/]  [dim]{state.hero.title}[/]",
            "",
            _row("health", f"{player.hp} / {player.max_hp}"),
            _row("level", _level_line(state)),
            _row("speed", f"{player.speed:.2f}   {_rate_line(player.speed)}"),
            _row("damage", f"{low}-{high}"),
            _row("crit", f"{player.crit_chance:.0%}  x{player.crit_multiplier:.1f}"),
            _row("accuracy", f"{player.accuracy}"),
            _row("evasion", f"{player.evasion}"),
            _row("armour", f"{player.armor}"),
            "",
        ]

        for slot in SLOTS:
            item = player.equipment.get(slot)
            if item is None:
                lines.append(f"[dim]{slot:<9}[/][dim]nothing[/]")
                continue
            # The same describer the shop uses, so a blade reads the same in
            # both places -- and an amulet, whose effect is a sentence rather
            # than a list of numbers, reads as one.
            lines.append(
                f"[dim]{slot:<9}[/][bold]{item.name}[/]  "
                f"[dim]{describe_item(ITEMS[item.item_id])}[/]"
            )

        lines.append("")
        lines.append(_row("carried", _carried(state)))

        if state.curses:
            # Given their own block rather than a column, because a price is a
            # sentence and the player needs to be reminded what they agreed to.
            lines.append("")
            lines.append("[dim]curses[/]")
            for curse in state.curses:
                lines.append(f"  [bold red]{curse.name}[/]  [dim]{curse.price}[/]")

        return "\n".join(lines)


def _rate_line(speed: float) -> str:
    """How often a held direction acts, against the ceiling.

    Shown as ``9/20`` because the number is worth seeing twice: it is what the
    hero's speed is *for* under the hand, and it is the one place speed is felt
    rather than read. The ceiling is there so that speed bought later has
    somewhere to go.
    """
    return (
        f"{actions_per_second(speed):.0f}/{MAX_ACTIONS_PER_SECOND:.0f} a second"
    )


def _level_line(state: GameState) -> str:
    """The level, and how much of the next one the run has already earned."""
    if state.level >= MAX_LEVEL:
        return f"{state.level}  (nothing left to learn)"
    earned = state.kills % KILLS_PER_LEVEL
    return f"{state.level}  ({earned}/{KILLS_PER_LEVEL} kills to the next)"


def _row(label: str, value: str) -> str:
    """A label and its value, in a column.

    Nine wide because "accuracy" is eight: at eight the value runs straight into
    the label and the sheet reads as one long word.
    """
    return f"[dim]{label:<9}[/]{value}"


def _carried(state: GameState) -> str:
    """What is in the pack, counted rather than listed."""
    counts: dict[str, int] = {}
    for item in state.inventory:
        counts[item.name] = counts.get(item.name, 0) + 1
    if not counts:
        return "[dim]nothing[/]"
    return ", ".join(f"{count}x {name}" for name, count in sorted(counts.items()))
