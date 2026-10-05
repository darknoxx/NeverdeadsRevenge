"""The shop.

Opened from the title with ``s``. Everything it sells is described in
:mod:`neverdeads_revenge.game.shop`; this screen prices nothing and decides
nothing, it draws a list and asks for a purchase.

Handles its own keys rather than using a Textual list widget, for the same
reason the name entry does: a key held on the screen before this one keeps
arriving, and a focused widget would take those repeats as navigation. Owning the
keys means the repeats can be recognised and dropped.
"""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from ...game.shop import SECTIONS, Offer, ShopError, build_stock, buy

__all__ = ["ShopScreen"]


class ShopScreen(ModalScreen[None]):
    """Spend what the runs brought in."""

    BINDINGS = [
        Binding("s", "leave", "Leave"),
        Binding("escape", "leave", "Leave"),
    ]

    def __init__(self, progress) -> None:
        super().__init__()
        self.progress = progress
        self.offers: list[Offer] = []
        self.index = 0
        #: The last thing the shop said: a purchase, or a refusal.
        self.message = ""

    def compose(self) -> ComposeResult:
        with Vertical(id="shop"):
            yield Static("THE SHOP", id="shop-title")
            yield Static(id="shop-gold")
            yield Static(id="shop-list")
            yield Static(id="shop-message")
            yield Static(
                "up/down choose   [bold]enter[/] buy   [bold]s[/] leave",
                id="shop-hint",
            )

    def on_mount(self) -> None:
        self._restock()
        self._draw()

    # -- keys ---------------------------------------------------------------
    def on_key(self, event) -> None:
        # A key still repeating from the title is not a press. See App.note_key.
        if self.app.note_key(event.key):
            event.stop()
            return

        key = event.key
        if key in ("s", "escape"):
            return  # a binding has it
        if key in ("up", "k", "w"):
            event.stop()
            self._move(-1)
        elif key in ("down", "j"):
            event.stop()
            self._move(1)
        elif key in ("enter", "return"):
            event.stop()
            self._purchase()

    def action_leave(self) -> None:
        self.dismiss()

    def _move(self, delta: int) -> None:
        if not self.offers:
            return
        self.index = (self.index + delta) % len(self.offers)
        self._draw()

    def _purchase(self) -> None:
        if not self.offers:
            return
        offer = self.offers[self.index]
        try:
            self.message = buy(self.progress, offer)
        except ShopError as refusal:
            self.message = str(refusal)
        else:
            # Written immediately: coin spent is coin gone, and a crash on the
            # way back to the title must not hand it back.
            self.app.save_progress()
            self._restock()
        self._draw()

    def _restock(self) -> None:
        self.offers = build_stock(self.progress)
        self.index = max(0, min(self.index, len(self.offers) - 1))

    # -- drawing ------------------------------------------------------------
    def _draw(self) -> None:
        self.query_one("#shop-gold", Static).update(self._gold_line())
        self.query_one("#shop-list", Static).update(self._list())
        self.query_one("#shop-message", Static).update(self.message)

    def _gold_line(self) -> Text:
        line = Text(no_wrap=True)
        line.append("you have  ", style="dim")
        line.append(f"{self.progress.gold}", style="bold yellow")
        line.append("  coins")
        return line

    def _list(self) -> Text:
        body = Text(no_wrap=True)
        section = None
        for position, offer in enumerate(self.offers):
            if offer.section != section:
                if section is not None:
                    body.append("\n")
                body.append(f"{offer.section}\n", style="bold cyan")
                section = offer.section
            self._row(body, offer, position == self.index)
        return body

    def _row(self, body: Text, offer: Offer, selected: bool) -> None:
        """One line: cursor, name, price, what it does.

        A wild offer gets a second line for what it costs. The price of a
        bargain is the half the player has to read, and a footnote on the same
        line as the promise is a footnote nobody reads.
        """
        cursor = ">" if selected else " "
        if offer.maxed:
            body.append(f"{cursor} ", style="bold green")
            body.append(f"{offer.label:<22}", style="dim")
            body.append("   --  ", style="dim")
            body.append("already yours\n", style="dim green")
            return

        dim = not offer.affordable
        name_style = "#6b6b6b" if dim else ("bold" if selected else "")
        body.append(f"{cursor} ", style="bold yellow" if selected else "dim")
        body.append(f"{offer.label:<22}", style=name_style)
        body.append(
            f"{offer.price:>5}",
            style="#6b6b6b" if dim else "bold yellow",
        )
        body.append(f"  {offer.detail}", style="#6b6b6b" if dim else "dim")
        body.append("\n")

        if offer.catch:
            body.append(f"   {'':<22}     ", style="dim")
            body.append(f"{offer.catch}\n", style="#6b6b6b")
