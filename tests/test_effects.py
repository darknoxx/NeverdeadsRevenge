"""Tests for the panel that says what is on you.

Two things are worth testing here, and the second is the reason the panel wraps
its own lines instead of letting the widget do it:

* that it shows a curse in red and a gift in green, each with the sentence that
  says what it does -- the same sentences the character sheet prints;
* that it **never grows taller than the box it was given**, and says how many
  entries it had to leave out when it runs short.

A panel whose whole purpose is that the player can see what is on them cannot be
the thing that quietly hides the fifth curse.
"""

from __future__ import annotations

from rich.text import Text

from neverdeads_revenge.game.actors import NOXX
from neverdeads_revenge.game.curses import CURSES
from neverdeads_revenge.game.gifts import GIFTS
from neverdeads_revenge.game.state import start_run
from neverdeads_revenge.ui.widgets.effects import effects_text

#: Every curse there is, for the "can it hold all of them" tests.
EVERY_CURSE = tuple(CURSES)


def _covered_by(text: Text, needle: str, colour: str) -> bool:
    """Whether ``needle`` is drawn in a span whose style names ``colour``."""
    plain = str(text)
    start = plain.index(needle)
    return any(
        colour in str(span.style) and span.start <= start < span.end
        for span in text.spans
    )


# -- what it says ------------------------------------------------------------
def test_a_curse_is_shown_in_red_with_what_it_costs():
    state = start_run(NOXX, seed=3)
    state.add_curse(CURSES["wither"])

    text = effects_text(state, width=200)

    assert "WITHER" in str(text)
    assert CURSES["wither"].price in str(text)
    assert _covered_by(text, "WITHER", "red"), "the curse is not red"


def test_a_gift_is_shown_in_green_with_what_it_gives():
    state = start_run(NOXX, seed=3)
    state.gifts.add("kind_dark")

    text = effects_text(state, width=200)

    assert "THE KIND DARK" in str(text)
    assert GIFTS["kind_dark"].blurb in str(text)
    assert _covered_by(text, "THE KIND DARK", "green"), "the gift is not green"


def test_a_wild_offer_shows_its_catch_as_well_as_its_pitch():
    """An effect listed without its cost is the blind spot the panel exists to
    close."""
    from neverdeads_revenge.game.shop import WILD_OFFERS

    state = start_run(NOXX, seed=3)
    state.wilds.add("greed")

    plain = str(effects_text(state, width=200))

    assert WILD_OFFERS["greed"].pitch in plain
    assert WILD_OFFERS["greed"].catch in plain


def test_nothing_on_you_says_so():
    """Never an empty box: a player who has just pressed ``p`` should see that
    the panel is working and that there is simply nothing on them yet."""
    assert "nothing on you" in str(effects_text(start_run(NOXX, seed=3), width=200))


def test_the_borrowed_hour_and_face_are_live_effects():
    state = start_run(NOXX, seed=3)
    state.rewind_ready = True
    state.shrouded = 2

    plain = str(effects_text(state, width=200))

    assert "the borrowed hour" in plain
    assert "nothing lands for 2 more turns" in plain


# -- what it refuses to do ---------------------------------------------------
def test_it_never_shows_more_lines_than_it_was_given():
    """The budget is the whole shape of the panel, title and notice included."""
    state = start_run(NOXX, seed=3)
    for key in EVERY_CURSE:
        state.add_curse(CURSES[key])

    for budget in (1, 2, 3, 6, 10, 16, 30):
        text = effects_text(state, budget=budget)
        assert len(str(text).splitlines()) <= budget, budget


def test_it_says_how_many_it_left_out():
    import re

    state = start_run(NOXX, seed=3)
    for key in EVERY_CURSE:
        state.add_curse(CURSES[key])

    plain = str(effects_text(state, budget=8))

    # The count is of entries, not of lines: a number the player can act on.
    assert re.search(r"and \d+ more", plain), plain


def test_a_group_heading_is_not_shown_over_an_empty_group():
    """A label over nothing reads as a bug rather than as a truncation."""
    state = start_run(NOXX, seed=3)
    state.gifts.add("kind_dark")
    for key in EVERY_CURSE:
        state.add_curse(CURSES[key])

    # Small enough that the curses take everything and the gifts get nothing.
    plain = str(effects_text(state, budget=7))

    assert "gifts" not in plain, "a heading was printed over an empty group"


# -- the widget --------------------------------------------------------------
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
    from neverdeads_revenge.ui.widgets.effects import Effects

    app = NeverdeadsRevenge()
    async with app.run_test(size=(100, 34)) as pilot:
        screen = _game(app)
        await pilot.pause()
        panel = screen.query_one(Effects)
        assert "nothing on you" in str(panel.render())

        screen.state.add_curse(CURSES["wither"])
        screen._refresh_all()
        await pilot.pause()

        assert "WITHER" in str(panel.render()), "the panel did not notice"


async def test_the_panel_is_always_on_screen():
    """No keypress to see what is on you: that was the whole complaint about the
    character sheet."""
    from neverdeads_revenge.ui.app import NeverdeadsRevenge
    from neverdeads_revenge.ui.widgets.effects import Effects

    app = NeverdeadsRevenge()
    async with app.run_test(size=(100, 34)) as pilot:
        screen = _game(app)
        await pilot.pause()
        panel = screen.query_one(Effects)

        assert panel.display is True
        assert panel.region.width > 0 and panel.region.height > 0


async def test_the_panel_and_the_log_share_the_bottom_row():
    from neverdeads_revenge.ui.app import NeverdeadsRevenge
    from neverdeads_revenge.ui.widgets.effects import Effects
    from neverdeads_revenge.ui.widgets.message_log import MessageLog

    app = NeverdeadsRevenge()
    async with app.run_test(size=(100, 34)) as pilot:
        screen = _game(app)
        await pilot.pause()

        row = screen.query_one("#bottom")
        panel = screen.query_one(Effects)
        log = screen.query_one(MessageLog)

        assert panel.parent is row and log.parent is row
        assert log.region.right <= panel.region.x, "the two overlap"
        assert log.region.y == panel.region.y


async def test_the_panel_never_grows_taller_than_the_box_it_was_given():
    """The one that matters. The box has a fixed height, so a run with
    everything on it must still fit -- or say what it left out."""
    from neverdeads_revenge.ui.app import NeverdeadsRevenge
    from neverdeads_revenge.ui.widgets.effects import Effects

    app = NeverdeadsRevenge()
    async with app.run_test(size=(100, 34)) as pilot:
        screen = _game(app)
        await pilot.pause()
        _fill(screen)
        await pilot.pause()

        panel = screen.query_one(Effects)
        shown = len(str(panel.render()).splitlines())

        assert shown <= panel.size.height, "the panel ran out of its own box"
        assert "more" in str(panel.render()), "it truncated without saying so"


async def test_the_panel_leaves_the_legend_its_rows():
    """Why the sidebar runs the full height. While it stopped at log it shared
    its height with the bottom row, and the draughts fell off the end of the
    legend -- which is the one thing the panel must not cost."""
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


async def test_the_panel_survives_a_short_terminal():
    """A short window must not push the panel out of its own box."""
    from neverdeads_revenge.ui.app import NeverdeadsRevenge
    from neverdeads_revenge.ui.widgets.effects import Effects

    app = NeverdeadsRevenge()
    async with app.run_test(size=(100, 24)) as pilot:
        screen = _game(app)
        await pilot.pause()
        _fill(screen)
        await pilot.pause()

        panel = screen.query_one(Effects)
        shown = len(str(panel.render()).splitlines())

        assert panel.size.height > 0, "the panel was squeezed out entirely"
        assert shown <= panel.size.height
