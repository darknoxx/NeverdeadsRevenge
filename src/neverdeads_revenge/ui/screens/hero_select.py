"""Hero select.

Milestone 1 ships one hero, but the screen already iterates over the roster so
the next one costs a dictionary entry in :mod:`game.actors` and nothing else.
Locked slots are shown rather than hidden, so the shape of what is coming is
visible from the start.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Static

from ...game.actors import HEROES, Hero

__all__ = ["HeroSelectScreen"]

#: Slugs for heroes that exist as a design idea but not in code yet.
FUTURE_HEROES = ("revenant", "warden")


class HeroSelectScreen(Screen[str]):
    """Choose a hero.

    Returns the chosen hero's key. A locked slot has no hero to return, so
    confirming on one does nothing -- a mistake there should not start a run
    with an unnamed character.
    """

    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("left", "previous", "Previous"),
        Binding("right", "next", "Next"),
        Binding("h", "previous", "Previous"),
        Binding("l", "next", "Next"),
        Binding("enter", "confirm", "Play"),
        Binding("space", "confirm", "Play"),
    ]

    def __init__(self, unlocked: set[str] | None = None) -> None:
        super().__init__()
        self.unlocked = unlocked if unlocked is not None else set(HEROES)
        self._index = 0

    @property
    def slots(self) -> list[Hero | None]:
        """Every slot in display order: real heroes, then the future ones."""
        real = [HEROES[key] for key in HEROES]
        return [*real, *(None for _ in FUTURE_HEROES)]

    @property
    def current(self) -> Hero | None:
        return self.slots[self._index]

    def compose(self) -> ComposeResult:
        with Horizontal(id="hero-select"):
            yield Static(id="hero-name")
            yield Static(id="hero-title")
        yield Static(id="hero-blurb")
        yield Static(id="hero-stats")
        yield Static(id="hero-locked")

    def on_mount(self) -> None:
        self.redraw()

    # -- rendering ----------------------------------------------------------
    def redraw(self) -> None:
        hero = self.current
        if hero is None:
            self.query_one("#hero-name", Static).update("???")
            self.query_one("#hero-title", Static).update("")
            self.query_one("#hero-blurb", Static).update(
                "\n[dim]Not yet resurrected.[/dim]\n"
            )
            self.query_one("#hero-stats", Static).update("")
            self.query_one("#hero-locked", Static).update("LOCKED")
            return

        self.query_one("#hero-name", Static).update(hero.name)
        self.query_one("#hero-title", Static).update(hero.title)
        self.query_one("#hero-blurb", Static).update(hero.blurb)
        self.query_one("#hero-stats", Static).update(self._stat_block(hero))

        locked = len(self.slots) > len(HEROES)
        self.query_one("#hero-locked", Static).update(
            "\n".join(">" if i == self._index else " " for i in range(len(self.slots)))
            + ("   (enter to play)" if not locked else "")
        )

    def _stat_block(self, hero: Hero) -> str:
        s = hero.stats
        rows = [
            ("health", f"{s.max_hp}", "low is a promise"),
            ("speed", f"{s.speed:.2f}", "actions per turn"),
            ("crit", f"{s.crit_chance:.0%}", f"x{s.crit_multiplier:.1f} damage"),
            ("damage", f"{s.damage[0]}-{s.damage[1]}", "per hit"),
            ("evasion", f"{s.evasion}", "hard to pin down"),
            ("armour", f"{s.armor}", "soaks that much"),
        ]
        lines = [f"{label:<9}{value:<8}[dim]{note}[/dim]" for label, value, note in rows]
        return "\n".join(lines)

    # -- actions ------------------------------------------------------------
    def _move(self, delta: int) -> None:
        total = len(self.slots)
        self._index = (self._index + delta) % total
        self.redraw()

    def action_previous(self) -> None:
        self._move(-1)

    def action_next(self) -> None:
        self._move(1)

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_confirm(self) -> None:
        hero = self.current
        if hero is None:
            return
        self.dismiss(hero.key)
