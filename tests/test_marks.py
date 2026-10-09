"""Tests for the columns that say what is on you.

Two things are worth testing here, and the second is the reason a column counts
what it shows instead of letting the widget clip it:

* that the curses are in one column and the gifts in another, names only, each in
  the colour the character sheet uses for the same thing;
* that a column **never grows taller than the box it was given**, and says ``+N``
  when it has to stop.

A column whose whole purpose is that the player can see what is on them cannot be
the thing that quietly hides the fifth curse.
"""

from __future__ import annotations

from rich.text import Text

from neverdeads_revenge.game.actors import NOXX
from neverdeads_revenge.game.curses import CURSES
from neverdeads_revenge.game.gifts import GIFTS
from neverdeads_revenge.game.state import start_run
from neverdeads_revenge.ui.widgets.marks import marks_text

#: Every curse there is, for the "can it hold all of them" tests.
EVERY_CURSE = tuple(CURSES)

#: The two columns the screen builds, as they are handed to ``marks_text``.
CURSES_COLUMN = ("curses",)
MARKS_COLUMN = ("gifts", "effects")


def _covered_by(text: Text, needle: str, colour: str) -> bool:
    """Whether ``needle`` is drawn in a span whose style names ``colour``."""
    plain = str(text)
    start = plain.index(needle)
    return any(
        colour in str(span.style) and span.start <= start < span.end
        for span in text.spans
    )


# -- what it says ------------------------------------------------------------
def test_a_curse_is_a_red_name_and_nothing_else():
    state = start_run(NOXX, seed=3)
    state.add_curse(CURSES["wither"])

    text = marks_text(state, ("curses",))

    assert "WITHER" in str(text)
    assert _covered_by(text, "WITHER", "red"), "the curse is not red"
    # The sentence is the character sheet's job now, not the column's.
    assert "quarter" not in str(text)


def test_a_gift_is_a_green_name_and_nothing_else():
    state = start_run(NOXX, seed=3)
    state.gifts.add("kind_dark")

    text = marks_text(state, MARKS_COLUMN)

    assert "THE KIND DARK" in str(text)
    assert _covered_by(text, "THE KIND DARK", "green"), "the gift is not green"
    assert "floor" not in str(text)


def test_an_effect_is_a_cyan_name():
    state = start_run(NOXX, seed=3)
    state.wilds.add("greed")

    text = marks_text(state, MARKS_COLUMN)

    assert "greed" in str(text)
    assert _covered_by(text, "greed", "cyan"), "the effect is not cyan"


def test_the_borrowed_hour_and_face_are_named_while_they_are_live():
    state = start_run(NOXX, seed=3)
    state.rewind_ready = True
    state.shrouded = 2

    plain = str(marks_text(state, MARKS_COLUMN))

    assert "the borrowed hour" in plain
    assert "the borrowed face" in plain


def test_an_empty_column_still_says_what_it_is():
    """A bare box is a box a player has to guess at."""
    text = marks_text(start_run(NOXX, seed=3), CURSES_COLUMN)

    assert "CURSES" in str(text)
    assert "WITHER" not in str(text)


def test_the_columns_do_not_show_each_others_groups():
    state = start_run(NOXX, seed=3)
    state.add_curse(CURSES["wither"])
    state.gifts.add("kind_dark")

    curses_only = str(marks_text(state, CURSES_COLUMN))
    marks_only = str(marks_text(state, MARKS_COLUMN))

    assert "WITHER" in curses_only and "KIND DARK" not in curses_only
    assert "KIND DARK" in marks_only and "WITHER" not in marks_only


# -- what it refuses to do ---------------------------------------------------
def test_a_column_never_shows_more_lines_than_it_was_given():
    state = start_run(NOXX, seed=3)
    for key in EVERY_CURSE:
        state.add_curse(CURSES[key])

    for budget in (1, 2, 3, 6, 10, 30):
        text = marks_text(state, CURSES_COLUMN, budget=budget)
        assert len(str(text).splitlines()) <= budget, budget


def test_it_counts_what_it_left_out():
    """A number, because it is a column of names and the thing being counted is
    names."""
    state = start_run(NOXX, seed=3)
    for key in EVERY_CURSE:
        state.add_curse(CURSES[key])

    plain = str(marks_text(state, CURSES_COLUMN, budget=4))

    assert f"+{len(EVERY_CURSE) - 2}" in plain, plain


def test_a_name_too_long_for_the_column_is_marked_rather_than_wrapped():
    state = start_run(NOXX, seed=3)
    state.gifts.add("kind_dark")

    lines = str(marks_text(state, MARKS_COLUMN, width=8)).splitlines()

    assert any("…" in line for line in lines)
    assert all(len(line) <= 8 for line in lines), "a name wrapped"


# -- the widgets -------------------------------------------------------------
def _game(app):
    """Start a run on the app and hand back its screen."""
    from neverdeads_revenge.ui.screens.game import GameScreen

    app.push_screen(GameScreen("noxx", seed=3))
    return app.screen


def _fill(screen) -> None:
    """Put a little of everything on the run."""
    for key in EVERY_CURSE:
        screen.state.add_curse(CURSES[key])
    screen.state.gifts.update(GIFTS)
    screen.state.wilds.update(("greed", "pact", "grave_goods"))
    screen.state.rewind_ready = True
    screen.state.shrouded = 3
    screen._refresh_all()


async def test_a_curse_taken_mid_run_shows_up_at_once():
    """The run is mutated in place, so a reactive holding the same object never
    fires. The screen calls ``redraw`` for exactly this reason."""
    from neverdeads_revenge.ui.app import NeverdeadsRevenge
    from neverdeads_revenge.ui.widgets.marks import Marks

    app = NeverdeadsRevenge()
    async with app.run_test(size=(100, 34)) as pilot:
        screen = _game(app)
        await pilot.pause()
        column = screen.query_one("#curses", Marks)
        assert "WITHER" not in str(column.render())

        screen.state.add_curse(CURSES["wither"])
        screen._refresh_all()
        await pilot.pause()

        assert "WITHER" in str(column.render()), "the column did not notice"


async def test_the_columns_are_always_on_screen():
    """No keypress to see what is on you: that was the whole complaint about the
    character sheet."""
    from neverdeads_revenge.ui.app import NeverdeadsRevenge
    from neverdeads_revenge.ui.widgets.marks import Marks

    app = NeverdeadsRevenge()
    async with app.run_test(size=(100, 34)) as pilot:
        screen = _game(app)
        await pilot.pause()

        for column in screen.query(Marks):
            assert column.display is True
            assert column.region.width > 0 and column.region.height > 0


async def test_the_columns_the_log_and_the_map_share_the_row_without_overlap():
    from neverdeads_revenge.ui.app import NeverdeadsRevenge
    from neverdeads_revenge.ui.widgets.marks import Marks
    from neverdeads_revenge.ui.widgets.message_log import MessageLog

    app = NeverdeadsRevenge()
    async with app.run_test(size=(100, 34)) as pilot:
        screen = _game(app)
        await pilot.pause()

        row = screen.query_one("#bottom")
        log = screen.query_one(MessageLog)
        curses, marks = screen.query(Marks)

        assert log.parent is row and curses.parent is row and marks.parent is row
        assert log.region.right <= curses.region.x, "the log and the curses overlap"
        assert curses.region.right <= marks.region.x, "the columns overlap"
        assert log.region.y == curses.region.y == marks.region.y


async def test_a_column_never_grows_taller_than_the_box_it_was_given():
    from neverdeads_revenge.ui.app import NeverdeadsRevenge
    from neverdeads_revenge.ui.widgets.marks import Marks

    app = NeverdeadsRevenge()
    async with app.run_test(size=(100, 34)) as pilot:
        screen = _game(app)
        await pilot.pause()
        _fill(screen)
        await pilot.pause()

        for column in screen.query(Marks):
            shown = len(str(column.render()).splitlines())
            assert shown <= column.size.height, f"{column.id} ran out of its box"
        assert "+" in str(screen.query_one("#curses", Marks).render())


async def test_the_columns_leave_the_legend_its_rows():
    """Why the sidebar runs the full height. While it stopped at the log it
    shared its height with the bottom row, and the draughts fell off the end of
    the legend -- which is the one thing the columns must not cost."""
    from neverdeads_revenge.ui.app import NeverdeadsRevenge
    from neverdeads_revenge.ui.widgets.legend import Legend

    app = NeverdeadsRevenge()
    async with app.run_test(size=(100, 34)) as pilot:
        screen = _game(app)
        await pilot.pause()

        legend = screen.query_one(Legend)
        lines = str(legend.render()).splitlines()

        assert len(lines) <= legend.size.height, "the legend is clipped"
        assert any("!" in line for line in lines), "the potion row is gone"
        assert any("*" in line for line in lines), "the elixir row is gone"
