"""Title screen.

The name is drawn in the block font from :mod:`neverdeads_revenge.ui.blocks`, and
every line is padded to the same width before it leaves here. Textual centres
each line of a ``Static`` on its own, so a ragged block would come out with the
second word centred independently of the first instead of sitting under it.

Below a certain width the block art wraps, and a wrapped block font is less
readable than no block font at all -- so the plain name is shown instead. That is
the one case where the font's size is the wrong size.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen

from ..blocks import render_word

__all__ = ["TitleScreen", "TITLE_ART"]

def _title_art() -> str:
    """The two words, stacked and aligned to each other.

    Every line is padded to the same width before it leaves here. Textual centres
    each line of a ``Static`` on its own, so a ragged block would come out with
    the second word centred independently of the first instead of sitting under
    it -- and the two lines would drift apart at any terminal width.
    """
    first = render_word("NEVERDEAD'S")
    second = render_word("REVENGE")

    width = max(len(line) for line in first)
    indent = max(0, (width - max(len(line) for line in second)) // 2)
    padded = [" " * indent + line for line in second]

    lines = [*first, "", *padded]
    return "\n".join(line.ljust(width) for line in lines)


TITLE_ART = _title_art()

#: Width the block art needs before it is worth drawing, including a little air.
#: Below this it wraps, and a wrapped block font is less readable than no block
#: font -- which is the whole complaint this file exists to answer.
ART_MIN_WIDTH = max(len(line) for line in TITLE_ART.splitlines()) + 2

#: Shown instead when the terminal cannot hold the block art.
PLAIN_TITLE = "N E V E R D E A D ' S\nR E V E N G E"

TAGLINE = "a terminal roguelite"


class TitleScreen(Screen[None]):
    """Press anything to begin."""

    BINDINGS = [
        Binding("s", "shop", "Shop"),
        Binding("h", "scores", "Scores"),
        Binding("escape", "quit", "Quit"),
        Binding("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield from _centered()

    def on_mount(self) -> None:
        self._fit_title()
        self._show_best()

    def on_resize(self) -> None:
        """Swap between the block art and the plain name as the width allows."""
        self._fit_title()

    def _show_best(self) -> None:
        from textual.widgets import Static

        best = getattr(self.app, "progress", None)
        self.query_one("#title-best", Static).update(
            best_line(best.best_score if best else 0)
        )

    def _fit_title(self) -> None:
        from textual.widgets import Static

        wide = self.app.size.width >= ART_MIN_WIDTH
        self.query_one("#title-art", Static).update(TITLE_ART if wide else PLAIN_TITLE)

    def action_scores(self) -> None:
        """``h`` looks at old runs instead of starting a new one."""
        from .scoreboard import ScoreboardScreen

        # Armed so a held ``h`` does not close the board it just opened.
        self.app.arm_repeat_filter()
        self.app.push_screen(ScoreboardScreen(self.app.progress))

    def action_shop(self) -> None:
        """``s`` spends coin instead of starting a run."""
        self.app.arm_repeat_filter()
        self.app.open_shop()

    def on_key(self, event) -> None:
        """Any key starts the game -- no hunting for the right one.

        Two exceptions, and they have to be named here because "any key" would
        otherwise swallow them: the bound keys, and a repeat of a key held on the
        screen before this one -- holding enter to leave the summary would
        otherwise start a run on the way past.
        """
        if event.key in ("s", "h", "escape", "q"):
            return  # a binding has it
        if self.app.note_key(event.key):
            event.stop()
            return
        event.stop()
        self.app.open_hero_select()


def _centered():
    from textual.containers import Vertical
    from textual.widgets import Static

    with Vertical(id="title-screen"):
        yield Static(TITLE_ART, id="title-art")
        yield Static(TAGLINE, id="title-subtitle")
        yield Static(id="title-best")
        yield Static(
            "\npress any key   ·   [bold]s[/] shop   ·   [bold]h[/] scores",
            id="title-hint",
        )


def best_line(best: int) -> str:
    """What the title screen says about the best run so far.

    Blank when there has never been a run. "best 0" on a first launch is a worse
    welcome than saying nothing at all.
    """
    return f"best  {best}" if best else ""
