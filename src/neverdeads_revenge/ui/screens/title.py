"""Title screen.

The name is drawn in a hand-made block font rather than a figlet one. Both
obvious alternatives were tried and rejected on the result:

* The ``_|/\\`` figlet style spells only the first word legibly, and barely:
  at five rows of underscores and pipes the eye cannot pick the letters out,
  which is exactly the complaint that produced this file.
* The block figlet fonts (ANSI Shadow and friends) read beautifully but are
  eight columns per letter, so ``NEVERDEAD'S`` alone is 88 wide and will not
  fit an 80-column terminal.

Five by five solid blocks are the compromise: legible at a glance, and the
whole name fits in 65 columns.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen

from ... import __version__

__all__ = ["TitleScreen", "TITLE_ART", "render_word"]

#: A five-row block font. ``█`` and space only.
#:
#: Only the letters the name needs. A full alphabet would be a font nobody
#: asked for; this is a piece of typography with one job.
BLOCK: dict[str, tuple[str, ...]] = {
    "A": (" ███ ", "█   █", "█████", "█   █", "█   █"),
    "D": ("████ ", "█   █", "█   █", "█   █", "████ "),
    "E": ("█████", "█    ", "████ ", "█    ", "█████"),
    "G": (" ████", "█    ", "█  ██", "█   █", " ███ "),
    "N": ("█   █", "██  █", "█ █ █", "█  ██", "█   █"),
    "R": ("████ ", "█   █", "████ ", "█  █ ", "█   █"),
    "S": (" ████", "█    ", " ███ ", "    █", "████ "),
    "V": ("█   █", "█   █", "█   █", " █ █ ", "  █  "),
    # One column wide and two rows tall, sitting high. In a five-wide cell it
    # floated so far from the letter before it that it read as a stray mark
    # rather than a possessive, and the name looked misspelled. Cells are not
    # all the same width here, and this is the reason why.
    "'": ("█", "█", " ", " ", " "),
}

#: Blank columns between letters.
LETTER_GAP = " "

ROWS = 5


def render_word(word: str) -> list[str]:
    """Draw ``word`` in the block font, one string per row.

    Unknown characters are skipped rather than raising: the alternative is a
    title screen that refuses to load because someone typed a letter the font
    does not have, and a title screen is the worst place to find that out.
    """
    # (glyph rows, whether a gap goes before it). The apostrophe takes no gap on
    # either side -- it is punctuation hanging off the letter, not a letter.
    cells: list[tuple[tuple[str, ...], bool]] = []
    previous = ""
    for char in word.upper():
        if char not in BLOCK:
            continue
        gap = bool(cells) and char != "'" and previous != "'"
        cells.append((BLOCK[char], gap))
        previous = char

    if not cells:
        return []
    return [
        "".join((LETTER_GAP if gap else "") + glyph[row] for glyph, gap in cells)
        for row in range(ROWS)
    ]


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
        Binding("escape", "quit", "Quit"),
        Binding("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield from _centered()

    def on_mount(self) -> None:
        self._fit_title()

    def on_resize(self) -> None:
        """Swap between the block art and the plain name as the width allows."""
        self._fit_title()

    def _fit_title(self) -> None:
        from textual.widgets import Static

        wide = self.app.size.width >= ART_MIN_WIDTH
        self.query_one("#title-art", Static).update(TITLE_ART if wide else PLAIN_TITLE)

    def on_key(self, event) -> None:
        """Any key starts the game -- no hunting for the right one."""
        event.stop()
        self.app.open_hero_select()


def _centered():
    from textual.containers import Vertical
    from textual.widgets import Static

    with Vertical(id="title-screen"):
        yield Static(TITLE_ART, id="title-art")
        yield Static(TAGLINE, id="title-subtitle")
        yield Static(f"\nversion {__version__}", id="title-version")
        yield Static("press any key", id="title-hint")
