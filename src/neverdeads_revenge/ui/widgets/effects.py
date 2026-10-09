"""What is on you, beside the log.

The character sheet has shown this since the first curse -- gifts in green,
curses in red, each next to the sentence that says what it does. The trouble is
that the sheet is a keypress away and it *closes*: a player deciding whether to
open a chest, or whether to cross a room, is not going to open a modal to
remember what they are already carrying.

So the same blocks sit on the screen instead, all the time: curses in red, gifts
in green, and everything else in force in cyan. It shares the bottom row with the
message log, which is a tail view of short lines and was printing them into half
a screen of nothing.

It went through two worse shapes first. As an overlay on the map it was docked to
a layer that never painted, so it was invisible and ``p`` looked broken. As a
fourth column in the sidebar it could not be done at all: the sidebar is full to
the row (the legend needs every one of its fourteen) and the map will not give up
width. Side by side with the log, nothing has to be hidden to see anything else.

**It counts what it can show and says so when it cannot show everything.** The
box has a fixed height, so a long run -- six curses, three gifts, a couple of
offers -- would run off the bottom and stop mid-list, silently. A panel whose
whole purpose is that the player can see what is on them cannot be the thing that
quietly hides the fifth curse. So it wraps the entries itself, measures them
against the height it was given, and ends with ``... and N more`` when it has to
stop. ``c`` is still the whole sheet.

The three blocks are the same three the sheet prints, and the sentences are the
same sentences: a curse's ``price``, a gift's ``blurb``, an offer's ``pitch`` and
``catch``. Read once in the shop, they have to be readable again in a corridor,
or the trade the player made is a trade they have forgotten.
"""

from __future__ import annotations

import textwrap

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

from ...game.gifts import gift_by_key
from ...game.shop import WILD_OFFERS
from ...game.state import GameState

__all__ = ["Effects", "PANEL_WIDTH", "effects_text"]

#: Width of the box, in cells. It shares the row under the map with the log, so
#: this is also what decides how much width the log keeps.
PANEL_WIDTH = 42

#: Columns the box's own border (2) and padding (2) spend. A line that fits in
#: ``PANEL_WIDTH - CHROME`` fits the panel.
CHROME = 4


class Effects(Static):
    """The curses, gifts and effects in force, beside the log."""

    DEFAULT_CSS = f"""
    Effects {{
        width: {PANEL_WIDTH};
        height: 1fr;
        border: round $panel;
        background: $surface;
        padding: 0 1;
    }}
    """

    #: The run whose marks this panel describes. Reactive so a *new* run redraws
    #: on assignment; a run that has changed in place is redrawn by the screen
    #: calling :meth:`redraw`, exactly as the HUD is -- a reactive holding the
    #: same object never fires.
    state: reactive[GameState | None] = reactive(None, layout=True)

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("markup", False)
        super().__init__(**kwargs)
        # A widget that can take focus swallows movement keys.
        self.can_focus = False

    def on_mount(self) -> None:
        self.redraw()

    def on_resize(self) -> None:
        """Re-measure on a resize.

        How much the panel can show is a function of how tall it is, so a window
        that gets shorter has to rebuild rather than leave a truncated list
        claiming to be the whole of it.
        """
        self.redraw()

    def watch_state(self, state: GameState | None) -> None:
        self.redraw()

    def redraw(self) -> None:
        """Rebuild the panel from the run.

        Named ``redraw`` rather than ``refresh`` on purpose: ``refresh`` is
        Textual's own method, and overwriting it breaks internal callers that
        expect the return value. The legend learned this first.
        """
        self.update(
            effects_text(self.state, width=self._width(), budget=self._budget())
        )

    def _width(self) -> int:
        """The columns one line may use.

        Falls back to the nominal width before the first layout pass, which is
        also the width it will have afterwards -- the two agree, so the first
        frame is not a different shape from the second.
        """
        return self.size.width or PANEL_WIDTH - CHROME

    def _budget(self) -> int | None:
        """How many lines the panel may use: the box it was given.

        ``None`` before the first layout pass, which means "do not truncate" --
        one frame is allowed to be wrong, and the resize that follows corrects
        it.
        """
        return self.size.height or None


def effects_text(
    state: GameState | None,
    width: int = PANEL_WIDTH - CHROME,
    budget: int | None = None,
) -> Text:
    """The whole panel as one Rich ``Text``.

    ``budget`` is the total number of lines the panel may occupy, title and
    notice included -- the whole shape of the thing, not just the entries. It is
    applied at the end, to the finished list, so that no combination of a small
    budget and a long run can produce a panel taller than it was allowed to be.
    A function rather than a method so a test can build the panel from a run
    without a terminal, the way ``legend_rows`` is a function and not a widget.
    """
    lines: list[Text] = [Text("ON YOU", style="bold")]

    blocks = _blocks(state, width)
    if not blocks:
        lines.append(Text("nothing on you", style="dim"))
    else:
        # Two lines are not the entries': the title above them and the notice
        # below them. ``_fit`` is handed what is left.
        fitted, dropped = _fit(blocks, None if budget is None else budget - 2)
        lines.extend(fitted)
        if dropped:
            lines.append(
                Text(f"... and {dropped} more -- c for the whole sheet", style="dim")
            )

    if budget is not None:
        # ``max(1, ...)`` so that the title -- the one line that says what the
        # panel *is* -- survives a budget too small for anything else.
        lines = lines[: max(1, budget)]

    out = Text()
    for index, line in enumerate(lines):
        if index:
            out.append("\n")
        out.append_text(line)
    return out


def _blocks(state: GameState | None, width: int) -> list[tuple[Text, list[list[Text]]]]:
    """The panel as ``(heading, entries)``, one pair per group in force."""
    if state is None:
        return []

    groups = (
        ("curses", [(c.name, c.price) for c in state.curses], "bold red"),
        ("gifts", _gift_rows(state), "bold green"),
        ("effects", _effect_rows(state), "bold cyan"),
    )

    blocks: list[tuple[Text, list[list[Text]]]] = []
    for heading, rows, style in groups:
        if not rows:
            continue
        blocks.append(
            (
                Text(heading, style="dim"),
                [_entry(name, blurb, style, width) for name, blurb in rows],
            )
        )
    return blocks


def _fit(
    blocks: list[tuple[Text, list[list[Text]]]], budget: int | None
) -> tuple[list[Text], int]:
    """Lay the blocks out, dropping what does not fit.

    Returns the lines that fit and how many *entries* were left out -- the
    number a player can act on, not the number of lines.

    A heading is only printed when at least one of its entries is: a group label
    over an empty group reads as a bug rather than as a truncation.
    """
    lines: list[Text] = []
    dropped = 0

    for heading, entries in blocks:
        if budget is None:
            lines.append(heading)
            for entry in entries:
                lines.extend(entry)
            continue

        # One line is held back for the notice, and the heading costs one.
        room = budget - 2 - len(lines)
        fits = 0
        used = 0
        for entry in entries:
            if used + len(entry) > room:
                break
            used += len(entry)
            fits += 1

        if not fits:
            dropped += len(entries)
            continue

        lines.append(heading)
        for entry in entries[:fits]:
            lines.extend(entry)
        dropped += len(entries) - fits

    return lines, dropped


def _entry(name: str, blurb: str, style: str, width: int) -> list[Text]:
    """One entry, wrapped by hand.

    Wrapped here rather than by the widget because the panel has to know how
    many lines it is spending before it decides what to show. The name keeps its
    colour on the first line and the sentence stays dim, so a screen of red does
    not become unreadable -- the same split the character sheet makes.
    """
    head = f"  {name}"
    wrapped = textwrap.wrap(
        f"{head}  {blurb}", width=width, subsequent_indent="  "
    ) or [head]

    lines: list[Text] = []
    for index, line in enumerate(wrapped):
        piece = Text()
        if index == 0 and line.startswith(head):
            piece.append(head, style=style)
            piece.append(line[len(head) :], style="dim")
        else:
            piece.append(line, style="dim")
        lines.append(piece)
    return lines


def _gift_rows(state: GameState) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for key in sorted(state.gifts):
        gift = gift_by_key(key)
        if gift is not None:
            rows.append((gift.name, gift.blurb))
    return rows


def _effect_rows(state: GameState) -> list[tuple[str, str]]:
    """Everything else in force: what was bought, and what is live right now.

    The wild offers are the third set of run-long rules, beside the curses and
    the gifts, so they belong here -- and their *catch* is shown with their
    pitch, because an effect listed without its cost is the same blind spot this
    panel exists to close. The two borrowed-* rows are the other half of that:
    the gift block says what the hour and the face can do, and these say they
    are in hand this very turn.
    """
    rows: list[tuple[str, str]] = []
    for key in sorted(state.wilds):
        offer = WILD_OFFERS.get(key)
        if offer is not None:
            rows.append((offer.name, f"{offer.pitch} · {offer.catch}"))

    if state.rewind_ready:
        rows.append(
            ("the borrowed hour", "in hand: the last action can be taken back")
        )

    if state.shrouded:
        turns = "turn" if state.shrouded == 1 else "turns"
        rows.append(
            ("the borrowed face", f"nothing lands for {state.shrouded} more {turns}")
        )

    return rows
