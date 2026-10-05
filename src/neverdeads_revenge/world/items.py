"""Loot.

Items live in ``world/`` rather than ``game/`` for the same reason tiles do: the
generator has to place them, and the generator must not import the game layer.
An item is world content -- it exists on the map and can be seen, walked over and
picked up -- while what a *drink* does to your health is a game rule.

Right now everything is a healing draught. That is not a placeholder: a run has
one resource that runs out, health, and one way to get it back. Anything else
that could be found on the floor (a weapon, a scroll, a map) needs systems that
do not exist yet.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from neverdeads_revenge.core.rng import Rng

from .map import GroundItem
from .modifiers import Modifiers

__all__ = [
    "ItemTemplate",
    "ITEMS",
    "make_item",
    "roll_item",
    "loot_count",
    "equipment_count",
]


@dataclass(frozen=True, slots=True)
class ItemTemplate:
    """A kind of item, and what it does for you."""

    key: str
    name: str
    glyph: str
    color: str
    #: ``draught``, ``weapon`` or ``armour``. The legend groups by this, because
    #: one row per kind fits in the sidebar and one row per item does not.
    kind: str
    #: Health restored when drunk.
    heal: int = 0
    #: Which equipment slot it fills. ``None`` for something you drink.
    slot: str | None = None
    #: What wearing it changes.
    modifiers: Modifiers = Modifiers()
    #: Relative chance of being rolled for a floor.
    weight: float = 1.0
    #: How much ``weight`` grows per floor descended. Better things get more
    #: common as you go down, which is what makes a deep floor's loot worth the
    #: risk of the deep floor.
    weight_growth: float = 1.0


#: Glyph and colour per kind of thing. Weapons and armour follow the old
#: roguelike convention -- ``)`` for a blade, ``[`` for something you wear --
#: because it costs nothing to be legible to people who already know it.
WEAPON_GLYPH = ")"
WEAPON_COLOR = "bright_white"
ARMOUR_GLYPH = "["
ARMOUR_COLOR = "#b87333"

ITEMS: dict[str, ItemTemplate] = {
    # -- draughts ----------------------------------------------------------
    "potion": ItemTemplate(
        key="potion",
        name="potion",
        glyph="!",
        color="bright_red",
        kind="draught",
        heal=8,
        weight=5.0,
    ),
    "elixir": ItemTemplate(
        key="elixir",
        name="elixir",
        glyph="*",
        color="bright_magenta",
        kind="draught",
        heal=20,
        weight=2.0,
        weight_growth=1.25,
    ),
    # -- weapons -----------------------------------------------------------
    "knife": ItemTemplate(
        key="knife",
        name="chipped knife",
        glyph=WEAPON_GLYPH,
        color=WEAPON_COLOR,
        kind="weapon",
        slot="weapon",
        modifiers=Modifiers(damage=1),
        weight=5.0,
    ),
    "blade": ItemTemplate(
        key="blade",
        name="serrated blade",
        glyph=WEAPON_GLYPH,
        color=WEAPON_COLOR,
        kind="weapon",
        slot="weapon",
        modifiers=Modifiers(damage=2, crit_chance=0.05),
        weight=3.0,
        weight_growth=1.10,
    ),
    "estoc": ItemTemplate(
        key="estoc",
        name="thin estoc",
        glyph=WEAPON_GLYPH,
        color=WEAPON_COLOR,
        kind="weapon",
        slot="weapon",
        modifiers=Modifiers(damage=1, crit_chance=0.10, crit_multiplier=0.2),
        weight=2.0,
        weight_growth=1.18,
    ),
    "cleaver": ItemTemplate(
        key="cleaver",
        name="rusted cleaver",
        glyph=WEAPON_GLYPH,
        color=WEAPON_COLOR,
        kind="weapon",
        slot="weapon",
        # Heavy: the most damage of the four and the only one that costs speed,
        # so "better weapon" is a decision rather than a straight upgrade.
        modifiers=Modifiers(damage=3, speed=-0.15),
        weight=2.0,
        weight_growth=1.15,
    ),
    # -- armour ------------------------------------------------------------
    "leather": ItemTemplate(
        key="leather",
        name="leather coat",
        glyph=ARMOUR_GLYPH,
        color=ARMOUR_COLOR,
        kind="armour",
        slot="armour",
        modifiers=Modifiers(armor=1),
        weight=5.0,
    ),
    "cloak": ItemTemplate(
        key="cloak",
        name="grey cloak",
        glyph=ARMOUR_GLYPH,
        color=ARMOUR_COLOR,
        kind="armour",
        slot="armour",
        # Evasion is worth ten points of enemy hit chance per point, so one is
        # already a lot. Two measured as a 30-point swing and made the floor
        # loot worth more than the fights.
        modifiers=Modifiers(evasion=1),
        weight=3.0,
        weight_growth=1.10,
    ),
    "boots": ItemTemplate(
        key="boots",
        name="swift boots",
        glyph=ARMOUR_GLYPH,
        color=ARMOUR_COLOR,
        kind="armour",
        slot="armour",
        modifiers=Modifiers(speed=0.15, evasion=1),
        weight=2.0,
        weight_growth=1.15,
    ),
}


def make_item(template: ItemTemplate) -> GroundItem:
    """Create a floor item from a template."""
    return GroundItem(
        item_id=template.key,
        name=template.name,
        glyph=template.glyph,
        color=template.color,
        heal=template.heal,
        kind=template.kind,
        slot=template.slot,
        modifiers=template.modifiers,
    )


def _weight_at(template: ItemTemplate, depth: int) -> float:
    if depth < 1:
        return template.weight
    return template.weight * template.weight_growth ** (depth - 1)


def roll_item(
    rng: Rng, depth: int = 1, kinds: tuple[str, ...] | None = None
) -> ItemTemplate:
    """Pick an item kind for a floor at ``depth``.

    ``kinds`` restricts the pool. Draughts and equipment are rolled separately
    rather than from one table, and that is not a detail: a single table cut the
    supply of healing to a quarter the moment equipment was added, and the game
    became far harder without anything obviously having changed.
    """
    pool = [t for t in ITEMS.values() if kinds is None or t.kind in kinds]
    return rng.choice_weighted([(t, _weight_at(t, depth)) for t in pool])


def loot_count(depth: int) -> int:
    """How many draughts a floor holds.

    Deliberately stingy, and it grows slowly. Health is a run-long resource, so
    the supply of it is the difficulty dial that matters most: a floor that
    hands out four draughts is a floor where the monsters stop being scary.
    """
    return min(1 + depth // 3, 4)


def equipment_count(depth: int) -> int:
    """How many weapons and coats a floor holds, on top of the draughts.

    Its own budget, not a share of the draughts'. Kept small and grown slowly:
    equipment is never used up, so every piece is a permanent upgrade, and a
    floor that scatters three of them is handing out three of those across a run
    that only has ten floors. The strong tier is meant to be the chests.
    """
    return min(1 + depth // 5, 2)