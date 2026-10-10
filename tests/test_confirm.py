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


# -- the other one: throwing a run away --------------------------------------
async def _in_a_run(app, pilot):
    from neverdeads_revenge.ui.screens.game import GameScreen

    app._prologue_seen = True
    app.push_screen(GameScreen("noxx", seed=3))
    await pilot.pause()
    await pilot.press("escape")
    await pilot.pause()


async def test_q_in_the_pause_menu_asks_before_it_throws_the_run_away():
    """``q`` there does not save -- ``s`` is the one that saves -- so it is the
    other keypress in the game that cannot be undone."""
    from neverdeads_revenge.ui.screens.pause import PauseScreen

    app = NeverdeadsRevenge()
    async with app.run_test(size=(100, 34)) as pilot:
        await _in_a_run(app, pilot)
        assert isinstance(app.screen, PauseScreen)

        await pilot.press("q")
        await pilot.pause()

        assert isinstance(app.screen, ConfirmScreen), "it threw the run away"
        assert "QUIT TO THE TITLE" in str(
            app.screen.query_one("#confirm-title").render()
        )


async def test_no_puts_you_back_in_the_pause_with_the_run_still_there():
    from neverdeads_revenge.ui.screens.pause import PauseScreen

    app = NeverdeadsRevenge()
    async with app.run_test(size=(100, 34)) as pilot:
        await _in_a_run(app, pilot)

        await pilot.press("q")
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()

        assert isinstance(app.screen, PauseScreen)
        assert app.screen.query_one("#pause-title") is not None


async def test_yes_leaves_the_run_behind_and_writes_nothing():
    """The difference between the two ways out of the pause menu: one writes
    the floor down and one does not."""
    from neverdeads_revenge.persistence import run_path

    app = NeverdeadsRevenge()
    async with app.run_test(size=(100, 34)) as pilot:
        await _in_a_run(app, pilot)

        await pilot.press("q")
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()

        assert isinstance(app.screen, TitleScreen)
        assert not run_path().exists(), "q wrote a save it said it would not"


async def test_save_and_quit_still_writes_the_run_without_asking():
    """``s`` is not destructive -- it is the whole point of it -- so it must not
    have picked up a dialog on the way past."""
    from neverdeads_revenge.persistence import run_path

    app = NeverdeadsRevenge()
    async with app.run_test(size=(100, 34)) as pilot:
        await _in_a_run(app, pilot)

        await pilot.press("s")
        await pilot.pause()

        assert isinstance(app.screen, TitleScreen), "s opened a dialog"
        assert run_path().exists(), "s did not write the run"
