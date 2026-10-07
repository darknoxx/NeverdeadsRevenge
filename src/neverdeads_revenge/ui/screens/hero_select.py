"""Hero select.

The roster is data, so the next hero costs a dictionary entry in
:mod:`game.actors` and nothing else. Locked slots are shown rather than hidden,
so the shape of what is coming is visible from the start.

The chosen hero is drawn as their letter in the block font from
:mod:`neverdeads_revenge.ui.blocks`, at the size the title spells its own name
in, because that letter is what the player is about to spend the whole run
looking for on the map. Choosing a character you have not seen is not much of a
choice.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Static

from ...game.actors import HEROES, Hero
from ...game.combat import chance_against
from ...game.pace import MAX_ACTIONS_PER_SECOND, actions_per_second
from ..blocks import ROWS, render_word

__all__ = ["HeroSelectScreen", "FUTURE_HEROES", "STAT_ROWS"]

#: Slugs for heroes that exist as a design idea but not in code yet.
FUTURE_HEROES = ("revenant", "warden")

#: Rows in the stat table. ``app.tcss`` pins the widget to this number, so a row
#: added here without a row added there is a row that gets clipped -- and a
#: locked slot has no table at all, so the widget has to hold its height anyway.
STAT_ROWS = 8


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
        # One column, centred on the screen, so the letter, the name, the prose
        # and the numbers all sit on the same axis. They used to be three
        # separate blocks with three different left edges, and the prose sat
        # against the left wall of the terminal.
        #
        # The centring is a container rather than ``align-h`` on the screen:
        # Textual ignores horizontal alignment on a ``Screen`` itself, which is
        # why the title screen wraps its own content the same way.
        # The roster goes inside the card rather than beside it. A full-width
        # child fills the container, and a container with nothing left over has
        # nothing to centre -- which is why the card sat against the left wall
        # while everything inside it looked correctly centred.
        with Vertical(id="hero-select"):
            with Vertical(id="hero-card"):
                yield Static(id="hero-art")
                yield Static(id="hero-name")
                yield Static(id="hero-blurb")
                yield Static(id="hero-stats")
                yield Static(id="hero-roster")

    def on_mount(self) -> None:
        self.redraw()

    # -- rendering ----------------------------------------------------------
    def redraw(self) -> None:
        hero = self.current
        self.query_one("#hero-roster", Static).update(self._roster())
        # One short line for the placeholder, a wrapped paragraph for a real
        # hero. Centred for the one and left-aligned for the other: a single
        # line sitting at the left edge of a forty-wide column reads as a
        # mistake rather than as alignment.
        self.query_one("#hero-blurb", Static).styles.text_align = (
            "center" if hero is None else "start"
        )
        if hero is None:
            self.query_one("#hero-art", Static).update(self._locked_art())
            self.query_one("#hero-name", Static).update("[dim]???[/]")
            self.query_one("#hero-blurb", Static).update(
                "\n[dim]Not yet resurrected.[/dim]\n"
            )
            self.query_one("#hero-stats", Static).update("")
            return

        self.query_one("#hero-art", Static).update(self._art(hero))
        # Name and title on one line, in the hero's own colour. The small glyph
        # that used to sit beside the name is gone: the letter above *is* the
        # glyph now, and printing it twice at two sizes is one of them too many.
        self.query_one("#hero-name", Static).update(
            f"[bold {hero.color}]{hero.name}[/]  [dim]{hero.title}[/]"
        )
        self.query_one("#hero-blurb", Static).update(hero.blurb)
        self.query_one("#hero-stats", Static).update(self._stat_block(hero))

    @staticmethod
    def _art(hero: Hero) -> str:
        """The hero's letter in blocks, in the colour they will be on the map."""
        art = render_word(hero.glyph)
        if not art:
            # A hero whose letter the font does not carry still gets a card.
            return f"[bold {hero.color}]{hero.glyph}[/]"
        return f"[bold {hero.color}]" + "\n".join(art) + "[/]"

    @staticmethod
    def _locked_art() -> str:
        """A question mark, centred in the same rows the real letters use.

        The same height on purpose. A locked slot that collapsed to a single row
        would make the whole screen jump as the player cycles through the roster,
        and the jump would land exactly on the slot that has nothing to show.
        """
        margin = "\n" * (ROWS // 2)
        return f"{margin}[dim]?[/]{margin}"

    def _roster(self) -> str:
        """One glyph per slot, the current one boxed, locked ones dim.

        The old screen only ever showed the hero you were already on, which was
        fine with a roster of one and useless with a roster of three: cycling
        through cards you cannot see the end of is not choosing, it is browsing.
        """
        parts: list[str] = []
        for index, hero in enumerate(self.slots):
            here = index == self._index
            if hero is None:
                cell = "[dim]?[/dim]"
            else:
                cell = f"[bold {hero.color}]{hero.glyph}[/]"
            parts.append(f"[reverse] {cell} [/reverse]" if here else f" {cell} ")
        return "  ".join(parts)

    @staticmethod
    def _stat_block(hero: Hero) -> str:
        """The numbers, one row each.

        The row count is fixed and ``app.tcss`` pins the widget to it, because a
        table that changed height would move everything below it -- and a locked
        slot has no table at all, so the card would shrink exactly where the
        player is cycling past. ``tests/test_ui.py`` asserts the count.
        """
        s = hero.stats
        rows = [
            ("health", f"{s.max_hp}", HeroSelectScreen._health_note(s.max_hp)),
            # The rate rather than the raw speed, and against its ceiling:
            # "9/20 a second" is what the number is *for*, and the ceiling is
            # what later equipment and upgrades have to spend.
            (
                "speed",
                f"{s.speed:.2f}",
                f"{actions_per_second(s.speed):.0f}/{MAX_ACTIONS_PER_SECOND:.0f} a second",
            ),
            ("crit", f"{s.crit_chance:.0%}", f"x{s.crit_multiplier:.1f} damage"),
            ("damage", f"{s.damage[0]}-{s.damage[1]}", "per hit"),
            # Accuracy was not on this screen at all, which hid the one thing
            # Walkyrion has that neither other hero does. And both of these are
            # worth ten points a step and clamped, so a bare integer is a number
            # with no meaning attached: the note is the worked example against a
            # monster with neither, which is what the floor-one templates are.
            (
                "accuracy",
                f"{s.accuracy}",
                f"hits a plain thing {chance_against(s.accuracy, 0):.0%}",
            ),
            (
                "evasion",
                f"{s.evasion}",
                f"their hit chance {chance_against(0, s.evasion):.0%}",
            ),
            ("armour", f"{s.armor}", "off every hit"),
            # The trait belongs on this screen. It is the difference between
            # three stat lines and three characters: Noxx gets faster, Yeti
            # harder, Walkyrion sharper, and nothing else tells you that.
            ("revenge", hero.trait.label, f"{hero.trait.describe(1)} per kill"),
        ]
        lines = [f"{label:<9}{value:<8}[dim]{note}[/dim]" for label, value, note in rows]
        return "\n".join(lines)

    @staticmethod
    def _health_note(max_hp: int) -> str:
        """Say what the health number means for this hero, not just that it exists.

        "low is a promise" was written for Noxx and read as nonsense beside
        Yeti's 46. The note is the only place the screen interprets a number
        instead of printing it, so it has to be about the hero being shown.
        """
        if max_hp >= 44:
            return "a long argument"
        if max_hp >= 32:
            return "room to be wrong"
        return "low is a promise"

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
