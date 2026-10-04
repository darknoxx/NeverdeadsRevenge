"""The prologue and the map legend.

Both live here, in the headless layer, for a reason that is not tidiness: the
legend's terrain half is generated from :class:`~neverdeads_revenge.world.tiles.Tile`
itself, so a new terrain type cannot be added without the legend noticing. The
same goes for the enemy half, which is read from ``ENEMIES``. Deriving the text
rather than writing it twice is what keeps the sidebar from quietly going stale.

The prologue is plain data. It is shown once per run, before floor 1, and it is
the only place the game's premise is stated in prose -- everything afterwards has
to work without being told again.
"""

from __future__ import annotations

from ..game.actors import ENEMIES, HEROES, scale_template
from ..world.generator import ESCAPE_DEPTH
from ..world.items import ITEMS
from ..world.tiles import Tile

__all__ = [
    "PROLOGUE",
    "PROLOGUE_TITLE",
    "GOAL_HINT",
    "terrain_legend",
    "terrain_help",
    "enemy_legend",
    "item_legend",
    "legend_rows",
]

#: The one line a player must never have to guess at.
#:
#: The prologue asks whether there is a way out; this answers it and says where,
#: in the panel that is on screen at every moment. Kept here rather than in the
#: widget so the width test can measure it like any other legend line.
GOAL_HINT = f"the way out is on floor {ESCAPE_DEPTH}"

#: Shown on the title screen, before a run exists. Kept short on purpose.
PROLOGUE_TITLE = "Der Tod ist nicht das Ende. Das war dir nicht vergönnt."

#: Lines told as the run opens, one per floor entry, then gone.
#:
#: Ordered: the premise, then the moment of waking, then what the hero wants.
#: No line explains a mechanic; mechanics are explained when they are met.
PROLOGUE: tuple[str, ...] = (
    "Das Letzte, was unser Held noch wusste, war die Schlacht auf dem Berg Karpas.",
    "Eine schwingende Axt über seinem Kopf.",
    "Schwärze. Tiefste Schwärze.",
    "Doch sie war nicht ruhig. Sie war nicht sanft, sondern wild und verstörend.",
    "Nach einer gefühlten Ewigkeit gefangen in diesem unruhigen Nichts öffneten sich seine Augen.",
    "Die Schwärze hatte ihm die Körperlichkeit zurückgegeben.",
    "Eine Möglichkeit, diese Leere zu verlassen?",
)

#: Terrain worth explaining. VOID and FLOOR are omitted on purpose: void is
#: "not yet seen", which the player learns from the dimming, and floor is the
#: default the eye assumes. GRASS and WATER are omitted too: they are pure
#: decoration, and the panel has to stay short enough to fit the sidebar without
#: the bottom of it -- the loot and the goal -- falling off the screen.
LEGEND_TERRAIN: tuple[Tile, ...] = (
    Tile.WALL,
    Tile.DOOR,
    Tile.RUBBLE,
    Tile.STAIRS_DOWN,
    Tile.RIFT,
)


def terrain_legend() -> list[tuple[str, str]]:
    """``(glyph, meaning)`` for every terrain type worth naming."""
    return [(tile.glyph, tile.description) for tile in LEGEND_TERRAIN]


def item_legend() -> list[tuple[str, str]]:
    """``(glyph, meaning)`` for what can be picked up.

    Read from ``ITEMS``, so a new draught, or a change to one, shows up here
    without a second edit.
    """
    return [
        (template.glyph, f"{template.name}, heals {template.heal}")
        for template in ITEMS.values()
    ]


def enemy_legend(depth: int = 1) -> list[tuple[str, str]]:
    """``(glyph, meaning)`` for the player's own marker and every enemy.

    Built from the live templates, so adding a monster to ``ENEMIES`` adds it
    here without a second edit. The numbers are the ones that matter when a
    fight goes wrong: how fast it moves and how hard it hits.

    ``depth`` matters. Monsters get tougher as the run goes down, and a sidebar
    that kept quoting floor-1 numbers next to a floor-8 map would be lying to the
    player at exactly the moment they need the truth. The kinds listed stay the
    same at every depth -- a monster that only appears from floor 6 would need a
    different panel, not a longer one.
    """
    rows: list[tuple[str, str]] = [
        (HEROES["noxx"].glyph, "you"),
    ]
    for template in ENEMIES.values():
        scaled = scale_template(template, depth)
        low, high = scaled.stats.damage
        speed = scaled.stats.speed
        pace = "slow" if speed < 0.85 else "even" if speed < 1.15 else "fast"
        # One line per monster, abbreviated. The panel lives in the sidebar next
        # to the map, and the map needs the rows more than the prose does: full
        # sentences cost two lines per monster and push the terrain half, which
        # is the half a new player actually needs, off the bottom.
        rows.append(
            (
                template.glyph,
                f"{template.name} {pace} {scaled.stats.max_hp}hp {low}-{high}d",
            )
        )
    return rows


def legend_rows(depth: int = 1) -> list[tuple[str, str]]:
    """The always-on legend: you, the monsters, then the loot.

    Terrain is deliberately *not* here. ``LEGEND_TERRAIN`` is static -- a wall is
    a wall on every floor -- while the monsters' numbers change every descent and
    the loot is what keeps a run alive. Only the second kind earns a permanent
    place next to the map; the first is a reference you look up once, and it lives
    in the help text where there is room for it.

    That split is not just tidiness. The panel is clipped rather than scrolled,
    and every row spent on "patchy grass" is a row that could push the rift --
    the thing the whole run is for -- off the bottom of the sidebar.

    A row with an empty glyph is a section break, or a continuation line when it
    carries text of its own; the widget decides how to render it.
    """
    return [*enemy_legend(depth), ("", ""), *item_legend()]


def terrain_help() -> str:
    """The static terrain reference, formatted for the help text."""
    return "\n".join(f"[bold]{tile.glyph}[/] {tile.description}" for tile in LEGEND_TERRAIN)