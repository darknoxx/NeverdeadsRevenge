"""What is on you, in columns beside the log.

Two narrow panels share the bottom row with the message log: the curses in red
on the left, and the gifts in green with everything else in force in cyan on the
right.

**Names only.** The sentence that says what each one does is on the character
sheet, one keypress away, and the panel is for the glance rather than the read.
That is the whole difference between this and the version before it: the full
sentences cost two lines each, which meant a run with five curses could be shown
three of them and a note. A name is one line, so the column can hold the list --
which is what "what is on me" actually means.

The colours are the character sheet's, and so are the names, so the two places
cannot drift apart.

**It counts what it can show.** The box has a fixed height, so a long run would
otherwise run off the bottom and stop mid-list, silently. A column that cannot
show everything ends with ``+N`` -- a number, because it is a column of names and
the thing being counted is names.
"""

from __future__ import annotations

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

from ...game.gifts import gift_by_key
from ...game.shop import WILD_OFFERS
from ...game.state import GameState

__all__ = ["Marks", "CURSES_WIDTH", "MARKS_WIDTH", "marks_text"]

#: Width of the curses column, in cells. Wide enough for the longest curse name
#: ("HESITATION", ten) with room for the border and padding.
CURSES_WIDTH = 16

#: Width of the other column. Wider, because the gift names are long -- "THE
#: BORROWED HOUR" is seventeen -- and an offer can be longer still.
MARKS_WIDTH = 22

#: The groups each panel may show, and the colour each is drawn in. The same
#: colours the character sheet uses for the same three things.
STYLE = {"curses": "red", "gifts": "green", "effects": "cyan"}


class Marks(Static):
    """One column of what is on you."""

    DEFAULT_CSS = """
    Marks {
        height: 1fr;
        border: round $panel;
        background: $surface;
        padding: 0 1;
    }
    """

    #: The run whose marks this column describes. Reactive so a *new* run redraws
    #: on assignment; a run that has changed in place is redrawn by the screen
    #: calling :meth:`redraw`, exactly as the HUD is -- a reactive holding the
    #: same object never fires.
    state: reactive[GameState | None] = reactive(None, layout=True)

    def __init__(self, kinds: tuple[str, ...], **kwargs) -> None:
        kwargs.setdefault("markup", False)
        super().__init__(**kwargs)
        #: Which groups this column shows, in order.
        self.kinds = kinds
        # A widget that can take focus swallows movement keys.
        self.can_focus = False

    def on_mount(self) -> None:
        self.redraw()

    def on_resize(self) -> None:
        """Re-measure on a resize.

        How much the column can show is a function of how tall it is, so a
        window that gets shorter has to rebuild rather than leave a truncated
        list claiming to be the whole of it.
        """
        self.redraw()

    def watch_state(self, state: GameState | None) -> None:
        self.redraw()

    def redraw(self) -> None:
        """Rebuild the column from the run.

        Named ``redraw`` rather than ``refresh`` on purpose: ``refresh`` is
        Textual's own method, and overwriting it breaks internal callers that
        expect the return value. The legend learned this first.
        """
        self.update(
            marks_text(
                self.state,
                self.kinds,
                width=self.size.width or MARKS_WIDTH - 4,
                budget=self.size.height or None,
            )
        )


def marks_text(
    state: GameState | None,
    kinds: tuple[str, ...],
    width: int = MARKS_WIDTH - 4,
    budget: int | None = None,
) -> Text:
    """One column as a Rich ``Text``: a heading per group, then the names.

    A function rather than a method so a test can build the column from a run
    without a terminal, the way ``legend_rows`` is a function and not a widget.
    """
    entries: list[tuple[Text, bool]] = []
    for kind in kinds:
        entries.append((Text(kind.upper(), style="dim"), False))
        names = _names(state, kind)
        if not names:
            entries.append((Text("-", style="dim"), False))
            continue
        for name in names:
            entries.append((Text(_clip(name, width), style=STYLE[kind]), True))

    if budget is None or len(entries) <= budget:
        lines = [text for text, _ in entries]
    else:
        # One line is held back for the count, so saying "there is more" can
        # never be the line that falls off the bottom.
        lines = []
        dropped = 0
        for text, is_entry in entries:
            if len(lines) >= budget - 1:
                if is_entry:
                    dropped += 1
                continue
            lines.append(text)
        lines.append(Text(f"+{dropped}", style="dim"))

    out = Text()
    for index, line in enumerate(lines):
        if index:
            out.append("\n")
        out.append_text(line)
    return out


def _names(state: GameState | None, kind: str) -> list[str]:
    """The names in one group, in the order the character sheet prints them."""
    if state is None:
        return []

    if kind == "curses":
        return [curse.name for curse in state.curses]

    if kind == "gifts":
        names = []
        for key in sorted(state.gifts):
            gift = gift_by_key(key)
            if gift is not None:
                names.append(gift.name)
        return names

    if kind == "effects":
        names = []
        for key in sorted(state.wilds):
            offer = WILD_OFFERS.get(key)
            if offer is not None:
                names.append(offer.name)
        if state.rewind_ready:
            names.append("the borrowed hour")
        if state.shrouded:
            names.append("the borrowed face")
        return names

    return []


def _clip(name: str, width: int) -> str:
    """A name that fits the column, with a mark if it does not.

    A backstop rather than the design: the columns are sized so that everything
    in the game fits, and this exists so that something added later cannot wrap
    a column and push the rest of the list out of view.
    """
    if width <= 1 or len(name) <= width:
        return name
    return name[: width - 1] + "…"
