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

from ..game.actors import ENEMIES, HEROES
from ..world.tiles import Tile

__all__ = ["PROLOGUE", "PROLOGUE_TITLE", "terrain_legend", "enemy_legend", "legend_rows"]

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
#: default the eye assumes. Both would only add noise.
LEGEND_TERRAIN: tuple[Tile, ...] = (
    Tile.WALL,
    Tile.STAIRS_DOWN,
    Tile.DOOR,
    Tile.RUBBLE,
    Tile.GRASS,
    Tile.WATER,
)


def terrain_legend() -> list[tuple[str, str]]:
    """``(glyph, meaning)`` for every terrain type worth naming."""
    return [(tile.glyph, tile.description) for tile in LEGEND_TERRAIN]


def enemy_legend() -> list[tuple[str, str]]:
    """``(glyph, meaning)`` for the player's own marker and every enemy.

    Built from the live templates, so adding a monster to ``ENEMIES`` adds it
    here without a second edit. The numbers are the ones that matter when a
    fight goes wrong: how fast it moves and how hard it hits.
    """
    rows: list[tuple[str, str]] = [
        (HEROES["noxx"].glyph, "you"),
    ]
    for key in ("ghoul", "bone", "wraith"):
        template = ENEMIES.get(key)
        if template is None:
            continue
        low, high = template.stats.damage
        speed = template.stats.speed
        pace = "slow" if speed < 0.85 else "even" if speed < 1.15 else "fast"
        # Two lines per monster: the numbers on one, so the panel does not need
        # a width that fits "skeleton: 14 hp, 3-6 dmg, even" on a single row.
        rows.append(
            (template.glyph, f"{template.name}, {pace} ({speed:.1f})"),
        )
        rows.append(
            (
                "",
                f"{template.stats.max_hp} hp, {low}-{high} dmg, "
                f"{template.behaviour}",
            )
        )
    return rows


def legend_rows() -> list[tuple[str, str]]:
    """The full legend: you, the monsters, then the terrain.

    A row with an empty glyph is a continuation or a spacer; the widget decides
    how to render it.
    """
    return [*enemy_legend(), ("", ""), *terrain_legend()]