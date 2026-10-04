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

from dataclasses import dataclass

from neverdeads_revenge.core.rng import Rng

from .map import GroundItem

__all__ = ["ItemTemplate", "ITEMS", "make_item", "roll_item", "loot_count"]


@dataclass(frozen=True, slots=True)
class ItemTemplate:
    """A kind of item, and what drinking it does for you."""

    key: str
    name: str
    glyph: str
    color: str
    #: Health restored when drunk.
    heal: int
    #: Relative chance of being rolled for a floor.
    weight: float = 1.0
    #: How much ``weight`` grows per floor descended. The better draught gets
    #: more common as you go down, which is what makes a deep floor's loot worth
    #: the risk of the deep floor.
    weight_growth: float = 1.0


ITEMS: dict[str, ItemTemplate] = {
    "potion": ItemTemplate(
        key="potion",
        name="potion",
        glyph="!",
        color="bright_red",
        heal=8,
        weight=5.0,
    ),
    "elixir": ItemTemplate(
        key="elixir",
        name="elixir",
        glyph="*",
        color="bright_magenta",
        heal=20,
        weight=2.0,
        weight_growth=1.25,
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
    )


def _weight_at(template: ItemTemplate, depth: int) -> float:
    if depth < 1:
        return template.weight
    return template.weight * template.weight_growth ** (depth - 1)


def roll_item(rng: Rng, depth: int = 1) -> ItemTemplate:
    """Pick an item kind for a floor at ``depth``."""
    return rng.choice_weighted(
        [(t, _weight_at(t, depth)) for t in ITEMS.values()]
    )


def loot_count(depth: int) -> int:
    """How many items a floor holds.

    Deliberately stingy, and it grows slowly. Health is a run-long resource, so
    the supply of it is the difficulty dial that matters most: a floor that
    hands out four draughts is a floor where the monsters stop being scary.
    """
    return min(1 + depth // 3, 4)