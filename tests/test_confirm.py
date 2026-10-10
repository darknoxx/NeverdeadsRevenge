"""Tests for the one question the game asks before it closes.

Everything else a player does happens inside a run and can be lived with or
lifted. Quitting the program cannot, so it is the only action in the game that
asks first.
"""

from __future__ import annotations

from neverdeads_revenge.ui.app import NeverdeadsRevenge
from neverdeads_revenge.ui.screens.confirm import ConfirmScreen
from neverdeads_revenge.ui.screens.title import TitleScreen


async def test_escape_at_the_title_asks_before_it_closes_the_game():
    app = NeverdeadsRevenge()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, TitleScreen)

        await pilot.press("escape")
        await pilot.pause()

        assert isinstance(app.screen, ConfirmScreen), "it closed without asking"
        assert not app._exit, "the game quit on the way to the question"
        assert "NEVERDEAD'S REVENGE" in str(
            app.screen.query_one("#confirm-title").render()
        )


async def test_q_asks_the_same_question():
    """``q`` is the other key that used to close the game on the first press."""
    app = NeverdeadsRevenge()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("q")
        await pilot.pause()

        assert isinstance(app.screen, ConfirmScreen)


async def test_no_puts_you_back_on_the_title_with_the_game_still_running():
    app = NeverdeadsRevenge()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

        await pilot.press("n")
        await pilot.pause()

        assert isinstance(app.screen, TitleScreen)
        assert not app._exit


async def test_escape_answers_no_like_it_does_everywhere_else():
    app = NeverdeadsRevenge()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

        assert isinstance(app.screen, TitleScreen)
        assert not app._exit


async def test_yes_closes_the_game():
    app = NeverdeadsRevenge()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

        await pilot.press("y")
        await pilot.pause()

        assert app._exit, "yes did not quit"
