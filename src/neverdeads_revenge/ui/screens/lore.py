"""The book.

Every page of the chronicle in the order they belong in, whether or not they
have been found. A page that has been found reads; one that has not is a gap
with the number still on it.

That is the whole design of the thing. The pages turn up anywhere -- a run can
find the fifteenth before the second -- and the *numbering* is what makes that
work rather than being a nuisance: a page found out of order goes into its own
place, and the holes around it say what is still out there. A book that only
listed what you had would be a pile; the gaps are what make it a book.

Reading it is free and it is not a turn. Nothing here touches a run.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Static

from ...game.lore import PAGE_COUNT, TITLE, numeral, page
from ...persistence import MetaProgress

__all__ = ["LoreScreen"]


class LoreScreen(Screen[None]):
    """The chronicle, with its holes in it."""

    BINDINGS = [Binding("escape", "close", "Close")]

    DEFAULT_CSS = """
    LoreScreen {
        align: center middle;
    }
    #lore {
        width: 96;
        height: 1fr;
        padding: 1 2;
    }
    #lore-title {
        width: 1fr;
        height: auto;
        text-style: bold;
        color: $accent;
    }
    #lore-progress {
        width: 1fr;
        height: auto;
        color: #8a9ba8;
        margin: 0 0 1 0;
    }
    #lore-body {
        width: 1fr;
        height: 1fr;
    }
    #lore-hint {
        width: 1fr;
        height: auto;
        margin: 1 0 0 0;
        color: #6b6b6b;
    }
    """

    def __init__(self, progress: MetaProgress) -> None:
        super().__init__()
        self.progress = progress

    def compose(self) -> ComposeResult:
        found = len(self.progress.pages)
        with VerticalScroll(id="lore"):
            yield Static(TITLE.upper(), id="lore-title")
            yield Static(
                f"{numeral(found)} of {numeral(PAGE_COUNT)} pages recovered"
                if found
                else "nothing recovered yet",
                id="lore-progress",
            )
            yield Static(self._book(), id="lore-body")
            yield Static("escape  back", id="lore-hint")

    def _book(self) -> str:
        """Every page, in order, with the missing ones still taking up room."""
        blocks: list[str] = []
        for number in range(1, PAGE_COUNT + 1):
            heading = f"[bold #8a9ba8]{numeral(number)}[/]"
            body = page(number) or ""
            if number in self.progress.pages:
                blocks.append(f"{heading}\n{body}")
            else:
                blocks.append(f"{heading}\n[#3d3d47]— torn out —[/]")
        return "\n\n".join(blocks)

    def action_close(self) -> None:
        self.app.note_key("escape")
        self.dismiss()
