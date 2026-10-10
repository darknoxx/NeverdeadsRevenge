"""The pack, and what is in it.

The character sheet answers "how strong am I". This answers "what have I got, and
what does it do" -- which had no answer on screen at all. An amulet's ability is
a sentence rather than a number, and the only place it was ever written down was
the shop it came from, so a player who had bought the deathwatch and then
descended had to remember what they had agreed to.

A modal, like the sheet, and for the same reason: somebody checking what they are
carrying mid-fight should not lose sight of what is standing next to them. Any
key closes it, and it costs no turn.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

from ...game.shop import describe_item
from ...game.state import GameState
from ...world.items import ITEMS

__all__ = ["InventoryScreen", "SLOTS"]

#: Slots, in the order they are shown. The same order the sidebar uses.
SLOTS: tuple[str, ...] = ("weapon", "armour", "amulet")

#: How wide each column is. The longest slot word is six, and the longest name
#: the game can hand you is "the revenant's patience" at twenty-three -- both
#: measured against the real items by a test rather than trusted to stay that
#: way.
#: Width of the panel, in cells. Set in ``app.tcss`` and named here so the
#: fitting test has something to check against instead of a magic number.
#: Raised from 80 when weapons started carrying statuses: "+4 damage, +15%
#: crit, +0.10 speed, chilled" is a real description now, and a wrapped
#: description in a column reads as a mistake.
PANEL_WIDTH = 86

SLOT_WIDTH = 8
NAME_WIDTH = 24


class InventoryScreen(ModalScreen[None]):
    """What is carried, what is worn, and what each of them does."""

    BINDINGS = [Binding("escape", "dismiss", "Close")]

    DEFAULT_CSS = """
    InventoryScreen {
        align: center middle;
        background: $background 70%;
    }
    """

    def __init__(self, state: GameState) -> None:
        super().__init__()
        self.state = state

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="inventory"):
            yield Static("CARRIED AND WORN", id="inventory-title")
            yield Static(self._sheet(), id="inventory-body")
            yield Static(
                "[bold]q[/] drink   [bold]c[/] the character sheet   "
                "walk over gear to swap it",
                id="inventory-hint",
            )

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
        """Everything carried and worn, as markup.

        One block of text with aligned columns rather than a widget tree: a dozen
        ``Static`` widgets would be a dozen things to keep in sync for no gain.
        """
        lines: list[str] = []

        lines.append("[dim]in the pack[/]")
        lines += self._pack()
        lines.append("")

        lines.append("[dim]worn[/]")
        lines += self._worn()

        if self.state.curses:
            # Given their own block rather than a column, because a price is a
            # sentence and the player needs reminding what they agreed to.
            lines.append("")
            lines.append("[dim]on you, and not by choice[/]")
            for curse in self.state.curses:
                lines.append(f"  [bold red]{curse.name}[/]  [dim]{curse.price}[/]")

        return "\n".join(lines)

    def _pack(self) -> list[str]:
        """Every draught, once, with what it is worth.

        Counted rather than listed: three potions is one line and one decision,
        and three lines saying "heals 8" is the same sentence three times.
        """
        counts: dict[str, int] = {}
        for item in self.state.inventory:
            counts[item.item_id] = counts.get(item.item_id, 0) + 1

        if not counts:
            return ["  [dim]nothing[/]"]

        lines = []
        for item_id, count in sorted(counts.items(), key=lambda pair: -pair[1]):
            template = ITEMS[item_id]
            name = f"{count}x {template.name}" if count > 1 else template.name
            lines.append(_entry("", name, describe_item(template)))
        return lines

    def _worn(self) -> list[str]:
        lines = []
        for slot in SLOTS:
            item = self.state.player.equipment.get(slot)
            if item is None:
                lines.append(f"  [dim]{slot:<{SLOT_WIDTH}}{'nothing':<{NAME_WIDTH}}[/]")
                continue
            lines.append(
                _entry(slot, item.name, describe_item(ITEMS[item.item_id]))
            )
        return lines


def _entry(slot: str, name: str, description: str) -> str:
    """A slot, a name and what it does, in three columns.

    The slot is there even when the row is a draught and has none, so the two
    blocks line up and the eye can run down one column.
    """
    return (
        f"  [dim]{slot:<{SLOT_WIDTH}}[/]"
        f"[bold]{name:<{NAME_WIDTH}}[/]"
        f"[dim]{description}[/]"
    )
